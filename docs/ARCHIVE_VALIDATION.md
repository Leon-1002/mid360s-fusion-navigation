# 归档验证 — 2026-11-23

本次针对独立归档副本完成的检查：

- Python 文件语法检查通过。
- PowerShell 文件语法检查通过。
- 项目 Bash 脚本 `bash -n` 检查通过。
- 从归档中的 Livox 驱动源码提取时钟类运行回归测试：两次已观察到的回拨及墙钟前跳一小时，PASS。
- 从归档中的 FAST-LIO 源码提取时间保护逻辑运行回归测试：启动间隔、正常流、过大时间间隔、回拨和故障锁存，PASS。
- 两份完整本地补丁对归档源码执行 `git apply --reverse --check`，均通过，证明补丁与快照一致；没有实际撤销修改。
- 归档内 STM32 `camera-pulse-test/build.ps1` 实际编译成功，输出 `build/camera-pulse-test.hex`；生成物按 .gitignore 排除。
- 对待归档文件检查常见 GitHub token、私钥和 AWS access key 格式，未发现匹配。此项是有限模式检查，不代表形式化安全审计。
- SHA256 文件清单见 `provenance/SHA256SUMS.json`；清单不包含它自身及 Git 元数据、构建输出。

本次未执行：全新环境完整 ROS2 编译部署、雷达或相机采集、STM32 烧录、硬件同步、标定、视觉融合、RTK 定位。此前实机结果来自保留的历史报告及测试统计，未重新进行实机测试。

保护措施：在独立目录整理副本；原 Windows 项目、WSL 工作区和硬件状态均未改动。没有打开 rosbag 数据库，没有上传 SDK 安装包或现场图像。GitHub 仓库默认私有。
