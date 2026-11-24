# Jetson AGX Orin 移植与复刻指南

更新：2026-11-23。本文记录已经执行的步骤、复刻命令和仍未完成的验收。
适用设备是 **Jetson AGX Orin Developer Kit**，不是之前讨论的 RK3588。
命令块除特别说明外均在 **Orin 的 Bash 终端**执行，不带终端提示符。

维护约定：本 README 随项目持续更新到项目结束。每阶段同步实际步骤、验证结果、失败记录与下一步；以机载运行和手持建图为当前主线，已知相机ROS丢帧不阻塞雷达建图启动。

## 1. 当前交付与验收边界

| 项目 | 当前结果 |
|---|---|
| 原 x86 相机版本 | 已固定标签和上传原始 SDK Release，保留原 Windows/WSL 流程 |
| ARM64 相机 | 原生编译、SDK 加载、ROS 节点初始化及实机采集已通过 |
| 采集参数 | 3072×2048 BayerRG8，曝光 30000 µs，增益 2.0，目标 5 FPS |
| 原始图像 ROS 接收 | 稳定段约 4.926 Hz；同一时间范围 SDK/JPEG 151 帧、raw 149 帧，仍少 2 帧 |
| JPEG ROS 接收 | 稳定段约 4.993 Hz，151 帧 |
| Livox SDK2、雷达 ROS 驱动、FAST-LIO | 已在 Orin 实机运行，点云/位姿约10Hz、IMU约194Hz |
| 相机与雷达联合运行 | 相机SDK持续约5FPS；联合负载下raw订阅约3.64Hz，尚未达目标接收率 |
| 手持建图 | 用户约20厘米往返；保存822824个有限坐标点的PCD，RViz已显示 |
| 硬同步 | Windows 台架此前通过；机载端串口桥、脉冲批次控制和联合验收未完成 |
| 图像时间戳 | 仍是主机收帧时间，尚未统一到雷达/触发时基 |
| RTK | 尚未接入，现有台架时钟是合成时间，不是真实 UTC |

**能够出图、接收速率接近目标、无丢帧、时间同步是四个不同的验收项。**
目前不能把机载端迁移称为全部完成。旧 Windows 台架结果也不能替代本机验收。

## 2. 已验证的环境

- Ubuntu 22.04.5 LTS / aarch64。
- JetPack 6.2.2 / L4T 36.5.0 / 内核 5.15.185-tegra。
- ROS 2 Humble，已有 colcon、Eigen 3.4、PCL 1.12、OpenCV 4.8 和 Python 3 开发环境。
- 登录用户 `door`，测试时 Wi-Fi 地址 `192.168.2.127`，SSH 端口 22。
- 原生 USB 3.0，实测相机链路 5000M；不使用 Windows usbipd。
- 当前独立部署目录 `/home/door/mid360s_orin_20261123`。
- 相机 ZM-3000-60UC，序列号 `DD07657AAK00023`，USB VID:PID `2e03:0001`。

本次复用了已有依赖，没有执行 apt 升级、JetPack 升级、系统重装或厂商旧内核驱动安装。
新的空白系统必须先准备 Humble 与依赖；本文的本机验证不等于验证过从零刷机。
检查所需依赖：

```bash
uname -m
cat /proc/device-tree/model
lsb_release -ds
test -r /opt/ros/humble/setup.bash
dpkg-query -W build-essential cmake python3-dev python3-colcon-common-extensions libeigen3-dev libpcl-dev libopencv-dev ros-humble-rclcpp ros-humble-sensor-msgs ros-humble-pcl-ros ros-humble-pcl-conversions
```

若缺依赖，应先查明本机 ROS 软件源及 JetPack 的 OpenCV 来源，再补缺项。不要为匹配本文版本而覆盖板卡原有 CUDA/OpenCV。

## 3. 版本与源文件获取

仓库是私有仓库，下一位操作者需要自己的仓库读取权限；不要复制本机私钥给其他人。

