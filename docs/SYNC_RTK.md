# 原路线与 RTK 预设

状态：接口设计预留；尚无雷达同步验收结果、RTK 设备或 GNSS 锁定结果。

## 保留的原项目路线

STM32 PB5 → 雷达 PPS；STM32 PA9 USART1 TX → USB 转 TTL → 电脑；电脑解析每个 PPS 对应的 GPRMC 秒值，再经以太网命令送给雷达。相机仍由 STM32 PA1 输出触发。

用户确认的非原厂雷达线：黄 Pin8 接 PB5；黑 Pin2/3 接 GND；白 Pin10 GPS 输入、绿 Pin11、红 Pin12 均不接并单独绝缘。红线不是电源正极。这份颜色表只适用于该线束。

STM32 电平为 3.3 V。USB 转 TTL 的具体设备、串口号及电平需在实测时确认，不能以 ST-LINK 替代串口通道。

原 LIV_handhold 的串口转发存在于旧 Livox ROS1 驱动；当前 ROS2 + SDK2 尚未移植该桥接。SDK2 的 SetLivoxLidarRmcSyncTime 是后续适配点。只接 PPS 或只编译程序不代表同步完成。现有 camera-pulse-test 仅输出 PA1 相机测试脉冲，不输出雷达 PPS/RMC。

未采用的 lidar-sync-test 直连实验只有不完整工程骨架，未生成固件、未烧录，本归档不把它作为可运行成果。

## RTK 两条独立数据路径

1. **时间**：后续 GNSS 有效 UTC + PPS 替代测试时间源；保留电脑向雷达发秒值的路线。必须标明秒值对应哪个 PPS、接收延迟和有效状态。时间有效与 RTK Fixed 是不同状态。
2. **定位**：GNSS 位置、协方差、解状态独立送入融合后端；预留天线至雷达的杆臂、坐标系和时间延迟标定。不得把未知杆臂当已标定零值，也不得把未知协方差当零误差。

配置模板所有入口默认 disabled/null；它是规划契约，尚无读取它的运行节点。无 GNSS 时不得伪装 UTC 有效；失锁或切换时间源应报告并分段重启验证，不在建图过程中悄悄改时间轴。

## 分阶段验收

先确认 STM32 PPS 与每秒 RMC 的配对和连续性，再验证电脑转发与雷达反馈/时间戳，最后接相机验证触发计数与帧号对应。单独运行驱动完成同步检查后才接建图；切换时间源时不运行已验证的 FAST-LIO 流程。

RTK 阶段先验证有效 UTC/PPS，再验证定位质量、杆臂与后端接口。FAST-LIVO2-RTK 参考项目当前采用 ROS1，不能直接当作 Humble 包加载；其中标定参数不适用于本机。

参考：
- https://github.com/xuankuzcr/LIV_handhold
- https://github.com/xuankuzcr/FAST-LIVO2-RTK
- https://github.com/Livox-SDK/Livox-SDK2
