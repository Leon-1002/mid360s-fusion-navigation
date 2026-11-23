#include "IMVApi.h"
#include <iostream>
#include <cstring>
int main() {
  IMV_DeviceList list{}; int rc=IMV_EnumDevices(&list,interfaceTypeUsb3);
  if(rc) return 1;
  int index=-1;
  for(unsigned i=0;i<list.nDevNum;++i) if(!std::strcmp(list.pDevInfo[i].serialNumber,"DD07657AAK00023")) index=i;
  if(index<0) return 2;
  IMV_HANDLE h=nullptr;
  if(IMV_CreateHandle(&h,modeByIndex,&index)) return 3;
  if(IMV_Open(h)) {IMV_DestroyHandle(h); return 4;}
  for(const char* name:{"Width","Height","WidthMax","HeightMax","OffsetX","OffsetY","BinningHorizontal","BinningVertical","DecimationHorizontal","DecimationVertical","DeviceLinkThroughputLimit","PayloadSize","MaxTransferSize","MaxNumTransfer","GainRaw"}) {
    int64_t v=0,lo=0,hi=0,inc=0;
    rc=IMV_GetIntFeatureValue(h,name,&v);
    if(!rc) {
      IMV_GetIntFeatureMin(h,name,&lo); IMV_GetIntFeatureMax(h,name,&hi); IMV_GetIntFeatureInc(h,name,&inc);
      std::cout<<name<<"="<<v<<" min="<<lo<<" max="<<hi<<" inc="<<inc<<std::endl;
    } else std::cout<<name<<" unavailable "<<rc<<std::endl;
  }
  for(const char* name:{"ExposureTime","ExposureAutoUpperLimit","ExposureAutoLowerLimit","Gain","GainRaw","AcquisitionFrameRate"}) {
    double v=0; rc=IMV_GetDoubleFeatureValue(h,name,&v);
    double lo=0,hi=0;
    if(!rc) {IMV_GetDoubleFeatureMin(h,name,&lo); IMV_GetDoubleFeatureMax(h,name,&hi);}
    std::cout<<name<<" rc="<<rc<<" value="<<v<<" min="<<lo<<" max="<<hi<<std::endl;
  }
  for(const char* name:{"PixelFormat","BinningHorizontalMode","BinningVerticalMode","ExposureAuto","GainAuto"}) {
    IMV_String v{}; rc=IMV_GetEnumFeatureSymbol(h,name,&v);
    std::cout<<name<<" rc="<<rc<<" value="<<v.str<<std::endl;
  }
  IMV_Close(h); IMV_DestroyHandle(h);
}