- 仓库：<https://github.com/Leon-1002/mid360s-fusion-navigation>
- 移植分支：`codex/orin-arm64`。
- x86 固定基线：`camera-x86-baseline-20261123`，原提交 `65ebf6f8aaaf14b351047c8bb5d4494ef454cca4`。
- ARM64 本阶段快照：`camera-arm64-port-20261123`。
- Orin 手持建图文档维护在 `codex/orin-arm64`。11 月 24 日的操作说明面向已经部署好的 Orin 和项目 Windows 工作区；从本分支新克隆的目录尚缺部分实机启动脚本和处理工具。
- x86 SDK Release：<https://github.com/Leon-1002/mid360s-fusion-navigation/releases/tag/camera-x86-baseline-20261123>
- ARM64 SDK Release：<https://github.com/Leon-1002/mid360s-fusion-navigation/releases/tag/camera-arm64-port-20261123>

获得仓库权限后，在 Orin 下载分支并固定到上述 ARM64 标签。若用浏览器下载源码 ZIP，也须选择同一标签。

```bash
git clone --branch codex/orin-arm64 https://github.com/Leon-1002/mid360s-fusion-navigation.git "$HOME/mid360s-fusion-navigation"
cd "$HOME/mid360s-fusion-navigation"
git checkout codex/orin-arm64
git rev-parse HEAD
```

源码布局：

```text
mid360s_mapping/camera/       相机 C++ 节点、架构选择、构建、运行、自检脚本
mid360s_mapping/onboard/      本 README、机载预检与雷达构建脚本
wsl/mid360s_lio/sdk/          已验证版本的 Livox SDK2 源码
wsl/mid360s_lio/src/          雷达驱动与 FAST-LIO 源码，包含 ikd-Tree
evidence/orin-20261123/       本次构建及采集验收记录
provenance/SHA256SUMS.json    文件哈希清单
```

大 SDK ZIP 放在 Release 附件，不在 Git 源码树内；编译产物和私钥也不在仓库内。

## 4. 建立隔离目录

以下命令只适用于**尚不存在的新目录**；现有 Orin 已部署过，不要重复覆盖。复刻时可以更换 `DEPLOY` 名称。

```bash
REPO="$HOME/mid360s-fusion-navigation"
DEPLOY="$HOME/mid360s_orin_20261123"
test ! -e "$DEPLOY" || { echo '目录已存在，请保留并换一个新部署目录'; exit 1; }
mkdir -p "$DEPLOY/workspace"
cp -a "$REPO/mid360s_mapping/camera" "$DEPLOY/camera"
cp -a "$REPO/wsl/mid360s_lio/sdk" "$DEPLOY/workspace/sdk"
cp -a "$REPO/wsl/mid360s_lio/src" "$DEPLOY/workspace/src"
cp "$REPO/mid360s_mapping/onboard/build-lidar.sh" "$DEPLOY/"
cp "$REPO/mid360s_mapping/onboard/preflight.sh" "$DEPLOY/"
cp "$REPO/mid360s_mapping/onboard/"*.py "$DEPLOY/"
cp "$REPO/mid360s_mapping/onboard/"*.sh "$DEPLOY/"
cp "$REPO/mid360s_mapping/onboard/MID360s_config.json" "$DEPLOY/"
mkdir -p "$DEPLOY/sync-test"
cp "$REPO/mid360s_mapping/sync-test/run_sync.py" "$REPO/mid360s_mapping/sync-test/livox_wire.py" "$DEPLOY/sync-test/"
```

归档保留了 Windows 文本换行。只规范化新部署副本中的 Shell 文件，避免 Bash 把 `\r` 当命令字符：

```bash
python3 - "$DEPLOY" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1])
for path in list(root.glob('*.sh')) + list((root / 'camera').glob('*.sh')):
    data = path.read_bytes()
    path.write_bytes(data.replace(b'\r\n', b'\n'))
PY
bash "$DEPLOY/preflight.sh" > "$DEPLOY/preflight-before.txt"
```

