# Orin 手持建图使用说明

适用于本项目的 Jetson AGX Orin、Mid-360S 内置 IMU 和 ZM-3000-60UC。本文使用 2026-11-24 房间实测的路线。采集时可以在 Orin 屏幕上同时看相机和雷达，走完后保存全景几何，再用录下的实拍图像给地图上色。

**只想看上一次的地图**，可直接在手机或电脑浏览器打开。拖动旋转，双指缩放或平移，电脑也可使用鼠标滚轮。左上角可以切换“相机真彩”和“全景几何”。[打开实测房间地图](https://mid360s-room-y58xd2.xiaomingji1002.chatgpt.site)

| 想得到的结果 | 使用的文件 | 含义 |
|---|---|---|
| 房间全景几何 | `map.pcd` | FAST-LIO 累积的三维点，包含相机没有看到的区域 |
| 可旋转的真彩地图 | `room-observed-rgb.pcd` | 在上述地图中，为相机看见、且通过可见性筛选的点写入实拍 RGB |
| 本地离线网页 | `room-3d.html` | 浏览器查看版，两种显示模式各最多抽取 17 万个点。完整点数保留在 PCD |

上次实测保存了 796,169 个几何点，其中 407,036 个点取得实拍颜色。公开网页展示这一次保存的快照。每次重新建图都会产生新文件，公开网址不会自动替换内容。

## 1. 打开相机和雷达实时预览

在 **Orin 图形桌面**操作。若已经能看到“Mid-360S 点云与相机实时预览”窗口，而且左右两侧的帧数都在增加，直接进入第 2 步。该窗口负责启动并持有传感器驱动，采集期间请保持打开。另一套旧入口 `start-mapping.sh` 会自行启动驱动，适合单独跑旧版 FAST-LIO 基线；本次彩色流程使用下面的入口。

如果系统刚开机，设备已连接且当前没有其他采集程序占用设备，在 Orin 桌面的终端执行：

```bash
root=/home/door/mid360s_orin_20261123
source /opt/ros/humble/setup.bash
source "$root/workspace/install/setup.bash"
export LD_LIBRARY_PATH="$root/workspace/sdk-build/sdk_core:${LD_LIBRARY_PATH:-}"
python3 -s "$root/sessions/viewer-tools-9xqTte/live_preview.py"
```

左侧应有更新的相机画面，右侧应有雷达点。右侧预览的颜色表示距离。这个实测入口使用 BayerRG8、3072×2048、30 ms、增益 2.0、目标 5 FPS，相机采用自由运行。当前相机曝光与雷达的时间对齐仍待验证。

## 2. 新建一场采集，启动建图和录包

另开一个 **Orin Bash 终端**，桌面终端或以 `door` 登录的 SSH 均可。第 2 至 5 步尽量在这个终端操作。先确认下列三个话题各有一个发布者，`/livox/lidar` 的类型为 `sensor_msgs/msg/PointCloud2`，且没有其他 FAST-LIO 正提供 `/map_save`。

```bash
root=/home/door/mid360s_orin_20261123
ref="$root/sessions/roommap-20261124-y58xD2"
source /opt/ros/humble/setup.bash
source "$root/workspace/install/setup.bash"
ros2 topic info /livox/lidar
ros2 topic info /livox/imu
ros2 topic info /camera/image_raw
ros2 service list | grep -x /map_save
df -h "$root/sessions"
```

这里最后查服务时，空输出表示当前没有同名服务。上次约 147 秒的原始录包占 2.6 GiB，后处理另用了约 1.1 GiB，长时间采集要预留相应空间。

下面复用已验证的建图、录包脚本和转换程序。历史脚本把输出位置写在脚本里，所以先为本次采集生成目录和脚本副本。每次新走一遍只执行一次这段：

```bash
session=$(mktemp -d "$root/sessions/roommap-$(date +%Y%m%d-%H%M%S)-XXXXXX")
unit=$(basename "$session")
printf '本次目录 %s\n服务前缀 %s\n' "$session" "$unit"
ln -s "$ref/adapter" "$session/adapter"
sed "s|^s=\$root/sessions/roommap-20261124-y58xD2$|s=$session|" "$ref/baseline.sh" > "$session/baseline.sh"
sed "s|^cd $ref$|cd $session|" "$ref/record.sh" > "$session/record.sh"
cp "$ref"/{intrinsics.json,extrinsic-candidate.json,mid360_lvi.yaml} "$session/"
grep -Fx "s=$session" "$session/baseline.sh" &&
grep -Fx "cd $session" "$session/record.sh" &&
test -x "$session/adapter/build/adapter" &&
systemd-run --user --unit="$unit-lio" --property=KillSignal=SIGINT /bin/bash "$session/baseline.sh"
```

看到一条新的里程计消息后启动录包。若等不到消息，先看 `tail -n 20 "$session/mapping.log"`，保持设备静止。

```bash
ros2 topic echo /Odometry --once --field header
systemd-run --user --unit="$unit-record" --property=KillSignal=SIGINT --property=TimeoutStopSec=90 /bin/bash "$session/record.sh"
journalctl --user -u "$unit-record" -n 25 --no-pager
```

录包日志应显示已订阅 `/livox/lidar`、`/livox/imu`、`/camera/image_raw`、`/Odometry` 四个话题。等四项齐全再走。记下打印的本次目录；若 SSH 断开，用户服务可继续运行。重新登录后先执行本节开头的 `root`、`ref` 和两条 `source`，再把 `session` 设回刚才打印的完整路径，执行 `unit=$(basename "$session")`。

**怎么走才能得到更多全景颜色。** 先放稳数秒，再缓慢移动。相机视场比雷达窄，要让镜头依次看见每面墙、桌椅正侧面和角落；需给地面或上方上色时，也要让它们进入相机画面。相邻视角留出重叠，转角放慢，走完后放稳。只把雷达绕一圈，朝向始终不变的相机无法给背面的点提供实拍颜色。

## 3. 停止录包，保存地图，再停止建图

在第 2 步的终端执行。设备保持静止。第一段结束后应看到话题、消息数和时长。

```bash
systemctl --user stop "$unit-record"
test -s "$session/room-bag/metadata.yaml" && ros2 bag info "$session/room-bag"
```

确认有本次采集的四个话题且各自消息数大于零。再执行：

```bash
python3 -s "$root/save-map.py" "$session" &&
systemctl --user stop "$unit-lio"
```

保存成功会打印 `MAP_FILE_PASS` 和点数，同时生成 `map.pcd`、`map-validation.json`。命令用 `&&` 把保存成功作为停建图的条件；保存失败时请保留建图进程，查看报错和 `mapping.log`。这次使用按场次命名的服务，所以请用上面的停止命令。旧的 `stop-mapping.sh` 根据另一种启动流程的标记文件寻找进程。

至此可以继续看实时预览。若要结束传感器采集，此时再关闭实时预览窗口。

## 4. 生成全景彩色点云

仍在 Orin 上，用第 2 步的 `session`。下面的输入是**刚刚正常关闭**的录包和同一场次保存的几何地图。标定文件对应当前固定安装；若移动过镜头或改变雷达与相机的相对位置，旧外参不能直接沿用。

```bash
test -s "$session/room-bag/metadata.yaml" &&
test -s "$session/map-validation.json" &&
test ! -e "$session/livo-input" &&
python3 -s "$ref/prepare_livo_room.py" "$session"
```

这一步解码 Bayer 原图，按内参校正图像，并生成 `livo-input/`、`camera.yaml`、`room-livo.yaml` 和 `input-summary.json`。确认成功后上色：

```bash
test -s "$session/livo-input/metadata.yaml" &&
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python3 -s "$ref/color_room_geometry.py" "$session"
cat "$session/observed-rgb.json"
```

结果是 `room-observed-rgb.pcd`。检查报告里的 `geometry_points`（几何点）、`colored_points`（实际取得颜色的点）和 `frames_with_pose`（有对应位姿的图像）。彩色覆盖率可以用前两项相除。首次生成成功后直接使用现有结果即可；已有同名中间目录或点云时先检查上次结果，保留原始记录。

## 5. 在 Windows 生成可旋转的本地网页

在 **Windows PowerShell** 执行，第一行输入第 2 步打印的 Orin 场次目录。脚本使用 Windows 上的项目模板和带 NumPy 的 Python。已有完整程序按点坐标毫米值写入有符号 16 位预览数据，每轴坐标应在约 ±32.76 米内；更大的场地可直接用 CloudCompare 打开原始 PCD。

```powershell
$remoteSession = Read-Host '粘贴 Orin 本次目录的完整路径'
$onboard = 'E:\chatgpt_project\mid360s_mapping\onboard'
$localSession = Join-Path "$onboard\evidence" (Split-Path $remoteSession -Leaf)
New-Item -ItemType Directory -Path $localSession -Force | Out-Null
$key = "$env:USERPROFILE\.ssh\mid360s_orin_20261123"
scp -i "$key" "door@192.168.2.127:$remoteSession/map.pcd" "door@192.168.2.127:$remoteSession/room-observed-rgb.pcd" "$localSession"
if ($LASTEXITCODE -ne 0) { throw '点云复制失败，请核对 Orin 地址和场次目录' }
python "$onboard\view_room_map.py" "$localSession"
if ($LASTEXITCODE -ne 0) { throw '网页生成失败，请查看 Python 报错' }
Start-Process (Join-Path $localSession 'room-3d.html')
```

## 常见情况

| 现象 | 先看哪里 |
|---|---|
| 几何有了，彩色只有一部分 | 对比全景几何和彩色模式；检查相机是否真正扫过缺色区域，以及 `frames_with_pose` 的数量 |
| 预览有相机图，但彩色生成失败 | 用 `ros2 bag info` 检查已关闭录包是否实际录到了原图和里程计；预览画面不能替代这两路记录 |
| 录包没有 `metadata.yaml` | 查看 `journalctl --user -u "$unit-record" -n 40`，确认录包已正常结束；暂缓运行上色脚本 |
| 门框、桌边颜色错位 | 核对刚性安装和相机转动速度；当前外参是自然场景候选值，曝光相位与 ROS 时间的对应关系尚未验收 |
| 想直接使用在线 FAST-LIVO2 | 上次静置时读到了真彩点云，但手持回放的轨迹发散。本文交付的手持地图采用 FAST-LIO 几何和离线真彩投影；在线融合仍属实验 |

本文核对了 Orin 上的历史脚本、安装路径和已封包的数据。新场次的服务名和目录按现场脚本整理，编写说明时没有重新启动设备或再做一遍手持实验。
