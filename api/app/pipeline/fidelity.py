"""Translation fidelity checks: deterministic, no model, no added latency.

A model translation can drop a number, add one, or flip a "not". These checks compare the source and the
translation on exactly those things, because they are the errors that change meaning in a clinic
(dose, days, allergy yes/no). They cannot prove a translation is right; they catch the dangerous kinds of wrong.

Used three ways:
- Korean said to the doctor (patient relay, case-card Korean): a mismatch BLOCKS the translation and the
  patient's own words are shown instead.
- Translations shown to the patient (doctor's words, prescription gloss): a mismatch FLAGS the text, and the
  original Korean / printed numbers stay on screen as the reference.
"""

from __future__ import annotations

import re

_DIGITS = re.compile(r"\d+(?:\.\d+)?")
# Only real numerals count here. Words like "yesterday", "a week", 하루 are left out on purpose: they are
# time units, not numbers, and counting them on one side only would raise false alarms.
_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
          "eight": "8", "nine": "9", "ten": "10", "once": "1", "twice": "2", "thrice": "3"}
_WORD_RE = re.compile(r"\b(" + "|".join(_WORDS) + r")\b", re.I)
_TH = {"หนึ่ง": "1", "สอง": "2", "สาม": "3", "สี่": "4", "ห้า": "5", "หก": "6", "เจ็ด": "7", "แปด": "8",
       "เก้า": "9", "สิบ": "10"}
_TH_NOT_NUMBERS = ["สามี", "สามารถ", "หกล้ม", "สองสาม"]  # husband, can, fell over, "a few"
_KO_NATIVE = {"이틀": "2", "사흘": "3", "나흘": "4", "닷새": "5", "엿새": "6", "이레": "7", "열흘": "10",
              "보름": "15", "한 번": "1", "두 번": "2", "세 번": "3", "네 번": "4", "한번": "1", "두번": "2",
              "세번": "3", "네번": "4", "한 알": "1", "두 알": "2", "한 방울": "1", "두 방울": "2"}
_KO_SINO = re.compile(r"(?<![가-힣])(일|이|삼|사|오|육|칠|팔|구|십)\s?(일|주|개월|년|회|시간|분|정|알|방울)"
                      r"(?=[\s,.?!~]|$|간|째|동안|전|에|이|은|씩|정도)")
_SINO = {"일": "1", "이": "2", "삼": "3", "사": "4", "오": "5", "육": "6", "칠": "7", "팔": "8", "구": "9", "십": "10"}


def numbers(text: str) -> set[str]:
    text = text or ""
    nums = set(_DIGITS.findall(text))
    nums |= {_WORDS[m.lower()] for m in _WORD_RE.findall(text)}
    th = text
    for word in _TH_NOT_NUMBERS:
        th = th.replace(word, " ")
    nums |= {d for w, d in _TH.items() if w in th}
    rest = text
    for w, d in _KO_NATIVE.items():
        if w in rest:
            nums.add(d)
            rest = rest.replace(w, " ")
    nums |= {_SINO[m.group(1)] for m in _KO_SINO.finditer(rest)}
    return nums

# Negation cues. Korean "안" only as a separate word (not 안약 / 안과); "못" likewise.
_NEG = {
    "ko": re.compile(r"없|않|아니|(?<![가-힣])안(?=\s)|(?<![가-힣])못(?=\s)|말고|마세요|금지|불가"),
    "en": re.compile(r"\b(no|not|none|never|without|don't|doesn't|didn't|isn't|aren't|can't|cannot|haven't|hasn't|nothing)\b|n't\b", re.I),
    "th": re.compile(r"ไม่|ห้าม|อย่า|ไม่มี|ไม่เคย"),
}


def has_negation(text: str) -> bool:
    return any(p.search(text or "") for p in _NEG.values())


def compare(source: str, translation: str) -> list[str]:
    """Problems found between a source text and its translation. Empty list = nothing caught."""
    src, dst = numbers(source), numbers(translation)
    issues = [f"number_missing:{n}" for n in sorted(src - dst)]
    issues += [f"number_added:{n}" for n in sorted(dst - src)]
    if has_negation(source) != has_negation(translation):
        issues.append("negation_mismatch")
    return issues