`deploy-camera.sh`、`deploy-lidar.sh` 是本次指定路径的辅助脚本，包含固定部署路径和拒绝覆盖检查。
需要自定义路径时按本文显式步骤操作；不要直接修改旧工作区来适配。

## 5. ARM64 相机 SDK：下载、校验、解压

从 ARM64 Release 下载附件并保存到 `$DEPLOY/camera/vendor/packages/`：

`MVviewer_Ver2.3.2_Linux_arm_aarch64_Build20220402.zip`

厂商原始下载地址：
<http://download.huaraytech.com/pub/sdk/Ver2.3.2/Linux/Arm/MVviewer_Ver2.3.2_Linux_arm_aarch64_Build20220402.zip>

厂商目录的 `Arm` 大小写不能改；本次原站通过 HTTP 下载，优先使用已归档 Release 并比对下方 SHA256。

```bash
cd "$DEPLOY/camera"
mkdir -p vendor/packages
printf '%s\n' 'e48e52802d65fdf8d1f67c2e0077bcf106eab2beaccf824db7dd369bbfc4d955  vendor/packages/MVviewer_Ver2.3.2_Linux_arm_aarch64_Build20220402.zip' | sha256sum -c -
python3 -m zipfile -e vendor/packages/MVviewer_Ver2.3.2_Linux_arm_aarch64_Build20220402.zip vendor/packages
test ! -e vendor/arm64/extracted || { echo 'SDK已存在，停止覆盖'; exit 1; }
sh vendor/packages/MVviewer_Ver2.3.2_Linux_arm_aarch64_Build20220402.run --noexec --nox11 --nochown --target "$PWD/vendor/arm64/extracted"
file vendor/arm64/extracted/lib/Jetson_TX1/libMVSDK.so.2.1.0.194984
```

`file` 必须显示 ARM aarch64 / ELF64。包内目录名虽然是 `Jetson_TX1`，实际使用的是经 Orin 验证的 ARM64 用户态库。
SDK 包针对较旧 L4T；本次**只解压**，不运行包内 `install.sh`，不安装旧内核 USB 驱动，也不替换 `/opt/MVS` 等已有 SDK。

架构选择由 `sdk-env.sh` 完成：x86 使用 `vendor/extracted/lib/m64x86`，ARM64 使用 `vendor/arm64/extracted/lib/Jetson_TX1`。
库必须经过 ELF 架构检查；不能把 x86 `.so` 复制到 ARM64 目录冒充移植。`LD_LIBRARY_PATH` 仅影响当前启动进程。

## 6. 相机编译与无设备自检

```bash
cd "$DEPLOY/camera"
set -o pipefail
bash build.sh 2>&1 | tee build-aarch64.log
bash check-runtime.sh
```

预期：生成 `build-aarch64/zm_camera`；SDK 版本 `V2.3.2.194984`；输出 `Runtime check PASS`。
`check-runtime.sh` 检查动态库并创建 ROS 节点后退出，不打开相机。
生成的 `loader-aarch64-*.txt` 与 `ros-runtime-aarch64.txt` 要保留。
不能用 `--ros-args --help` 替代本节点的自检参数；该参数组合此前造成过异常退出。

## 7. USB 连接与权限

关闭占用相机的 MV Viewer，把 USB 接至 Orin USB 3.0 端口。无需 usbipd、强制绑定或重装 USB 驱动。

```bash
lsusb -d 2e03:0001
lsusb -t
```

本次显示 `Bus 002 Device 003`，链路 `5000M`。**总线号与设备号会随插拔变化**，不要永远写死 `002/003`。
按本次枚举结果检查并临时授权：

```bash
ls -l /dev/bus/usb/002/003
sudo setfacl -m "u:$(id -un):rw" /dev/bus/usb/002/003
getfacl /dev/bus/usb/002/003
```

