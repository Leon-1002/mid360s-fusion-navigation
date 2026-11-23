# 项目专用 ChArUco 标定板 v1

用于 ZM-3000-60UC 相机内参和畸变标定。本板由程序重新生成，不使用他人的照片、标题或打印文件；标记编码使用 OpenCV 标准字典。此板本身不代表相机与雷达外参已标定，也不是 FAST-Calib 的四圆孔靶板。

## 打印文件与参数

- 打印：[A4 矢量 PDF](output/pdf/mid360s-charuco-5x7-30mm-A4-v1.pdf)。请打印 PDF，不要打印预览 PNG。
- 参数：[board.json](board.json)。尺寸单位为米，标定程序应读取这个文件。
- 数字文件检查：[validation.json](validation.json)。这是文件验证，不是相机标定结果。
- 5 列 × 7 行棋盘格，单格 **30 mm**；对应 **4×6=24 个内部角点**。
- 白格内标记的黑色外框边长 **21 mm**；字典 `DICT_4X4_50`，标记 ID 为 0–16，边框 1 个模块，`legacy_pattern=false`。
- 棋盘区域 **150×210 mm**，A4 纸 **210×297 mm**；横、纵各有一条 **100 mm** 校验线。

旧板的标记边长尚未确定。本参数文件仅对应新生成的 v1 板，不可直接套到旧板上。

## 打印、固定和验收

1. 纸张选择 A4、纵向、单面，选择“实际大小 / 100%”；关闭“适合页面”、缩放和无边距自动放大。
2. 使用不反光的白纸，黑色打印清晰，不覆反光膜。将整个棋盘区域贴紧平整、坚硬的底板，避免局部鼓包；胶带只贴图案外的留白。
3. 分别测量横、纵校验线的端点刻线间距，都应为 100 mm。尺寸不符应修正打印设置并重打；横纵比例不一致的纸张不能直接使用名义参数。
4. 抽查棋盘格 30 mm、标记外框 21 mm。新板必须重新测量，旧板测得 100 mm 不代表新打印件也正确。
5. 保持镜头焦距、对焦位置不变，使用实际采集分辨率 3072×2048。采集覆盖画面中心、四边、四角，并具有不同倾角和距离的清晰图像；移动后停稳再取样，避免运动模糊。
6. 相机内参求解之后，另行进行固定安装下的相机—雷达外参标定；不得把支架外形尺寸或示例配置当作已标定外参。

## 复刻生成与验证

本次生成环境为 Python 3.12，依赖版本固定在 requirements.txt：`opencv-python` 5.0.0.93（此版本提供 `cv2.aruco.CharucoBoard` 和 `CharucoDetector`）、`numpy`、`reportlab`、`PyMuPDF`。建议在独立虚拟环境中安装，不改变采集程序环境。Orin 的标定程序只需读取板参数，不必安装这套 PDF 生成依赖。

```bash
python -m venv .venv
# Linux: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python generate_board.py
```

程序使用 OpenCV 的字典编码和板上标记坐标，以矢量矩形绘制 PDF。随后将实际 PDF 渲染为 300 DPI 图像，要求检出全部 **17 个标记和 24 个 ChArUco 角点**，检查 A4 页面、角点尺寸位置、两条 100 mm 校验线，并生成 150 DPI 预览。打开预览检查排版，实际打印后仍需尺量。

参考：[OpenCV ChArUco 板定义与检测](https://docs.opencv.org/4.x/df/d4a/tutorial_charuco_detection.html)。
