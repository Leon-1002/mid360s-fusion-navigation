# Mid-360S 融合导航工程

**2026-11-24 · Orin 手持建图**　[启动、录制、停止、保存和生成彩色地图](mid360s_mapping/onboard/Orin手持建图使用说明.md) · [移植 README](mid360s_mapping/onboard/README.md) · [在线查看实测房间地图](https://mid360s-room-y58xd2.xiaomingji1002.chatgpt.site)

截至 2026-11-23 的阶段成果归档。设备为 Livox Mid-360S、ZM-3000-60UC 和 STM32F103C8T6；Windows + WSL2 Ubuntu 22.04 + ROS 2 Humble。

## 已验证和待完成

| 项目 | 状态与边界 |
|---|---|
| 雷达 + IMU FAST-LIO | 2026-11-19 约一米往返实测；首尾估计位置差 2.51 cm；时间戳回退 0；地图 317651 个有限坐标点。不是外部真值精度认证。 |
| 无同步时钟修复 | 实际驱动源码采用共同锚定的单调时间；GPS/PTP 分支保留。 |
| 相机 USB / 预览 | 已出图；沿用 30 ms、增益 2.0、3072×2048、目标 5 FPS。 |
| 原始图像 ROS 传输 | 未达标：一次 15 秒并行订阅 JPEG 约 5.02 Hz，image_raw 约 0.68 Hz。 |
| STM32 相机测试固件 | 联合固件已构建、烧录、镜像读回核对；PA1 5 Hz 固定 300 脉冲与相机 300 帧对应。 |
| 相机硬触发 | 实测 Line2：300 脉冲 / 300 连续帧，约 5.0015 FPS，无坏帧或时戳回退。新线 3 棕接 PA1，6 黑接 GND。 |
| 雷达 PPS / 秒值同步 | 联合实测 75 秒，73 次校时确认；稳定窗口 69.328 秒两路时戳正常。点云 CRC 字段零，完整性未验；合成时间不是真实 UTC。 |
| 标定 / 视觉融合 / RTK / 自主导航 | 尚未完成；RTK 当前未接入。 |

## 项目专用标定板（2026-11-23）

[打印 A4 ChArUco PDF](mid360s_mapping/calibration/charuco/output/pdf/mid360s-charuco-5x7-30mm-A4-v1.pdf) · [参数、打印及复刻说明](mid360s_mapping/calibration/charuco/README.md)

5×7 个棋盘格，格长 30 mm，标记外框 21 mm，字典 DICT_4X4_50。提供横纵 100 mm 校验线、参数 JSON、矢量 PDF、生成脚本和检测报告；实际 PDF 渲染检测通过 17 个标记和 24 个角点。打印使用 A4、实际大小 100%，并实测两条校验线。此交付是相机内参标定工具，不表示内参、外参或视觉融合已完成。

## 目录

- `mid360s_mapping/`：现用启动、采集、检查脚本，相机源代码，STM32 相机脉冲工程，历史报告。
- `wsl/mid360s_lio/`：实际工作区的受版本控制源码快照；包含当前本地修改和 ikd-Tree 子模块。保留第三方许可；省略 FAST-LIO 的论文及演示媒体、运行输出。
- `provenance/`：上游地址、精确提交、本地 diff 和文件校验信息。
- `evidence/`：已完成测试的统计文件、STM32 读回记录及示例地图。未打包原始 rosbag、现场照片或 SDK 安装包。
- `docs/`：恢复方法及后续同步、RTK 接口规划。

**本 README 与 docs 中的现状说明优先于历史说明。** 历史相机 README 中 Line1 接法是当时尝试；不是现已验证的硬触发方案。`-HardwareTrigger` 启动脚本现默认 Line2，并显式配置输入模式。`fastdds-camera.xml` 是已撤回的实验，勿启用作为恢复步骤。

当前归档未宣称全新环境一键部署成功。见 [恢复说明](docs/RESTORE.md) 和 [同步与 RTK 预设](docs/SYNC_RTK.md)。原雷达建图源码保持原状；相机修改前已做本地备份。

## 2026-11-23 联合台架实测

结果为 `JOINT_TIMING_PASS_CRC_UNAVAILABLE`。同一 STM32 同时输出相机触发、雷达 PPS 和 RMC，电脑按原路线转发秒值。相机完成 300 脉冲 / 300 帧，雷达同期稳定。相机及雷达临时设置恢复成功。

详见 [验收记录](mid360s_mapping/sync-test/联合硬件触发验收-20261123.txt)、[实测统计](evidence/sync/joint-20261123-175440/summary.json) 和 [固件说明](mid360s_mapping/stm32/joint-sync-test/README.txt)。固件产物位于 `artifacts/joint-sync-test/`。

相机采集使用 Windows 原生 SDK；不代表 ROS image_raw 接收率达标。触发对应表为合成定时器计划值，实际曝光相位未外部测量，ROS 时间戳尚未统一，RTK/视觉融合未完成。首次校时过渡异常保留在完整统计中，稳定采集窗口单列。

## Orin ARM64 移植分支（2026-11-23）

修改前 x86 版本固定在 `camera-x86-baseline-20261123` 标签；Release 附有原始 x86 SDK ZIP。
本分支 `codex/orin-arm64` 增加按架构选库及 ELF 检查；x86/ARM64 两端均通过原生构建、SDK 加载和 ROS 节点初始化。实际 Orin 为 JetPack 6.2.2 / Ubuntu 22.04.5，雷达 SDK、ROS 驱动和 FAST-LIO 也已编译成功。

机载相机实机采集已验证：两次40秒各200帧，SDK无帧号缺口/超时。稳定段ROS raw约4.926Hz，同区间SDK/JPEG151帧、raw149帧；原始图像无丢帧验收失败，证据保留。雷达网络和机载同步/建图尚待验收。

**复刻入口：[Jetson AGX Orin移植README](mid360s_mapping/onboard/README.md)**，包括环境、源码标签、SDK获取与SHA256、隔离目录、编译、USB权限、收帧和ROS接收计数验收、雷达构建、故障处理及回退。
另见 [移植记录](mid360s_mapping/onboard/移植进度-20261123.txt)、[实测证据](evidence/orin-20261123/) 和 [相机说明](mid360s_mapping/camera/README.md)。原 x86 主分支及基线标签保留。