本次只有 root 可写时，SDK 报 `USB cameras=0`；上述临时 ACL 由操作者执行后可识别正确序列号并采集。
这项权限在拔插后消失。若 `setfacl` 不存在，需要先安装 Ubuntu 的 `acl` 工具。

可选的长期配置（**尚未在本次机器安装/验证**）：管理员确认后添加仅匹配该相机序列号的 udev 规则；示例用户组为 `door`，其他用户须替换。
安装前备份已有同名文件，不覆盖未知内容。

```text
SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", ATTR{idVendor}=="2e03", ATTR{idProduct}=="0001", ATTR{serial}=="DD07657AAK00023", GROUP="door", MODE="0660"
```

可保存为 `/etc/udev/rules.d/99-mid360s-zm-camera.rules`，执行 `sudo udevadm control --reload-rules` 后在停采状态重新插拔，再检查实际权限。
不要给所有 USB 设备设置 `0666`。本次只使用临时 ACL，没有修改系统 udev 规则。

## 8. 独立相机采集与 ROS 接收验收

此阶段使用自由运行，只验证 USB/SDK/ROS 链路；六芯触发线可以保持连接。不要在此阶段重置 STM32 或改雷达时钟。

先在终端 A 启动接收检查：

```bash
DEPLOY="$HOME/mid360s_orin_20261123"
source /opt/ros/humble/setup.bash
cd "$DEPLOY/camera"
python3 check_camera_delivery.py
```

立即在终端 B 启动 40 秒采集：

```bash
DEPLOY="$HOME/mid360s_orin_20261123"
bash "$DEPLOY/camera/run-camera.sh" --ros-args -p preview:=false -p seconds:=40.0 -p fps:=5.0 -p exposure_us:=30000.0 -p gain:=2.0 -p hardware_trigger:=false
```

两个终端须使用相同 `ROS_DOMAIN_ID` 与 RMW 配置。默认本机 ROS 环境即可，本次没有启用实验性 Fast DDS XML。
本节点不自动设置 ROI/PixelFormat；先核实已有相机设置为 3072×2048 BayerRG8，接收检查也会拒绝其他格式。
本次已有设置满足要求，没有改分辨率、缩短曝光或提高增益。

`check_camera_delivery.py` 预热 3 秒后并行订阅 raw/JPEG 30 秒，最长等待 50 秒；验证每帧尺寸、长度、时间戳及接收速率，写入 `camera-delivery.json`。
其 `RATE_PASS` 只代表接收速率在 4.8–5.2 Hz 容差内，不代表无丢帧；`lossless_delivery_verified` 保持 false。
早期证据文件结果为 `PASS`，其含义同样只限当时速率检查，不能当作无丢帧合格。

采集日志位置由脚本打印：

```text
camera/capture-日期-时间-随机字符/
  console.log          SDK采集统计、帧号缺口、超时
  settings-before.txt  采集前设置快照
  frames.csv           SDK帧号、设备ticks、主机收帧时间、尺寸
  snapshot.png         第10帧预览快照
```

正常退出会尝试恢复临时相机参数；异常断电不能保证恢复，须用快照核对。`/tmp/zm-camera-用户ID.lock` 防止本启动脚本重复占用相机。
SSH 无桌面环境使用 `preview:=false`，不强行启动 GUI。

本次稳定段：raw 与 JPEG 的首末 `header.stamp` 相同，SDK CSV 该闭区间有 151 帧；JPEG 收到151，raw收到149。
raw 约4.926Hz，最大接收间隔约0.401秒；时间戳无回退、无坏尺寸/长度。SDK整次采集帧号无缺口、无超时。
因此：**ARM64 实机采集成功，但 raw ROS 无丢帧验收尚未通过**。原 WSL 0.68Hz 的记录不能替代本次数据，也不能据此宣称已全部解决。
启动时观察到 `sequence size exceeds remaining buffer`，仍保留日志，尚未确定原因；没有证据证明它一定导致缺失的2帧。

