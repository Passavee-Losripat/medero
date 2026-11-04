"""Render MOCK prescription labels and receipts to PNG for the reader demo and eval.

Uses Pillow and a local Korean system font (not redistributed; only the rendered
MOCK images are). Every image carries a MOCK watermark. Run: make mock-docs
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT_CANDIDATES = [os.getenv("MOCK_FONT", ""), "/System/Library/Fonts/AppleSDGothicNeo.ttc",
                   "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"]


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if p and Path(p).exists():
            return ImageFont.truetype(p, size)
    sys.exit("No Korean font found; set MOCK_FONT to a .ttf/.ttc path")


def watermark(img: Image.Image) -> None:
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font(120)
    for y in range(0, img.height, 260):
        d.text((40, y), "MOCK  MOCK  MOCK", font=f, fill=(220, 40, 40, 45))
    img.alpha_composite(layer)


def render_slip(slip: dict, out: Path) -> None:
    w, h = 900, 260 + 150 * len(slip["items"])
    img = Image.new("RGBA", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, w - 10, h - 10], outline="black", width=3)
    d.text((40, 30), slip["title"], font=font(44), fill="black")
    d.text((40, 95), f"환자: {slip['patient']}   조제일: {slip['date']}", font=font(28), fill="black")
    d.text((40, 140), "약품명 / 1회 투약량 / 1일 투여횟수 / 총 투약일수", font=font(24), fill=(90, 90, 90))
    y = 190
    for it in slip["items"]:
        d.line([30, y - 10, w - 30, y - 10], fill=(200, 200, 200), width=2)
        d.text((40, y), it["drug_name_ko"], font=font(34), fill="black")
        d.text((40, y + 50), f"{it['dose']}   {it['times_per_day']}   {it['days']}   {it['instructions_ko']}",
               font=font(30), fill="black")
        y += 150
    d.text((40, h - 60), "약사에게 확인하세요 · MOCK 샘플 (실제 처방 아님)", font=font(24), fill=(200, 0, 0))
    watermark(img)
    img.convert("RGB").save(out)


def main() -> None:
    slips = json.loads((HERE / "prescriptions" / "slips.json").read_text(encoding="utf-8"))["slips"]
    for s in slips:
        out = HERE / "prescriptions" / f"{s['id']}.png"
        render_slip(s, out)
        print("wrote", out.relative_to(HERE.parent.parent))


if __name__ == "__main__":
    main()
