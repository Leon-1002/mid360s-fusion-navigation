# 恢复与使用

此仓库是现有成果的独立快照，不覆盖原现场目录。历史脚本含本机路径、相机序列号、用户名和网卡地址，需要按实际部署修改。

## 雷达源码

在 WSL Ubuntu 22.04、ROS2 Humble 环境中，把 `wsl/mid360s_lio` 复制到一个**新的**工作目录。源码内已经包含本地修改，不要再重复应用 provenance 的补丁。

原入口默认 `$HOME/mid360s_lio`，若该目录已存在，保留它，在新目录完成独立构建后再适配入口。安装 ROS2、colcon、Eigen、PCL、OpenCV 等上游声明依赖。SDK2 可用 `cmake -S sdk -B sdk-build -DCMAKE_INSTALL_PREFIX="$PWD/sdk-install"` 配置，再用 `cmake --build sdk-build -j2` 构建。确认生成的 SDK 动态库后参考 `mid360s_mapping/build-local.sh` 构建 ROS2 包；该脚本固定切到原工作目录，不能未经调整拿来构建新目录。

Windows `.cmd` 和相机启动脚本仍保留 `E:\chatgpt_project\mid360s_mapping` 部署位置。克隆到其他路径时先调整入口。不要从归档直接启动去控制现有采集会话。

## 相机

厂家 SDK 安装包不随仓库分发。版本、下载地址和 SHA256 在 `mid360s_mapping/camera/README.md` 中；展开到 `camera/vendor/extracted`，使 include 和 lib/m64x86 位于该目录，再使用 build.sh。运行库软链接由 build.sh 生成。不要启用已撤回的 Fast DDS 实验配置或强制 USB 绑定。

## STM32

打开 `mid360s_mapping/stm32/camera-pulse-test/camera-pulse-test.uvprojx`，使用 Keil ARM Compiler 5 构建；本机编译器路径写在工程中，其他电脑需调整。这是 PA1 单轮十脉冲测试，不是 PPS + 串口同步固件。当前归档未进行烧录或新硬件验证。

## 许可与边界

第三方源码保留其原许可与版权声明，不对全部内容另行套用统一许可证。上游来源见 provenance/upstreams.json；STM32 库来自已下载的 LIV_handhold 工程。SDK 安装包、完整原始采集数据、个人照片、调试器界面状态、凭据均不纳入。
