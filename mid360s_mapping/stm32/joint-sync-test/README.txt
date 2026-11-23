联合硬件触发台架固件（JOINT_V1，合成时间，不是真实 UTC）

沿用原项目路线：PB5 -> 雷达 PPS；PA9 -> USB-TTL RXD -> 电脑以太网秒值转发。
PA1 -> 相机 Line2（新线 3 脚棕）；相机 6 脚细黑 -> STM32 GND。
雷达黄 Pin8 -> PB5，黑 Pin2/3 -> GND；雷达 GPS 串口白线保持不接。
相机 USB 供电，其他未使用线保持绝缘。

PB5：TIM3 CH2，1 Hz，100 ms 高电平，OC2REF 同时作为 TIM3 TRGO。
PA1：TIM2 CH2，5 Hz，10 ms 高电平。TIM2 ITR2 接 TIM3 TRGO，使用硬件 Trigger 模式。
两定时器采用同一 APB1 时钟和 10 kHz 计数基准；TIM2 在下一个 PPS 上升沿启动。
相机第一个触发位于该 PPS +190 ms，此后每 200 ms 一次，300 次后在下降沿停止。
此相位是定时器设计值，尚无示波器或相机曝光输出的外部测量。
PA1 上电保持低；电脑通过 ST-LINK 写 camera_request 触发批次，无需按 RESET。
再次测试可重新 arm；不能在校时中重启 STM32，因为合成时间会回到起点。

源码继承 lidar-pps-uart 的 RMC 日历与故障保护。发生漏 PPS 时两路脉冲均停止。
camera_state: 0 空闲、1 等待 PPS、2 批次运行、3 已结束。
camera_pulses 在相机脉冲下降沿计数；camera_epoch 为启动 PPS 的合成秒值。
主机必须先核对 Flash 与当前构建完全一致，再按 map 符号写 RAM 请求，防止旧固件误写。

构建：PowerShell 执行 build.ps1 -CompilerDirectory E:\Keil5\Core\ARM\AC5\bin
产物：build\joint-sync-test.hex / .axf / .map / .bin
Keil 工程：joint-sync-test.uvprojx（STM32F103C8，64 KB Flash / 20 KB RAM）。
本次下载使用 Keil 并已 Verify OK；主机另做完整镜像读回比对。
更换固件前备份在 ../before-joint-20261123-174902/flash-64k.bin。
原 radar-only 和 camera-pulse-test 工程均保留，可按原流程回退。

联合测试入口：../../sync-test/start-joint.ps1
前置：关闭 MV Viewer / Livox Viewer / ROS 雷达采集；相机留 Windows；COM8 和 ST-LINK 接通。
换固件导致合成纪元重置后，先给雷达断电重启，再开始新的测试。
不要在测试运行时按 RESET、开 Viewer 或拔插硬件。
程序先保存相机设置，确认无脉冲时不出帧，再启动雷达同步；雷达稳定后自动发送300脉冲。
结束后核对帧数、帧号、格式、设备时间戳递增、主机观察帧率及雷达稳定时戳。
相机临时参数与雷达临时网络配置均还原，错误保留在会话报告。

预计输出 frame-trigger-correspondence.jsonl 仅在整批验收通过后生成；其中时间为定时器
计划对应值，不是相机内部时间戳已变为 UTC 的证明，不能直接替代 ROS header.stamp。
恢复原无同步建图前先结束台架程序，并按原步骤重启雷达以退出合成时间。

参考：STM32 RM0008 第15章，TIM2 ITR2 = TIM3 TRGO；原作 LIV_handhold 的 PPS/RMC 路线。
