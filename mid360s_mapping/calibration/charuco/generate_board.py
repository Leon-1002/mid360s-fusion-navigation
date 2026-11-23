"""Generate and validate the project's dimensioned vector ChArUco PDF."""
from pathlib import Path
import hashlib
import json
import cv2
import pymupdf as fitz
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "pdf"
NAME = "mid360s-charuco-5x7-30mm-A4-v1"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    board = cv2.aruco.CharucoBoard((5, 7), 0.030, 0.021, dictionary)
    board.setLegacyPattern(False)
    pdf = OUT / (NAME + ".pdf")
    c = canvas.Canvas(str(pdf), pagesize=(210 * mm, 297 * mm), invariant=1)
    c.setTitle("Mid-360S Fusion Navigation - ChArUco Calibration Board v1")
    c.setAuthor("Leon-1002 / mid360s-fusion-navigation")
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(105 * mm, 280 * mm, "MID360S FUSION NAVIGATION")
    c.setFont("Helvetica", 10)
    c.drawCentredString(105 * mm, 273 * mm, "ChArUco v1 | 5 x 7 squares | DICT_4X4_50")
    c.drawCentredString(105 * mm, 267 * mm, "Square: 30 mm | Marker outer edge: 21 mm | IDs: 0-16")
    # Board top-left is (30, 255) mm in PDF coordinates. The board is
    # 150 x 210 mm. OpenCV board coordinates run right/down from top-left.
    def rect(x, y, w, h):
        c.rect((30 + x) * mm, (255 - y - h) * mm,
               w * mm, h * mm, stroke=0, fill=1)

    for row in range(7):
        for col in range(5):
            if (row + col) % 2 == 0:
                rect(col * 30, row * 30, 30, 30)
    # Each marker has 4 payload modules and a 1-module black border.
    # Use OpenCV's marker geometry and dictionary instead of inventing IDs.
    for marker_id, corners in zip(board.getIds(), board.getObjPoints()):
        x, y = np.round(corners[0, :2] * 1000, 4)
        bits = cv2.aruco.generateImageMarker(dictionary, int(marker_id), 6, borderBits=1)
        rect(float(x), float(y), 21, 21)
        white_path = c.beginPath()
        for row in range(6):
            for col in range(6):
                if bits[row, col] == 255:
                    white_path.rect((30 + float(x) + col * 3.5) * mm,
                                    (255 - float(y) - (row + 1) * 3.5) * mm,
                                    3.5 * mm, 3.5 * mm)
        c.setFillColorRGB(1, 1, 1)
        c.drawPath(white_path, stroke=0, fill=1)
        c.setFillColorRGB(0, 0, 0)

    c.setLineWidth(0.2 * mm)
    c.line(55 * mm, 29 * mm, 155 * mm, 29 * mm)
    for x in (55, 155):
        c.line(x * mm, 27 * mm, x * mm, 31 * mm)
    c.setFont("Helvetica", 9)
    c.drawCentredString(105 * mm, 34 * mm, "100 mm CHECK - measure between end ticks")
    c.line(18 * mm, 100 * mm, 18 * mm, 200 * mm)
    for y in (100, 200):
        c.line(16 * mm, y * mm, 20 * mm, y * mm)
    c.saveState()
    c.translate(13 * mm, 150 * mm)
    c.rotate(90)
    c.drawCentredString(0, 0, "100 mm CHECK")
    c.restoreState()
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(105 * mm, 19 * mm, "A4 - Print at Actual Size (100%) - Disable Fit to Page")
    c.setFont("Helvetica", 8)
    c.drawCentredString(105 * mm, 13 * mm, "Keep flat. Do not cover the pattern. Camera intrinsics target.")
    c.showPage()
    c.save()

    config = {
        "board_id": NAME, "type": "charuco", "dictionary": "DICT_4X4_50",
        "squares_x": 5, "squares_y": 7, "square_length_m": 0.030,
        "marker_length_m": 0.021, "marker_border_bits": 1,
        "marker_ids": board.getIds().tolist(), "legacy_pattern": False,
        "top_left_square": "black", "charuco_corner_count": 24,
        "board_size_mm": [150, 210], "paper_size_mm": [210, 297],
        "board_origin": "top-left chessboard corner, x right, y down",
        "print_scale_percent": 100, "check_lines_mm": {"horizontal": 100, "vertical": 100},
        "generator_opencv_version": cv2.__version__,
    }
    (ROOT / "board.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    # Validate the DELIVERED PDF, not merely OpenCV's source pattern.
    doc = fitz.open(pdf)
    assert len(doc) == 1
    page = doc[0]
    np.testing.assert_allclose([page.rect.width / mm, page.rect.height / mm], [210, 297], atol=0.001)
    pix = page.get_pixmap(dpi=300, colorspace=fitz.csGRAY, alpha=False)
    gray = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    charuco, charuco_ids, markers, ids = cv2.aruco.CharucoDetector(board).detectBoard(gray)
    assert ids is not None and sorted(ids.flatten().tolist()) == list(range(17))
    assert charuco_ids is not None and sorted(charuco_ids.flatten().tolist()) == list(range(24))
    # Verify placement and scale against independent PDF millimetre positions.
    points = board.getChessboardCorners()[charuco_ids.flatten(), :2] * 1000
    expected = (points + np.array([30, 42])) * (300 / 25.4)
    errors = np.linalg.norm(charuco.reshape(-1, 2) - expected, axis=1)
    assert float(errors.max()) < 1.5, errors
    lines = [item for path in page.get_drawings() for item in path["items"] if item[0] == "l"]
    lengths_mm = [abs(item[2] - item[1]) / mm for item in lines]
    assert sum(abs(length - 100) < 0.001 for length in lengths_mm) == 2
    page.get_pixmap(dpi=150, alpha=False).save(OUT / (NAME + "-preview.png"))
    report = {
        "result": "PASS", "page_count": 1, "page_size_mm": [210, 297],
        "detected_markers": len(ids), "detected_charuco_corners": len(charuco_ids),
        "render_dpi": 300, "max_corner_position_error_px": float(errors.max()),
        "check_lines_100mm": 2, "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "note": "Digital file validation only; measure both 100 mm bars after physical printing.",
    }
    (ROOT / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