相同统计区间的帧数核对可复刻为：

```bash
cd "$DEPLOY/camera"
python3 audit_camera_delivery.py camera-delivery.json capture-20261123-200833-K6BU/frames.csv camera-delivery-count-audit.json
```

把 `capture-...` 换成自己本轮采集目录。检查器按接收报告的首末主机时间戳在 SDK CSV 中计数；本次实际结果 `COUNT_FAIL`、退出码1，raw缺2、JPEG缺0。该失败必须保留，不能只引用速率检查的成功结果。

## 9. 雷达驱动与 FAST-LIO 原生构建

```bash
DEPLOY="$HOME/mid360s_orin_20261123"
set -o pipefail
bash "$DEPLOY/build-lidar.sh" 2>&1 | tee "$DEPLOY/build-lidar.log"
source /opt/ros/humble/setup.bash
source "$DEPLOY/workspace/install/setup.bash"
ros2 pkg executables livox_ros_driver2
ros2 pkg executables fast_lio
```

预期找到 `livox_ros_driver2_node` 与 `fastlio_mapping`。
构建脚本先编 Livox SDK2，再按顺序编驱动和 fast_lio；使用 -j2 限制并行度，显式引用工作区 SDK，包含 ikd-Tree 源码。
它会在缺失时复制驱动的 ROS2 package.xml 和 launch 文件，不覆盖已有文件。
原有 RapidJSON、PCL/Boost 等编译警告保留。`BUILD_TESTING=OFF` 表示此次构建没有运行上游单元测试，不能写成测试套件全部通过。

**到此只构建，不启动雷达。** 下一节是已验证的机载启动入口。旧 WSL 启动器中有 `~/mid360s_lio`、网卡与主机 IP 假设，不能直接拿来运行本部署目录。

## 9.1 Orin 实机网络与一键建图（已验证）

相机USB、雷达网线、USB-TTL接Orin；PPS/相机触发线保持原接法，不重置STM32。
本机有线网口已确认为 `eno1`，Wi-Fi是 `wlP1p1s0`。其他板卡先查接口，不能盲套名称。
首次配置由管理员执行：

```bash
sudo bash "$DEPLOY/setup-lidar-network.sh"
```

脚本保存 `network-before-日期-时间-随机字符/`，创建 `mid360s-orin` NetworkManager连接，地址192.168.1.50/24，不设默认路由，保留旧有线配置与Wi-Fi。
正常应看到 `192.168.1.119 dev eno1 src 192.168.1.50`；默认路由仍经192.168.2.1/Wi-Fi。
同名连接已存在时脚本拒绝覆盖；这时检查 `nmcli connection show mid360s-orin`，不重复创建。回退可激活快照中记录的原有线连接UUID；不删除Wi-Fi配置。

```bash
DEPLOY="$HOME/mid360s_orin_20261123"
bash "$DEPLOY/start-mapping.sh" --check
bash "$DEPLOY/start-mapping.sh" rviz:=true
```

在Orin桌面终端用 `rviz:=true`；SSH无桌面时省略该参数，默认false。默认同时启动雷达驱动、FAST-LIO和相机；`camera:=false` 可单独验证雷达。
使用已通过的0.15米滤波参数、关闭在线雷达IMU外参估计。相机自由运行，30ms/增益2/5FPS；尚未视觉融合或统一图像时间戳。
启动前检查雷达状态，错误状态会拒绝启动；启动前补齐FAST-LIO的 `Log/`、`PCD/` 目录，避免首次复制源码缺空目录导致日志文件打开失败。
每次生成独立 `sessions/mapping-.../`，保存雷达配置、状态、launch.pid和console.log；最新目录写在 `latest-mapping-session.txt`。
联合启动使用 `launch-camera.sh` 直接exec相机节点，让ROS launch的退出信号到达相机；相机图像/帧号/设置仍在camera/capture目录，控制台在建图主日志。

