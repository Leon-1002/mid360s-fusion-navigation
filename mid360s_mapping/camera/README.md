# ZM-3000-60UC USB / ROS 2 接入

## 2026-11-23 更新（优先于下方历史 Line1 试验说明）

新线由用户确认：1 红、2 白、3 棕、4 绿、5 黄、6 黑。本轮使用 Line2：3 脚棕线接 PA1/A1，6 脚黑线接 STM32 GND；其余芯线单独绝缘，相机 USB 供电。

双击 `开始相机Line2触发测试.cmd`，入口显式选择 Line2 / Input / RisingEdge，并关闭输入反相；默认保留 30 ms、增益 2.0、目标 5 FPS。等 READY 后，使用 `stm32/camera-pulse-test` 固件按 RESET 一次，验收十脉冲对应十个连续帧号。正常退出恢复相机设置。

`启动相机.ps1 -HardwareTrigger` 的默认触发源现为 Line2，可用 `-TriggerSource Line1` 明确选择历史输入。无 `-HardwareTrigger` 的自由采集入口保持不变。新代码已构建，尚未完成新线的硬件收帧验证；当前相机时间戳仍是主机收帧时间。

完整清单在 `../sync-test/硬件触发测试步骤-20261123.txt`。雷达专用 `lidar-pps-uart` 固件不输出相机脉冲，不能用于相机十帧验收。

目标相机序列号：DD07657AAK00023，USB VID:PID = 2e03:0001。
此阶段仅连接 USB，自由采集；六芯线尚未接入，不代表已完成同步或视觉融合。

## 环境与运行

Windows 使用 usbipd-win 把指定相机交给 WSL Ubuntu-22.04。相机被 WSL 占用期间 Windows MVviewer 不能同时打开它。
雷达 USB 网卡独立使用，不转交给 WSL。

在 PowerShell 中启动（首次共享已完成）：

```powershell
powershell -ExecutionPolicy Bypass -File E:\chatgpt_project\mid360s_mapping\camera\启动相机.ps1
```

或在已连接相机的 WSL 中运行：

```bash
bash /mnt/e/chatgpt_project/mid360s_mapping/camera/run-camera.sh
```

图像窗口按 Q / Esc，或终端 Ctrl+C 退出；正常退出恢复启动前读取的 TriggerMode、AcquisitionMode、帧率设置、ExposureAuto、ExposureTime、GainAuto、GainRaw、DeviceLinkThroughputLimit，不写相机 UserSet。强制结束进程、断电等不能保证恢复；原值保存在每次 capture 目录的 settings-before.txt。

测试默认原始分辨率 3072×2048、5 Hz、固定曝光 10000 µs。当前 WSL USB 转发条件下 10 Hz 测试出现帧号跳变，因此 5 Hz 仅作为接入验证基线，不能据此宣称达到融合算法需要的帧率。原始话题 `/camera/image_raw`（Bayer RGGB8），另有 `/camera/image_raw/compressed`（全分辨率去马赛克后的 JPEG，质量 90，按订阅需要生成）。均为 SensorDataQoS / best effort，frame_id=camera_optical_frame。尚无标定参数、CameraInfo 或相机与雷达之间的 TF。

可通过 `--ros-args -p fps:=5.0 -p exposure_us:=10000.0` 指定临时采集参数；调试限时运行加 `-p seconds:=30.0`。画面黑时先检查镜头盖、光圈与朝向，不能把软件收到字节等同于光学成像合格。

Windows 启动入口设为曝光 30000 µs、GainRaw=2.0，供下次启动使用。现场试过 60000 µs / 4.0，但 snapshot 出现大面积过曝，因此不能作为验收参数。当前运行窗口的值以滑条为准。预览窗口提供 Exposure ms 滑条（1～100 ms）与 Gain /10 滑条（显示 20 对应 GainRaw=2.0），直接调整相机参数；最终标定前必须确定焦距/对焦和图像尺寸。长曝光与较高增益只是室内预览选择，不保证移动时清晰。

## 2026-11-19 阶段验证与未解决项

## 2026-11-20 相机单独硬触发测试入口

