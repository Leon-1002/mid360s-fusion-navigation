# 相机 PA1 脉冲测试

目标芯片为 STM32F103C8T6，Flash 限定 64 KB，RAM 限定 20 KB。

每次复位在 PA1 输出一组 10 个脉冲，频率 1 Hz，高电平持续 10 ms。首个上升沿约在复位并完成初始化后的 990 ms 出现，第 10 个脉冲结束后 PA1 保持低电平。再次按 RESET 开始新一组。计数变量 `completed_pulses` 表示已结束的脉冲数，`test_complete` 为 1 时表示本轮结束。

PA1 对应板上 A1。相机线色采用用户提供的非原厂线标签，白线为 2 脚 Line1，蓝线为 5 脚 ISO_GND。拟测试连接为白线到 A1，蓝线到 GND。相机由 USB 供电，其他线端分别绝缘。连接前断电，启动采集并配置好相机后再按 STM32 RESET 开始计数。

相机需要设置 FrameStart、TriggerMode On、TriggerSource Line1、上升沿触发、连续采集模式。保留曝光 30 ms、增益 2.0 和 3072×2048 分辨率。应收到与本轮对应的 10 帧，保存帧号和接收计数进行验收。实际枚举名称以 SDK 查询结果为准。

GPIO 直连方案尚需验证相机的实际电气兼容性与收帧结果。编译通过仅证明固件能够生成，波形、帧计数及硬同步均需实机验证。

2026-11-20 调试修正：最初版本在空闲循环中使用 WFI，且没有配置睡眠调试支持。现场可读取 SWD 端口 ID，但内部寄存器、RAM 和 Flash 均报访问错误。依据 STM32F1 对睡眠调试的要求，将测试程序改为 NOP 空闲循环，便于保持 SWD 可访问。该因素与当前现象相符，修正后的硬件连接恢复仍需上板验证。修改前的源码与 Keil 构建产物保存在 before-idle-fix 日期目录。

2026-11-20 11:39 实机读取：用户通过 BOOT0=1 恢复烧录并写入修正版，随后断电将 BOOT0 恢复为 0 再上电。ST-LINK 读取内部寄存器、RAM 和 Flash 全部成功，6140 字节 Flash 与 Keil HEX 一致。completed_pulses=10、test_complete=1，TIM2 已停止，PA1 配置为推挽低电平。芯片 Flash 容量寄存器为 64 KB，厂商检查值为 0x20，符合当前设备包检查值。原始记录见 chip-read-20261120-113932.json。此结果验证程序完成计数及调试访问恢复，实际输出波形和相机十帧接收仍需验证。

## 编译

Keil 用户可直接打开本目录的 `camera-pulse-test.uvprojx`，按 F7 编译。目标为 STM32F103C8，使用本机 ARM Compiler 5。该工程已通过本机 µVision 实际构建，结果为 0 Error(s)、0 Warning(s)，产物在 `build-keil`。在 Options for Target 的 Debug 页选择 ST-Link Debugger，在 Settings 中选择 SW 接口，再在 Utilities 页确认使用调试驱动进行 Flash 下载。Flash Download 中启用 Program 和 Verify，使用对应 STM32F103C8 的 Flash 算法。烧录按钮位于 Flash → Download。

在 PowerShell 中执行本目录的 `build.ps1`。默认使用本机已有的 `E:/Keil5/Core/ARM/AC5/bin64`，可通过 `-CompilerDirectory` 指定其他 ARM Compiler 5 路径。输出位于 `build` 目录，HEX 包含 Flash 地址，BIN 的起始烧录地址为 `0x08000000`。

烧录会覆盖芯片中现有固件。烧录前应读出并保存现有 Flash，确认工具没有执行读保护解除或整片擦除等额外操作。固件上电即运行，应在烧录和准备阶段将相机触发线断开。

## 来源

沿用 LIV_handhold 的 TIM2_CH2 / PA1 复用推挽输出方式。vendor 中的 STM32 标准外设库、CMSIS 头文件、启动文件和时钟初始化文件复制自本机已经下载的 LIV_handhold 工程，保留原文件及许可声明。启动文件沿用原项目的 hd 版本，其 TIM2 向量位置适用于本测试使用的 C8 芯片，链接内存范围按 C8 限制。

https://github.com/xuankuzcr/LIV_handhold

新增 main.c 使用有限脉冲计数，并根据实际 APB1 时钟计算定时器分频。系统初始化沿用原工程的 8 MHz 外部晶振 / 72 MHz 配置，晶振启动失败时使用库保留的内部时钟，频率精度随时钟源变化。