只读运行检查（另开终端）：

```bash
source /opt/ros/humble/setup.bash
source "$DEPLOY/workspace/install/setup.bash"
session=$(cat "$DEPLOY/latest-mapping-session.txt")
python3 "$DEPLOY/check-mapping.py" --seconds 30 --camera --output "$session/pipeline-health.json"
```

这是启动与持续数据检查，不是相机5FPS或硬同步验收。大型点云/图像用原始CDR订阅只计数，避免Python逐点解码拖慢监测线程。首次全解码监测的失败记录仍保留，不把监测线程的低接收率直接当成驱动低速。

## 9.2 手持移动、保存、停止（已完成首次实机保存）

雷达IMU初始化完成、RViz显示点云后，在连接允许范围慢速移动，保持传感器之间的相对安装位置不变。
不要在本阶段启动运动控制、飞控解锁或自主导航。当前用户选择先手持建图，载具以后确定。

```bash
source /opt/ros/humble/setup.bash
python3 "$DEPLOY/capture-path.py"
bash "$DEPLOY/save-map.sh"
```

`capture-path.py` 保存FAST-LIO发布的完整 `/path`，包含订阅前已经发生的移动。`full-path.csv` 与统计保存在本次session。
`save-map.sh` 调用 `/map_save`，检查新PCD文件、点数、二进制长度和所有XYZ是否有限；不只相信服务返回success。再次保存前复制旧map.pcd为带时间戳备份。
保存后的 `map.pcd` 为 `camera_init` 坐标系下的三维点云，不是已完成重定位/规划验证的导航地图。

停止入口（先保存并校验，再向本次launch发送SIGINT）：

```bash
bash "$DEPLOY/stop-mapping.sh"
```

停止脚本核对PID确实属于本目录的launch，不使用全局pkill。停止后检查console.log的退出情况；该封装截至本阶段只完成语法检查，尚未实机执行，不能声称正常退出路径已全部验收。也可先save-map.sh成功，再在建图终端Ctrl+C。

### 2026-11-23 实机结果

- 首次session `mapping-20261123-203031-71ny`：相机有帧、雷达无数据。实际目标IP和端口正确，但雷达work_state=4（SDK定义为Error）。保留诊断码；只给雷达断电重启后恢复work_state=1。
- 首次退出时驱动等待无数据线程未及时结束，ROS launch升级到SIGKILL；相机Bash管道退出也未及时完成。后续改相机为直接exec；仍须继续验收完整停止行为。
- 正常session `mapping-20261123-203424-NqAx`：30秒轻量监测，点云10.002Hz、IMU194.400Hz、位姿10.001Hz、相机raw3.637Hz，均无时间戳回退。相机SDK持续约5FPS、无帧号缺口；联合ROS raw目标速率未通过。
- 首次静止保存444154点；用户报告约20厘米往返后保存822824点、26330619字节，PCD校验通过，旧地图保留。
- 完整Path为265个位姿，估计终点距会话起点0.02270米、估计最大位移0.50525米。用户手动距离约20厘米，没有外部精确真值，不能把2.3厘米当作经标定的测量精度；最大位移与描述的差异也保留。
- 轨迹逐帧记录器启动较晚，因此本轮动作核对使用完整 `/path`，而不是只取后启动的 `trajectory.csv`。
- RViz在Orin桌面启动，OpenGL4.6，截图确认已显示点云。

快照证据保存在本地归档工作区的 `evidence/orin-mapping-20261123/`。地图以 `map-203853.pcd.gz` 压缩归档，数据哈希见同目录的 `map-hashes.txt`。

## 10. 后续机载联合测试：尚未执行的步骤

