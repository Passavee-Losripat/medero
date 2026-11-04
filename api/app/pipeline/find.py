"""Find a clinic or pharmacy: hand-off to a map app, nothing more.

Korean clinics are organised by department (과). This maps the BODY PART or plain words the patient used
to the department signboard to search for. It is a fixed keyword table, not a model, and it never names a
condition. The patient chooses; Medero never ranks or recommends a place. Emergency words show the fixed
emergency card instead (guardrail 6).

Keyword lists are drafts and need native-speaker review (docs/korean-review.md).
"""

from __future__ import annotations

import re
from urllib.parse import quote

from .. import fixed_text as fx
from ..safety import detect_emergency

# id, Korean signboard name, English, Thai, keywords (en / th / ko), matched as lowercase substrings
DEPARTMENTS: list[dict] = [
    {"id": "eye", "ko": "안과", "en": "Eye clinic (ophthalmology)", "th": "คลินิกตา",
     "kw": ["eye", "vision", "contact lens", "ปวดตา", "ตาแดง", "เจ็บตา", "คันตา", "ดวงตา", "눈이", "눈 ", "눈알", "시력", "렌즈"]},
    {"id": "ent", "ko": "이비인후과", "en": "Ear, nose & throat", "th": "หู คอ จมูก",
     "kw": ["ear", "nose", "throat", "sinus", "hearing", "ปวดหู", "หูอื้อ", "จมูก", "เจ็บคอ", "ไซนัส", "귀가", "귀 ", "콧물", "코가", "목이 아", "인후"]},
    {"id": "skin", "ko": "피부과", "en": "Skin clinic (dermatology)", "th": "คลินิกผิวหนัง",
     "kw": ["skin", "rash", "acne", "ผิว", "ผื่น", "สิว", "피부", "두드러기", "여드름"]},
    {"id": "dental", "ko": "치과", "en": "Dentist", "th": "ทันตกรรม",
     "kw": ["tooth", "teeth", "gum", "dental", "ฟัน", "เหงือก", "이가 아", "치아", "잇몸", "치과"]},
    {"id": "ortho", "ko": "정형외과", "en": "Bones & joints (orthopedics)", "th": "กระดูกและข้อ",
     "kw": ["bone", "joint", "ankle", "knee", "wrist", "shoulder", "back pain", "neck", "sprain", "twist",
            "กระดูก", "ปวดข้อ", "ข้อเท้า", "เข่า", "ปวดหลัง", "แพลง", "뼈", "관절", "발목", "무릎", "손목", "어깨", "허리", "삐었"]},
    {"id": "internal", "ko": "내과", "en": "General medicine (internal medicine)", "th": "อายุรกรรม",
     "kw": ["stomach", "belly", "fever", "cough", "cold", "flu", "diarrh", "vomit", "ท้อง", "ไข้", "ไอ", "หวัด",
            "ท้องเสีย", "อาเจียน", "배가", "복통", "열이", "기침", "감기", "설사", "구토"]},
    {"id": "kids", "ko": "소아청소년과", "en": "Children's clinic (pediatrics)", "th": "กุมารเวช",
     "kw": ["child", "baby", "kid ", "kids", "my son", "daughter", "ลูก", "เด็ก", "아이가", "아기", "소아"]},
    {"id": "women", "ko": "산부인과", "en": "Women's health (OB/GYN)", "th": "สูตินรีเวช",
     "kw": ["pregnan", "period", "menstrua", "vagina", "ตั้งครรภ์", "ประจำเดือน", "임신", "생리"]},
    {"id": "uro", "ko": "비뇨의학과", "en": "Urology", "th": "ระบบทางเดินปัสสาวะ",
     "kw": ["urin", "pee", "bladder", "ปัสสาวะ", "소변"]},
    {"id": "mental", "ko": "정신건강의학과", "en": "Mental health", "th": "สุขภาพจิต",
     "kw": ["anxiety", "depress", "panic", "insomnia", "can't sleep", "เครียด", "ซึมเศร้า", "นอนไม่หลับ",
            "불안", "우울", "불면"]},
    {"id": "family", "ko": "가정의학과", "en": "Family medicine (general clinic)", "th": "เวชศาสตร์ครอบครัว", "kw": []},
    {"id": "pharmacy", "ko": "약국", "en": "Pharmacy", "th": "ร้านขายยา",
     "kw": ["pharmacy", "prescription", "medicine", "ร้านขายยา", "ใบสั่งยา", "약국", "처방전"]},
]
_BY_ID = {d["id"]: d for d in DEPARTMENTS}


def _hit(keyword: str, text: str) -> bool:
    # English keywords must start a word ("ear" not in "near"); Thai/Korean have no such spacing rule
    if keyword.isascii():
        return re.search(r"(?<![a-z])" + re.escape(keyword), text) is not None
    return keyword in text


def map_links(query_ko: str) -> dict[str, str]:
    """Search links for the map apps people use in Korea. The app searches around the user's location."""
    q = quote(query_ko)
    return {"naver": f"https://map.naver.com/p/search/{q}",
            "kakao": f"https://map.kakao.com/link/search/{q}",
            "google": f"https://www.google.com/maps/search/{q}"}


def _public(d: dict, lang: str) -> dict:
    name = d.get(lang.split("-")[0]) or d["en"]
    return {"id": d["id"], "ko": d["ko"], "name": name, "links": map_links(d["ko"])}


FIND_SCHEMA = {"type": "object",
               "properties": {"department": {"type": "string", "enum": [d["id"] for d in DEPARTMENTS] + ["unsure"]}},
               "required": ["department"]}
FIND_SYSTEM = """You help a patient in Korea find which clinic signboard (department) to look for.
Read the patient's own words and choose ONE department id from the enum, or "unsure".
Choose by the body part or the kind of help asked for. Never name or guess a condition. Output JSON only."""


async def suggest_with_model(text: str, lang: str, provider) -> dict:
    """Keywords first (instant). Only when nothing matches, a constrained model call may pick one id
    from the fixed list; it cannot return free text, so it cannot name a condition."""
    out = suggest(text, lang)
    out["source"] = "keywords"
    if out["emergency"] or out["suggested"] or provider is None or len((text or "").strip()) < 4:
        return out
    res = await provider.json(task="find_department", system=FIND_SYSTEM,
                              user=f"PATIENT SAID: {text[:300]}", schema=FIND_SCHEMA, timeout_s=20)
    dep = (res.data or {}).get("department")
    if dep in _BY_ID:
        out["suggested"] = [_public(_BY_ID[dep], lang)]
        out["source"] = f"model:{provider.model}"
    return out


def suggest(text: str, lang: str = "en") -> dict:
    """Departments whose keywords appear in the patient's own words. Empty if nothing matches."""
    term = detect_emergency(text or "")
    if term:
        return {"emergency": True, "card": fx.EMERGENCY_CARD, "matched": [term]}
    low = (text or "").lower()
    matched, hits = [], []
    for d in DEPARTMENTS:
        found = [k for k in d["kw"] if _hit(k, low)]
        if found:
            hits.append(d["id"])
            matched += found
    if "kids" in hits:  # a child is mentioned: the children's clinic first
        hits.remove("kids"); hits.insert(0, "kids")
    return {"emergency": False, "suggested": [_public(_BY_ID[i], lang) for i in hits],
            "matched": matched, "all": [_public(d, lang) for d in DEPARTMENTS]}