在 PowerShell 执行 `& 'E:\chatgpt_project\mid360s_mapping\camera\启动相机.ps1' -HardwareTrigger`，进入 FrameStart / Line1 / RisingEdge 模式，曝光 30000 µs、增益 2.0。窗口日志出现 READY 后按一次 STM32 RESET。固件每轮输出 10 个 1 Hz 脉冲，每个高电平 10 ms。采集最长运行 180 秒，收到图像后若连续 3 秒无新帧，则结束本轮。检查结果应为 10 帧、帧号连续，并保留 frames.csv。等待脉冲期间 SDK 可能返回通用取帧错误 -101，日志保留原始返回码，最终以实际帧计数验收。

不加 `-HardwareTrigger` 时使用原自由采集入口。硬触发设置在正常退出或捕获异常后按逆序恢复，并保存设置快照。强制结束和断电仍无法保证恢复。该测试验证相机接受脉冲的收帧表现，雷达 PPS 与时间戳对齐另行验证。

STM32 测试固件已由用户在 Keil 烧录，用户提供的日志包含 Programming Done、Verify OK。相机硬触发结果待实测。

### 前期采集记录

- WSL 已识别 USB 3.0 相机，SDK 已获取 3072×2048 BayerRG8 图像，用户确认能看到房间并在调亮后有所改善。
- 10 Hz 请求下实际约 6 FPS，存在帧号跳变；关闭预览及固定短曝光均未消除。原因仍需排查，不应归咎于相机硬件损坏。
- 5 Hz 短时采集无帧号跳变/取帧超时，后续更长观察出现少量帧号跳变；并非已经完成长时间稳定性验证。
- capture-20261119-134731-P6tJ 的 15 秒独立订阅：JPEG 约 5.02 Hz、IMU 约 198.25 Hz、里程计约 10.00 Hz；原始图像只有约 0.68 Hz，**原始图像传输验收失败，尚需解决**。测试没有被降低标准或跳过。
- fastdds-camera.xml 是一次未启用的实验配置：在复测时未发现任何话题，已从 sdk-env.sh 撤下，不作为当前方案。配置参考 [Fast DDS 2.6 官方说明](https://fast-dds.docs.eprosima.com/en/2.6.x/fastdds/xml_configuration/transports.html)。
- 图像头时间为主机接收时刻；雷达已有时钟处理，不能直接据二者头时间差宣称图像延迟或已同步。

**header.stamp 是主机收到图像的时刻，不能视作曝光时间，也未与雷达硬件同步。** frames.csv 另存相机原始 timeStamp 数值（未假定其单位）、帧号、主机时间。后续需要验证硬件触发、时钟对应关系、相机内参和相机/雷达外参。

每次运行保存到独立 capture-日期-时间-随机后缀目录：console.log、settings-before.txt、frames.csv、snapshot.png。终端显示帧率、帧号跳变累计 gaps 和取帧超时；不要只用“能打开窗口”判断稳定性。

## 依赖来源与隔离

官方包：[MVviewer Linux x86 2.3.2](http://download.huaraytech.com/pub/sdk/Ver2.3.2/Linux/x86/MVviewer_Ver2.3.2_Linux_x86_Build20220402.zip)

SHA256: `51B98261CBD63B6AC4581D834907976BE31C5E38EA55E25ADA4BE5B27ED2E370`

安装包仅解压到 vendor/extracted，未执行厂家 install.sh，未改网卡设置，也未安装其旧内核驱动。运行库搜索路径仅在启动脚本内生效。SDK 的旧安装说明列出的内核范围不含当前 WSL 6.6，所以以实际采集结果为准。

编译：

```bash
bash /mnt/e/chatgpt_project/mid360s_mapping/camera/build.sh
```

用户已授权安装 `/etc/udev/rules.d/99-zm-camera.rules`，只匹配此序列号，将设备 OWNER 设置为 leon、MODE=0660。恢复权限时移走该规则、重载 udev 并重新插拔此相机；不用修改其他 USB 设备。

切回 Windows：先退出本程序，使用 `usbipd list` 确认相机当前 BUSID，再运行 `usbipd detach --busid <相机BUSID>`。BUSID 可能随接口变化，不能将雷达网卡误作相机。
