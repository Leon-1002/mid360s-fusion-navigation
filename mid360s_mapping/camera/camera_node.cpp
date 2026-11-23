#include "IMVApi.h"
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <opencv2/opencv.hpp>
#include <chrono>
#include <fstream>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <vector>

void check(int code, const std::string &what) {
  if (code != IMV_OK) throw std::runtime_error(what + ": SDK error " + std::to_string(code));
}
struct Camera {
  IMV_HANDLE h = nullptr;
  bool opened = false, grabbing = false;
  std::vector<std::function<void()>> restore;
  ~Camera() {
    if (grabbing) IMV_StopGrabbing(h);
    for (auto it = restore.rbegin(); it != restore.rend(); ++it) (*it)();
    if (opened) IMV_Close(h);
    if (h) IMV_DestroyHandle(h);
  }
  void set_enum(const char *name, const char *value, std::ostream &snapshot) {
    IMV_String old{};
    check(IMV_GetEnumFeatureSymbol(h, name, &old), std::string("read ") + name);
    std::string saved = old.str;
    snapshot << name << '=' << saved << '\n'; snapshot.flush();
    check(IMV_SetEnumFeatureSymbol(h, name, value), std::string("set ") + name);
    restore.push_back([this, name, saved] { if (IMV_SetEnumFeatureSymbol(h,name,saved.c_str())) std::cerr << "Restore failed: " << name << '\n'; });
  }
  void set_rate(double rate, std::ostream &snapshot) {
    bool enabled = false; double previous = 0;
    check(IMV_GetBoolFeatureValue(h,"AcquisitionFrameRateEnable",&enabled),"read rate enable");
    check(IMV_GetDoubleFeatureValue(h,"AcquisitionFrameRate",&previous),"read rate");
    snapshot << "AcquisitionFrameRateEnable=" << enabled << "\nAcquisitionFrameRate=" << previous << '\n'; snapshot.flush();
    check(IMV_SetBoolFeatureValue(h,"AcquisitionFrameRateEnable",true),"enable rate limit");
    restore.push_back([this, enabled, previous] {
      if (IMV_SetDoubleFeatureValue(h,"AcquisitionFrameRate",previous)) std::cerr << "Restore rate failed\n";
      if (IMV_SetBoolFeatureValue(h,"AcquisitionFrameRateEnable",enabled)) std::cerr << "Restore rate enable failed\n";
    });
    check(IMV_SetDoubleFeatureValue(h,"AcquisitionFrameRate",rate),"set rate");
  }
};
struct FrameLease {
  IMV_HANDLE h; IMV_Frame f{}; bool valid = false;
  ~FrameLease() { if(valid) IMV_ReleaseFrame(h,&f); }
};

