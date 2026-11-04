"""Render MOCK prescription labels and receipts to PNG for the reader demo and eval.

Uses Pillow with SIL Open Font License fonts from Google Fonts: Noto Sans KR (print) and Nanum Pen Script
(handwritten note). Run `make mock-docs`; it downloads the fonts into data/mock/.fonts (git-ignored) if missing.
Every image carries a MOCK watermark.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE / ".fonts"
FONT_URLS = {  # SIL OFL 1.1 (google/fonts)
    "NotoSansKR.ttf": "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf",
    "NanumPenScript-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/nanumpenscript/NanumPenScript-Regular.ttf",
}


def _font_file(name: str) -> Path:
    path = FONTS / name
    if not path.exists():
        import urllib.request
        FONTS.mkdir(exist_ok=True)
        urllib.request.urlretrieve(FONT_URLS[name], path)
    return path


def font(size: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(_font_file("NotoSansKR.ttf")), size)
    try:
        f.set_variation_by_axes([500])  # variable font: medium weight
    except Exception:
        pass
    return f


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


def pen_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_font_file("NanumPenScript-Regular.ttf")), size + 8)


def render_form(form: dict, out: Path) -> None:
    """A MOCK clinic prescription form (처방전) in the standard layout: header boxes, a medicine table with
    per-dose / per-day / days / substitution / instructions columns, and the validity line."""
    w, h = 1240, 1500
    ink, blue = (20, 20, 20), (40, 60, 150)
    img = Image.new("RGBA", (w, h), "white")
    d = ImageDraw.Draw(img)
    L, R = 60, w - 60
    d.text((L, 40), "[MOCK 서식]", font=font(22), fill=ink)
    d.text((w // 2 - 130, 70), "처  방  전", font=font(64), fill=ink)
    d.text((w // 2 + 160, 100), "(약국보관용)", font=font(26), fill=ink)
    boxes = ["건강보험", "의료급여", "산재보험", "자동차보험", "기타"]
    x = L
    for b in boxes:
        mark = "■" if b == form["insurance_box"] else "□"
        d.text((x, 170), f"{mark} {b}", font=font(26), fill=ink)
        x += 200
    # header grid
    top = 220
    rows = [("교부일자", form["issued"], "의료기관 명칭", form["clinic"]),
            ("교부번호", form["number"], "전화번호", "000-000-0000 (MOCK)"),
            ("환자 성명", form["patient"], "처방 의료인", form["doctor"]),
            ("주민등록번호", "XXXXXX-XXXXXXX (MOCK)", "면허번호", "제 00000 호 (MOCK)")]
    rh = 56
    for i, (a, b, c, e) in enumerate(rows):
        y = top + i * rh
        d.rectangle([L, y, R, y + rh], outline=ink, width=2)
        d.line([L + 190, y, L + 190, y + rh], fill=ink, width=2)
        d.line([w // 2, y, w // 2, y + rh], fill=ink, width=2)
        d.line([w // 2 + 200, y, w // 2 + 200, y + rh], fill=ink, width=2)
        d.text((L + 12, y + 14), a, font=font(24), fill=ink)
        d.text((L + 205, y + 12), b, font=font(26), fill=ink)
        d.text((w // 2 + 12, y + 14), c, font=font(24), fill=ink)
        d.text((w // 2 + 215, y + 12), e, font=font(26), fill=ink)
    y = top + 4 * rh
    d.rectangle([L, y, R, y + rh], outline=ink, width=2)
    d.line([L + 190, y, L + 190, y + rh], fill=ink, width=2)
    d.text((L + 12, y + 14), "질병분류기호", font=font(24), fill=ink)
    if form["disease_code"]:
        d.text((L + 205, y + 12), form["disease_code"], font=font(28), fill=ink)
    d.text((L, y + rh + 10), "※ 환자의 요구가 있을 때에는 질병분류기호를 기재하지 아니합니다.", font=font(22), fill=ink)
    # medicine table
    ty = y + rh + 60
    cols = [L, L + 470, L + 580, L + 690, L + 800, L + 910, R]
    heads = ["처방 의약품의 명칭", "1회\n투약량", "1일\n투여횟수", "총\n투약일수", "대체\n가능", "용법"]
    d.rectangle([L, ty, R, ty + 80], fill=(225, 232, 250), outline=ink, width=2)
    for i, hd in enumerate(heads):
        d.multiline_text((cols[i] + 10, ty + 10), hd, font=font(22), fill=ink, spacing=4)
    body_top, row_h = ty + 80, 64
    n_rows = 8
    for i in range(n_rows + 1):
        d.line([L, body_top + i * row_h, R, body_top + i * row_h], fill=(150, 150, 150), width=1)
    for c in cols:
        d.line([c, ty, c, body_top + n_rows * row_h], fill=ink, width=2)
    for i, it in enumerate(form["items"]):
        yy = body_top + i * row_h + 18
        name = ("(비급여)" if it.get("not_covered") else "") + it["drug_name_ko"]
        d.text((L + 10, yy), name, font=font(25), fill=ink)
        for j, k in enumerate(["dose", "times_per_day", "days"]):
            d.text((cols[j + 1] + 45, yy), it[k], font=font(26), fill=ink)
        d.text((cols[4] + 22, yy), it["substitution"], font=font(25), fill=ink)
        d.text((cols[5] + 10, yy), it["instructions_ko"], font=font(23), fill=ink)
        if it.get("handwritten"):
            # pen note beside its own line; the arrow comes from the print font (the pen font has no "→")
            note = Image.new("RGBA", (200, 56), (0, 0, 0, 0))
            nd = ImageDraw.Draw(note)
            text = it["handwritten"]
            x0 = 0
            if text.startswith("→"):
                nd.text((0, 10), "→", font=font(26), fill=blue + (255,))
                x0, text = 30, text[1:]
            nd.text((x0, 2), text, font=pen_font(30), fill=blue + (255,))
            img.alpha_composite(note.rotate(3, expand=True), (cols[5] + 108, yy - 14))
    by = body_top + n_rows * row_h + 40
    d.rectangle([L, by, R, by + 70], outline=ink, width=2)
    d.text((L + 20, by + 20), f"사용기간   교부일로부터 (  {form['valid_days']}  )일간      사용기간 내에 약국에 제출하여야 합니다.",
           font=font(26), fill=ink)
    d.text((L, h - 70), "MOCK 샘플 서식 · 실제 처방 아님 · 가상의 의료기관/약품", font=font(24), fill=(200, 0, 0))
    watermark(img)
    img.convert("RGB").save(out)


def render_receipt(r: dict, out: Path) -> None:
    """A generic MOCK receipt: title, issuer, patient, date, line items, totals."""
    w = 900
    rows = r["lines"] + r["extra"]
    h = 420 + 64 * len(rows)
    ink = (20, 20, 20)
    img = Image.new("RGBA", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([14, 14, w - 14, h - 14], outline=ink, width=3)
    d.text((w // 2, 60), r["title"], font=font(50), fill=ink, anchor="mm")
    d.text((w // 2, 112), r["subtitle"], font=font(24), fill=ink, anchor="mm")
    y = 160
    for k, v in [("발행기관", r["org"]), ("환자 성명", r["patient"] or "—"), ("진료(조제)일", r["date"])]:
        d.text((50, y), k, font=font(26), fill=(80, 80, 80))
        d.text((300, y), v, font=font(28), fill=ink)
        y += 48
    d.line([40, y + 6, w - 40, y + 6], fill=ink, width=2)
    y += 28
    for i, (k, v) in enumerate(rows):
        bold = i >= len(r["lines"])
        d.text((50, y), k, font=font(30 if bold else 28), fill=ink)
        d.text((w - 60, y), v + (" 원" if v and v[0].isdigit() and "-" not in v and "*" not in v else ""),
               font=font(30 if bold else 28), fill=ink, anchor="ra")
        y += 64
    d.text((50, h - 60), "MOCK 샘플 · 실제 영수증 아님", font=font(22), fill=(200, 0, 0))
    watermark(img)
    img.convert("RGB").save(out)


def main() -> None:
    slips = json.loads((HERE / "prescriptions" / "slips.json").read_text(encoding="utf-8"))["slips"]
    for s in slips:
        out = HERE / "prescriptions" / f"{s['id']}.png"
        render_slip(s, out)
        photo = HERE / "prescriptions" / f"{s['id']}_photo.jpg"
        phone_photo(out, photo)
        print("wrote", out.relative_to(HERE.parent.parent), "and", photo.name)
    receipts = json.loads((HERE / "receipts" / "receipts.json").read_text(encoding="utf-8"))["receipts"]
    for r in receipts:
        out = HERE / "receipts" / f"{r['id']}.png"
        render_receipt(r, out)
        photo = HERE / "receipts" / f"{r['id']}_photo.jpg"
        phone_photo(out, photo, angle=5, blur=0.8)
        print("wrote", out.relative_to(HERE.parent.parent), "and", photo.name)
    forms = json.loads((HERE / "prescriptions" / "forms.json").read_text(encoding="utf-8"))["forms"]
    for f in forms:
        out = HERE / "prescriptions" / f"{f['id']}.png"
        render_form(f, out)
        photo = HERE / "prescriptions" / f"{f['id']}_photo.jpg"
        phone_photo(out, photo, angle=-4, blur=0.9)
        print("wrote", out.relative_to(HERE.parent.parent), "and", photo.name)




def phone_photo(src: Path, out: Path, angle: float = -7, blur: float = 1.2) -> None:
    """Simulate a hand-held phone photo of a MOCK label: tilt, perspective, blur, uneven light, JPEG."""
    from PIL import ImageFilter, ImageEnhance

    img = Image.open(src).convert("RGB")
    w, h = img.size
    bg = Image.new("RGB", (int(w * 1.35), int(h * 1.5)), (164, 150, 132))  # desk
    bg.paste(img, ((bg.width - w) // 2, (bg.height - h) // 2))
    bg = bg.rotate(angle, resample=Image.BICUBIC, fillcolor=(150, 138, 120))
    dx = int(bg.width * 0.06)
    bg = bg.transform(bg.size, Image.QUAD, (dx, 0, 0, bg.height, bg.width, bg.height, bg.width - dx // 2, 0),
                      resample=Image.BICUBIC)
    shade = Image.linear_gradient("L").resize(bg.size).rotate(35)
    bg = Image.composite(bg, ImageEnhance.Brightness(bg).enhance(0.62), shade)
    bg = bg.filter(ImageFilter.GaussianBlur(blur))
    bg.save(out, "JPEG", quality=62)


if __name__ == "__main__":
    main()