1. 当前优先继续手持建图、地图保存与更长距离验证；原始图像ROS丢帧作为并行优化项，不再阻塞雷达建图。
2. Orin雷达网络、点云/IMU/位姿及相机并行采集已跑通；后续保持Wi-Fi控制链路独立。
3. 验证连续运行、完整停止与重启；扩大手持范围前先解决供电/线束约束。
4. 补精确标记点往返和更大范围地图质量检查，再按载具决定导航地图格式、重定位和规划接口。
5. USB-TTL已接入Orin，稳定路径 `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`，9600波特率15秒RMC检查通过；当前尚未持续转发秒值。
6. 迁移合成秒值经串口到以太网的时间桥。时间命令与 ROS 驱动可能竞争 UDP 端口，必须统一端口所有权，不同时盲启两个程序。
7. 移植 Windows ST-LINK/pyOCD 脉冲批次控制；核对 MCU 固件与触发批次数。不能照抄旧相机日志里“按 RESET”的提示重置已在同步的 STM32。
8. 明确 MCU 重置后雷达合成时钟的清理流程，再做 PPS/RMC 收敛、无时间戳回退、相机脉冲数与帧数对应及联合建图验收。
9. 最后再实施相机内参、相机与雷达外参、视觉融合及 RTK。当前没有真实 UTC，也未证明实际曝光相位。

当前线路记录（新相机线，勿套用旧线颜色）：Line2针3棕→STM32 PA1；针6细黑→GND；雷达黄PPS→PB5、黑GND→GND；PA9→USB-TTL RXD并共地。雷达GPS串口白线在既定以太网授时方案下不接。
单独相机硬触发启动参数应显式写 `hardware_trigger:=true trigger_source:=Line2`；`expected_frames` 必须与固件实际批次一致。无脉冲时等待是正常现象，不等于 USB 失效。

## 11. 常见故障与回退

| 现象 | 先查什么 |
|---|---|
| lsusb没有相机 | USB连接、供电、实际端口；此时不调曝光/ROS |
| lsusb有相机而SDK cameras=0 | 当前设备节点ACL、其他Viewer占用；不要直接强制绑定 |
| SDK架构检查拒绝加载 | uname -m与.so架构、ZMCAMERA_SDK_ROOT是否指错 |
| 动态库not found | 用check-runtime.sh检查完整ROS+SDK环境，裸ldd可能漏掉ROS环境 |
| 自由运行有帧、Line2无帧 | 触发源/LineMode与脉冲批次；避免在已同步期间按RESET |
| raw比JPEG少帧 | 保存双方时间范围和SDK帧记录，定位ROS链路；不能用JPEG速率代替raw验收 |
| SSH断开 | 先检查Wi-Fi路径，避免因雷达网络配置改掉默认路由 |

回退原则：停止本次部署启动的进程，保留现场日志；使用独立目录或切回固定 x86 标签，不删除原工作区、不 force push。
本次 Windows 相机修改前备份位于 `camera/before-arm64-20261123/`；机载工作区与旧 WSL 工作区分离。
临时 ACL 如需在拔插前撤回，停采后针对当前相机节点执行 `sudo setfacl -x u:door /dev/bus/usb/002/003`；设备号须按当前枚举更新。
本次未改系统 udev、网络、JetPack 或旧 FAST-LIO 源码，回退无需重刷系统。

## 12. 交接时必须保留的证据

保存源码标签/提交、SDK ZIP SHA256、预检记录、构建日志、运行自检、每次采集 console/frames/settings、ROS接收JSON与验收结论。
本次证据在仓库 `evidence/orin-20261123/`。新一轮实机测试另建目录，保留失败记录，不覆盖失败结论。
记录采集模式、设备序列号、测试持续时间和统计口径；标明是单机、联合负载还是硬同步测试。
不要上传SSH私钥、访问令牌、密码；发布到其他仓库前遵守厂商SDK许可。

## 13. 手持全景建图操作

实机采集、停止并保存几何地图、实拍图像上色和浏览器查看的命令见[《Orin 手持建图使用说明》](./Orin手持建图使用说明.md)。[查看 2026-11-24 的房间地图](https://leon-1002.github.io/mid360s-room-map/)。