int main(int argc, char **argv) {
  rclcpp::init(argc,argv);
  cv::setNumThreads(2);
  int result = 0;
  try {
    auto node = std::make_shared<rclcpp::Node>("zm_camera");
    const auto serial = node->declare_parameter<std::string>("serial","DD07657AAK00023");
    const bool preview = node->declare_parameter<bool>("preview",true);
    const double seconds = node->declare_parameter<double>("seconds",0.0);
    const double rate = node->declare_parameter<double>("fps",5.0);
    const double exposure = node->declare_parameter<double>("exposure_us",10000.0);
    const double gain = node->declare_parameter<double>("gain",4.0);
    const bool hardware_trigger = node->declare_parameter<bool>("hardware_trigger",false);
    const int expected_frames = node->declare_parameter<int>("expected_frames",0);
    if (rate <= 0 || rate > 60 || seconds < 0) throw std::runtime_error("invalid fps or seconds");
    if (expected_frames < 0 || (expected_frames > 0 && !hardware_trigger))
      throw std::runtime_error("expected_frames requires hardware_trigger");
    auto pub = node->create_publisher<sensor_msgs::msg::Image>("/camera/image_raw",rclcpp::SensorDataQoS().keep_last(2));
    auto compressed_pub = node->create_publisher<sensor_msgs::msg::CompressedImage>("/camera/image_raw/compressed",rclcpp::SensorDataQoS().keep_last(2));
    Camera camera;
    IMV_DeviceList devices{};
    check(IMV_EnumDevices(&devices,interfaceTypeUsb3),"enumerate USB cameras");
    std::cout << "SDK=" << IMV_GetVersion() << " USB cameras=" << devices.nDevNum << std::endl;
    int selected = -1;
    for (unsigned i=0;i<devices.nDevNum;++i) {
      auto &d=devices.pDevInfo[i];
      std::cout << d.modelName << " serial=" << d.serialNumber << std::endl;
      if(serial==d.serialNumber) selected=static_cast<int>(i);
    }
    if(selected<0) throw std::runtime_error("Requested camera absent or USB permissions missing");
    check(IMV_CreateHandle(&camera.h,modeByIndex,&selected),"create handle");
    check(IMV_Open(camera.h),"open camera"); camera.opened=true;
    std::ofstream snapshot("settings-before.txt");
    if(!snapshot) throw std::runtime_error("cannot save settings snapshot");
    camera.set_enum("TriggerMode","Off",snapshot);
    if(hardware_trigger) {
      camera.set_enum("TriggerSelector","FrameStart",snapshot);
      camera.set_enum("TriggerMode","Off",snapshot);
      camera.set_enum("TriggerSource","Line1",snapshot);
      camera.set_enum("TriggerActivation","RisingEdge",snapshot);
    }
    camera.set_enum("AcquisitionMode","Continuous",snapshot);
    camera.set_rate(rate,snapshot);
    camera.set_enum("ExposureAuto","Off",snapshot);
    double previous_exposure=0;
    check(IMV_GetDoubleFeatureValue(camera.h,"ExposureTime",&previous_exposure),"read exposure");
    snapshot << "ExposureTime=" << previous_exposure << '\n'; snapshot.flush();
    check(IMV_SetDoubleFeatureValue(camera.h,"ExposureTime",exposure),"set exposure");
    camera.restore.push_back([&camera,previous_exposure] { if(IMV_SetDoubleFeatureValue(camera.h,"ExposureTime",previous_exposure)) std::cerr << "Restore exposure failed\n"; });
    camera.set_enum("GainAuto","Off",snapshot);
    double previous_gain=0;
    check(IMV_GetDoubleFeatureValue(camera.h,"GainRaw",&previous_gain),"read gain");
    snapshot << "GainRaw=" << previous_gain << '\n'; snapshot.flush();
    check(IMV_SetDoubleFeatureValue(camera.h,"GainRaw",gain),"set gain");
    camera.restore.push_back([&camera,previous_gain] { if(IMV_SetDoubleFeatureValue(camera.h,"GainRaw",previous_gain)) std::cerr << "Restore gain failed\n"; });
    int64_t previous_bandwidth=0;
    check(IMV_GetIntFeatureValue(camera.h,"DeviceLinkThroughputLimit",&previous_bandwidth),"read USB throughput");
    snapshot << "DeviceLinkThroughputLimit=" << previous_bandwidth << '\n'; snapshot.flush();
    check(IMV_SetIntFeatureValue(camera.h,"DeviceLinkThroughputLimit",100000000),"set USB throughput");
    camera.restore.push_back([&camera,previous_bandwidth] { if(IMV_SetIntFeatureValue(camera.h,"DeviceLinkThroughputLimit",previous_bandwidth)) std::cerr << "Restore throughput failed\n"; });
    check(IMV_USB_SetUrbTransfer(camera.h,16,512),"set 8 MiB USB transfer queue");
    check(IMV_SetBufferCount(camera.h,3),"set buffers");
    if(hardware_trigger) camera.set_enum("TriggerMode","On",snapshot);
    check(IMV_StartGrabbing(camera.h),"start acquisition"); camera.grabbing=true;
    std::ofstream frames("frames.csv");
    frames << "frame_id,device_ticks,host_receive_ns,width,height,pixel_format\n";
    const std::string window="ZM-3000-60UC | USB preview | NOT synchronized";
    int exposure_ms=static_cast<int>(exposure/1000), gain_tenths=static_cast<int>(gain*10);
    if(preview) {
      cv::namedWindow(window,cv::WINDOW_NORMAL);
      cv::resizeWindow(window,960,740);
      cv::createTrackbar("Exposure ms",window,nullptr,100);
      cv::setTrackbarMin("Exposure ms",window,1);
      cv::setTrackbarPos("Exposure ms",window,exposure_ms);
      cv::createTrackbar("Gain /10",window,nullptr,160);
      cv::setTrackbarMin("Gain /10",window,10);
      cv::setTrackbarPos("Gain /10",window,gain_tenths);
    }
    using Clock=std::chrono::steady_clock;
    auto start=Clock::now(), last_report=start, last_frame=start;
    uint64_t count=0, report_count=0, gaps=0, previous=0, timeouts=0;
    double wait_total=0, publish_total=0, display_total=0;
    if(hardware_trigger)
      std::cout << "READY: FrameStart / Line1 / RisingEdge. Press STM32 RESET once. Expected frames="
                << expected_frames << std::endl;
    while(rclcpp::ok()) {
      if(preview) {
        const int next_exposure=cv::getTrackbarPos("Exposure ms",window);
        const int next_gain=cv::getTrackbarPos("Gain /10",window);
        if(next_exposure!=exposure_ms) {
          check(IMV_SetDoubleFeatureValue(camera.h,"ExposureTime",next_exposure*1000.0),"adjust exposure");
          exposure_ms=next_exposure; std::cout << "Exposure=" << exposure_ms << " ms" << std::endl;
        }
        if(next_gain!=gain_tenths) {
          check(IMV_SetDoubleFeatureValue(camera.h,"GainRaw",next_gain/10.0),"adjust gain");
          gain_tenths=next_gain; std::cout << "GainRaw=" << gain_tenths/10.0 << std::endl;
        }
      }
      if(seconds>0 && std::chrono::duration<double>(Clock::now()-start).count()>=seconds) break;
      if(hardware_trigger && expected_frames>0 && count>0 &&
         std::chrono::duration<double>(Clock::now()-last_frame).count()>=3) break;
      FrameLease lease{camera.h};
      auto phase=Clock::now();
      int rc=IMV_GetFrame(camera.h,&lease.f,1000);
      wait_total+=std::chrono::duration<double>(Clock::now()-phase).count();
      if(rc!=IMV_OK) {
        ++timeouts; std::cerr << "GetFrame error=" << rc << " timeouts=" << timeouts << std::endl;
        if(hardware_trigger && rc!=IMV_ERROR) check(rc,"hardware trigger GetFrame");
        if(!hardware_trigger && std::chrono::duration<double>(Clock::now()-last_frame).count()>8)
          throw std::runtime_error("No frame for 8 seconds");
        if(preview) {
          const int key=cv::waitKey(1);
          if(key=='q'||key=='Q'||key==27) break;
        }
        continue;
      }
      lease.valid=true; last_frame=Clock::now();
      const auto stamp=node->now(); // Host receive time only, NOT hardware exposure time.
      const auto &f=lease.f.frameInfo;
      if(f.status || !f.width || !f.height) throw std::runtime_error("Invalid frame status or dimensions");
      if(hardware_trigger && count && f.blockId<=previous)
        throw std::runtime_error("Non-increasing hardware-trigger frame ID");
      if(count && f.blockId>previous+1) gaps+=f.blockId-previous-1;
      previous=f.blockId; ++count;
      if(hardware_trigger) std::cout << "TRIGGER FRAME " << count << " id=" << f.blockId << std::endl;
      std::string encoding;
      switch(f.pixelFormat) {
        case gvspPixelMono8: encoding="mono8"; break;
        case gvspPixelBayRG8: encoding="bayer_rggb8"; break;
        case gvspPixelBayBG8: encoding="bayer_bggr8"; break;
        case gvspPixelBayGR8: encoding="bayer_grbg8"; break;
        case gvspPixelBayGB8: encoding="bayer_gbrg8"; break;
        default: throw std::runtime_error("Unsupported raw format: "+std::to_string(f.pixelFormat));
      }
      const size_t stride=f.width+f.paddingX;
      if(f.size<stride*f.height) throw std::runtime_error("Truncated raw image");
      sensor_msgs::msg::Image msg;
      phase=Clock::now();
      msg.header.stamp=stamp; msg.header.frame_id="camera_optical_frame";
      msg.width=f.width; msg.height=f.height; msg.encoding=encoding;
      msg.step=stride; msg.data.assign(lease.f.pData,lease.f.pData+stride*f.height);
      pub->publish(msg);
      publish_total+=std::chrono::duration<double>(Clock::now()-phase).count();
      frames << f.blockId << ',' << f.timeStamp << ',' << stamp.nanoseconds() << ',' << f.width << ',' << f.height << ',' << f.pixelFormat << '\n';
      if(hardware_trigger) frames.flush();
      phase=Clock::now();
      if(preview || count==10 || compressed_pub->get_subscription_count()>0) {
        cv::Mat bgr(f.height,f.width,CV_8UC3);
        IMV_PixelConvertParam convert{};
        convert.nWidth=f.width; convert.nHeight=f.height; convert.ePixelFormat=f.pixelFormat;
        convert.pSrcData=lease.f.pData; convert.nSrcDataLen=f.size;
        convert.nPaddingX=f.paddingX; convert.nPaddingY=f.paddingY;
        convert.eBayerDemosaic=demosaicBilinear; convert.eDstPixelFormat=gvspPixelBGR8;
        convert.pDstBuf=bgr.data; convert.nDstBufSize=bgr.total()*3;
        check(IMV_PixelConvert(camera.h,&convert),"convert preview");
        if(compressed_pub->get_subscription_count()>0) {
          sensor_msgs::msg::CompressedImage compressed;
          compressed.header=msg.header;
          compressed.format="bgr8; jpeg compressed bgr8";
          if(!cv::imencode(".jpg",bgr,compressed.data,{cv::IMWRITE_JPEG_QUALITY,90})) throw std::runtime_error("JPEG encoding failed");
          compressed_pub->publish(compressed);
        }
        if(count==10 && !cv::imwrite("snapshot.png",bgr)) throw std::runtime_error("Cannot save snapshot");
        if(preview) {
          cv::Mat small; cv::resize(bgr,small,cv::Size(960,640));
          cv::putText(small,"USB preview | host timestamps | Q to stop",{15,25},cv::FONT_HERSHEY_SIMPLEX,0.6,{0,255,0},1);
          cv::imshow(window,small);
          const int key=cv::waitKey(1);
          if(key=='q'||key=='Q'||key==27) break;
        }
      }
      display_total+=std::chrono::duration<double>(Clock::now()-phase).count();
      if(std::chrono::duration<double>(Clock::now()-last_report).count()>=2) {
        auto elapsed=std::chrono::duration<double>(Clock::now()-last_report).count();
        std::cout << "frames=" << count << " fps=" << (count-report_count)/elapsed << " gaps=" << gaps << " timeouts=" << timeouts << " " << f.width << "x" << f.height << " " << encoding << std::endl;
        std::cout << "mean_ms wait=" << wait_total*1000/count << " publish=" << publish_total*1000/count << " display=" << display_total*1000/count << std::endl;
        IMV_StreamStatisticsInfo stats{};
        if(IMV_GetStatisticsInfo(camera.h,&stats)==IMV_OK && stats.nCameraType==typeU3vCamera) {
          auto &u=stats.u3vStatisticsInfo;
          std::cout << "SDK received=" << u.imageReceived << " errors=" << u.imageError << " lost=" << u.lostPacketBlock << " fps=" << u.fps << " Mbps=" << u.bandwidth << std::endl;
        }
        report_count=count; last_report=Clock::now(); frames.flush();
      }
      rclcpp::spin_some(node);
    }
    std::cout << "END frames=" << count << " gaps=" << gaps << " timeouts=" << timeouts << std::endl;
    if(!count) throw std::runtime_error("No image acquired");
    if(expected_frames>0) {
      if(count!=static_cast<uint64_t>(expected_frames) || gaps)
        throw std::runtime_error("Trigger batch failed: expected=" + std::to_string(expected_frames) +
                                 " received=" + std::to_string(count) + " gaps=" + std::to_string(gaps));
      std::cout << "BATCH COUNT PASS: " << count << " frames, consecutive IDs. Check against STM32 pulse batch." << std::endl;
    }
    if(preview) cv::destroyAllWindows();
  } catch(const std::exception &e) { std::cerr << "ERROR: " << e.what() << std::endl; result=1; }
  rclcpp::shutdown(); return result;
}
