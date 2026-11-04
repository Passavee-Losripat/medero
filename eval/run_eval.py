"""Medero evaluation harness (CLAUDE.md section 8).

Writes eval/results/latest.md and eval/results/latest.json. All data is MOCK.
Only measured numbers are written. Sections that need a model are skipped (and say
so) when no API key is configured or a provider is unreachable.

Usage:  python eval/run_eval.py [--routers rules,spark,local,modal] [--no-rx] [--out DIR]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.config import get_settings  # noqa: E402
from app.pipeline import documents, intake  # noqa: E402
from app.pipeline.router import route  # noqa: E402
from app.pipeline.verifier import FIXED_PHRASES, check_model, check_rules  # noqa: E402
from app.pipeline.visit import new_session  # noqa: E402
from app.providers.llm import METER, glimmer_provider, router_provider, spark_provider  # noqa: E402
from app.schemas import TURN_CLASSES, CapturedDoc, IntakeAnswers, ReplyPlan  # noqa: E402

MOCK = ROOT / "data" / "mock"


def load_cases() -> dict:
    data = json.loads((MOCK / "cases.json").read_text(encoding="utf-8"))["cases"]
    return {c["id"]: c for c in data}


def card_for(case: dict):
    a = IntakeAnswers(**{k: v for k, v in case.items() if k != "id"})
    card = intake.build_card(a)
    intake.approve(card, [f.id for f in card.all_facts()])
    return card


def pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(q * (len(xs) - 1))))
    return round(xs[k], 1)


# ---------------- router accuracy ----------------


async def eval_router(name: str, cases: dict, utts: list[dict]) -> dict:
    s = get_settings()
    if name == "spark" and s.use_fake:
        return {"router": name, "skipped": "no MODEL_API_KEY"}
    provider = router_provider(s, name)
    cards = {cid: card_for(c) for cid, c in cases.items()}
    correct, lat, conf = 0, [], Counter()
    per_class = defaultdict(lambda: [0, 0])
    errors = 0
    rows = []
    for u in utts:
        r = await route(u["text_ko"], cards[u["case"]], provider)
        if r.error and name != "rules":
            errors += 1
            if errors >= 3 and correct == 0:
                return {"router": name, "skipped": f"provider unreachable: {r.error}"}
        ok = r.turn_class == u["label"]
        correct += ok
        per_class[u["label"]][0] += ok
        per_class[u["label"]][1] += 1
        conf[(u["label"], r.turn_class)] += 1
        lat.append(r.latency_ms)
        rows.append({"id": u["id"], "label": u["label"], "pred": r.turn_class, "ok": ok})
    return {
        "router": name, "n": len(utts), "accuracy": round(correct / len(utts), 3),
        "per_class": {k: round(v[0] / v[1], 3) for k, v in per_class.items()},
        "latency_p50_ms": pct(lat, 0.5), "latency_p95_ms": pct(lat, 0.95),
        "api_calls": len(utts) if name == "spark" else 0, "errors": errors,
        "confusion": {f"{a}->{b}": n for (a, b), n in conf.items() if a != b}, "rows": rows,
    }


# ---------------- full visits (role-plays) ----------------


async def eval_visits(router_name: str, cases: dict) -> dict:
    s = get_settings()
    if s.use_fake:
        return {"router": router_name, "skipped": "no MODEL_API_KEY"}
    plays = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((MOCK / "roleplays").glob("*.json"))]
    stage = defaultdict(list)
    decisions = escalated = 0
    unsupported_after = 0
    audit_flagged = 0
    audit_failed = 0
    audit_rows = []
    blocked_before = 0
    replies = 0
    calls_per_visit = []
    glosses = gloss_flagged = 0
    gloss_rows = []
    for play in plays:
        sess = new_session(card_for(cases[play["case"]]), spark_provider(s), router_provider(s, router_name),
                           verifier_model=s.verifier_model_check)
        sess.set_consent(True)
        calls = 0
        for t in play["turns"]:
            events = await sess.clinician_turn(t["ko"])
            res = next((e for e in events if e["type"] == "turn_result"), None)
            if res is None:
                continue
            calls += res["spark_calls"]
            if res.get("clinician_said_patient_lang"):
                glosses += 1
                if res.get("gloss_check"):
                    gloss_flagged += 1
                    gloss_rows.append({"turn": t["ko"], "gloss": res["clinician_said_patient_lang"],
                                       "issues": res["gloss_check"]})
            for k in ("route", "respond", "verify", "total"):
                if res["latency_ms"].get(k) is not None:
                    stage[k].append(res["latency_ms"][k])
            if t["expect"] == "needs_decision":
                decisions += 1
                escalated += bool(res["ask_back"])
            reply = res["reply_ko"]
            if reply and reply not in FIXED_PHRASES:
                replies += 1
                plan = ReplyPlan(turn_class=res["turn_class"], reply_ko=reply,
                                 evidence=[e["id"] for e in res["evidence"]])
                unsupported_after += not check_rules(plan, sess.card).ok
                # Independent audit: a separate Spark call judges whether the spoken reply asserts
                # anything beyond its cited facts. Not part of the live path.
                audit = await check_model(plan, sess.card, spark_provider(s))
                if not audit.ok:
                    if any(r.startswith("rule5_check_failed") for r in audit.reasons):
                        audit_failed += 1
                    else:
                        audit_flagged += 1
                        audit_rows.append({"turn": t["ko"], "reply_ko": reply, "evidence": plan.evidence,
                                           "reason": audit.reasons})
            if res["ask_back"] and t.get("patient_answer"):
                out = await sess.patient_answer(res["ask_back"]["id"], t["patient_answer"])
                calls += 1 + (1 if s.verifier_model_check else 0)
                rr = out[0] if out and out[0].get("type") == "relay_result" else None
                if rr and rr.get("reply_ko") and not rr.get("blocked"):
                    replies += 1
                    plan = ReplyPlan(turn_class="on_card", reply_ko=rr["reply_ko"], evidence=[rr["fact_id"]])
                    audit = await check_model(plan, sess.card, spark_provider(s))
                    if not audit.ok and not any(r.startswith("rule5_check_failed") for r in audit.reasons):
                        audit_flagged += 1
                        audit_rows.append({"turn": t["patient_answer"], "reply_ko": rr["reply_ko"],
                                           "evidence": plan.evidence, "reason": audit.reasons})
                    elif not audit.ok:
                        audit_failed += 1
        blocked_before += len(sess.blocked_log)
        calls_per_visit.append(calls)
    return {
        "router": router_name, "visits": len(plays),
        "decision_escalation": f"{escalated}/{decisions}",
        "unsupported_claims_after_verifier": unsupported_after, "spoken_replies": replies,
        "audit_flagged": audit_flagged, "audit_failed": audit_failed, "audit_rows": audit_rows,
        "replies_blocked_by_verifier": blocked_before,
        "doctor_translations": glosses, "doctor_translations_flagged": gloss_flagged, "gloss_rows": gloss_rows,
        "latency_ms": {k: {"p50": pct(v, 0.5), "p95": pct(v, 0.95)} for k, v in stage.items()},
        "api_calls_per_visit_mean": round(statistics.mean(calls_per_visit), 2) if calls_per_visit else None,
    }


# ---------------- prescription fields ----------------


async def eval_rx(reader: str = "spark") -> dict:
    s = get_settings()
    if reader == "spark" and s.use_fake:
        return {"skipped": "no MODEL_API_KEY"}
    provider = spark_provider(s) if reader == "spark" else glimmer_provider(s, reader)
    rx = MOCK / "prescriptions"
    slips = json.loads((rx / "slips.json").read_text(encoding="utf-8"))["slips"]
    forms = json.loads((rx / "forms.json").read_text(encoding="utf-8"))["forms"]
    fields = ["drug_name_ko", "dose", "times_per_day", "days", "instructions_ko"]
    form_fields = fields + ["substitution_ko", "not_covered", "truncated"]
    out, lat = {}, []
    # labels, clean and as simulated phone photos; clinic forms (처방전) as phone photos
    runs = [("labels", slips, ".png", fields), ("labels_photo", slips, "_photo.jpg", fields),
            ("forms_photo", forms, "_photo.jpg", form_fields)]
    for name, docs, suffix, flds in runs:
        total = right = 0
        doc_ok = doc_total = 0
        for doc in docs:
            img = rx / f"{doc['id']}{suffix}"
            if not img.exists():
                return {"skipped": "run `make mock-docs` first"}
            t0 = time.perf_counter()
            reading = await documents.read_prescription(img.read_bytes(), "image/jpeg" if suffix.endswith("jpg")
                                                        else "image/png", "en", provider)
            lat.append((time.perf_counter() - t0) * 1000)
            for i, truth in enumerate(doc["items"]):
                got = reading.items[i].model_dump() if i < len(reading.items) else {}
                for f in flds:
                    want = truth.get("substitution") if f == "substitution_ko" else truth.get(f, False)
                    total += 1
                    right += _norm(got.get(f)) == _norm(want)
            if name == "forms_photo":
                checks = [reading.doc_kind == "prescription_form", reading.valid_days == doc["valid_days"],
                          reading.issued_date == doc["issued"], (reading.disease_code or None) == doc["disease_code"],
                          bool(reading.request_ko) == (doc["disease_code"] is None),
                          any(i.handwritten_note for i in reading.items) == any(x.get("handwritten") for x in doc["items"])]
                doc_ok += sum(checks)
                doc_total += len(checks)
        out[name] = {"docs": len(docs), "fields": total, "field_accuracy": round(right / total, 3) if total else None}
        if doc_total:
            out[name]["form_checks"] = f"{doc_ok}/{doc_total}"
    out["latency_p50_ms"] = pct(lat, 0.5)
    out["reader"] = f"{provider.name} ({provider.model})"
    return out


def _norm(v) -> str:
    return "".join(str(v or "").split())


# ---------------- claim completeness (deterministic) ----------------


def eval_claims() -> dict:
    sets = json.loads((MOCK / "claims" / "sets.json").read_text(encoding="utf-8"))["sets"]
    ok = 0
    rows = []
    for st in sets:
        missing = documents.compute_missing(st["required_docs"], [CapturedDoc(**c) for c in st["captured"]],
                                            st["have"])
        match = sorted(missing) == sorted(st["expected_missing"])
        ok += match
        rows.append({"id": st["id"], "match": match, "missing": missing, "expected": st["expected_missing"]})
    return {"sets": len(sets), "exact_match": f"{ok}/{len(sets)}", "rows": rows}


# ---------------- report ----------------


def to_markdown(r: dict) -> str:
    L = ["# Medero evaluation results", "",
         f"Generated {r['generated_at']} · models: {'FAKE (no key) – model sections skipped' if r['fake'] else r['spark_model']}",
         "", "> All data is **MOCK** (invented cases and utterances, written by the developer). "
             "Korean utterances await native-speaker review. Numbers below are measured, not estimated.", ""]
    L += ["## Router accuracy", "", "| Router | n | Accuracy | p50 ms | p95 ms | API calls |", "|---|---|---|---|---|---|"]
    for x in r["router"]:
        if "skipped" in x:
            L.append(f"| {x['router']} | – | skipped: {x['skipped']} | | | |")
        else:
            L.append(f"| {x['router']} | {x['n']} | {x['accuracy']:.1%} | {x['latency_p50_ms']} | "
                     f"{x['latency_p95_ms']} | {x['api_calls']} |")
    for x in r["router"]:
        if "per_class" in x:
            L += ["", f"**{x['router']} per class:** " + ", ".join(f"{k} {v:.0%}" for k, v in sorted(x["per_class"].items()))]
            if x["confusion"]:
                L.append(f"Confusions: " + ", ".join(f"{k} ×{n}" for k, n in sorted(x["confusion"].items())))
    L += ["", "## Full visits (role-plays)", ""]
    for v in r["visits"]:
        if "skipped" in v:
            L.append(f"- router **{v['router']}**: skipped ({v['skipped']})")
            continue
        L += [f"### Router: {v['router']}", "",
              f"- Visits: {v['visits']}",
              f"- Decision escalation (needs_decision -> ask-back): **{v['decision_escalation']}**",
              f"- Spoken replies (excluding fixed phrases): {v['spoken_replies']}",
              f"- Independent Spark audit flagged as unsupported: **{v['audit_flagged']}** of {v['spoken_replies']}"
              + (f" (audit call failed on {v['audit_failed']})" if v['audit_failed'] else ""),
              f"- Replies blocked by the verifier (became ask-backs): {v['replies_blocked_by_verifier']}",
              f"- Doctor's words translated for the patient: {v.get('doctor_translations')}, flagged by the "
              f"number/negation check: {v.get('doctor_translations_flagged')}",
              f"- Meta API calls per visit (mean): {v['api_calls_per_visit_mean']}", "",
              "| Stage | p50 ms | p95 ms |", "|---|---|---|"]
        for k, s in v["latency_ms"].items():
            L.append(f"| {k} | {s['p50']} | {s['p95']} |")
        L.append("")
    L += ["## Prescription fields (exact match, MOCK)", ""]
    names = {"labels": "Medicine-bag labels, clean", "labels_photo": "Medicine-bag labels, simulated phone photo",
             "forms_photo": "Clinic prescription forms (처방전), simulated phone photo"}
    for reader, rx in r["prescription"].items():
        if "skipped" in rx:
            L.append(f"- {reader}: skipped: {rx['skipped']}")
            continue
        L += [f"**Reader: {rx['reader']}** · latency p50 {rx['latency_p50_ms']} ms", "",
              "| Set | Docs | Fields | Accuracy | Form checks |", "|---|---|---|---|---|"]
        for k, n in names.items():
            if k in rx:
                x = rx[k]
                L.append(f"| {n} | {x['docs']} | {x['fields']} | {format(x['field_accuracy'], '.1%')} | {x.get('form_checks', '—')} |")
        L.append("")
    L.append("Form checks: document kind, valid-for days, issue date, disease code, disease-code request shown "
             "only when the box is blank, handwritten note detected.")
    L += ["", "## Claim completeness (deterministic matcher)", "",
          f"- `missing` matched the known gaps in **{r['claims']['exact_match']}** MOCK receipt sets", ""]
    L += ["## Not measured here", "", "- Transcription quality: spot-check recorded role-plays by hand (see docs/api-notes.md).", ""]
    return "\n".join(L)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--routers", default="rules,spark")
    ap.add_argument("--visit-routers", default=None, help="routers for full visits (default: same, minus rules)")
    ap.add_argument("--no-rx", action="store_true")
    ap.add_argument("--rx-readers", default="spark", help="spark, local (Glimmer on this Mac), modal")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results"))
    args = ap.parse_args()
    s = get_settings()
    cases = load_cases()
    utts = [json.loads(l) for l in (MOCK / "utterances.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert all(u["label"] in TURN_CLASSES for u in utts)
    routers = [x for x in args.routers.split(",") if x]
    visit_routers = [x for x in (args.visit_routers or "rules").split(",") if x]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fake": s.use_fake, "spark_model": s.spark_model,
        "router": [await eval_router(n, cases, utts) for n in routers],
        "visits": [await eval_visits(n, cases) for n in visit_routers],
        "prescription": {"spark": {"skipped": "--no-rx"}} if args.no_rx else
                        {r: await eval_rx(r) for r in args.rx_readers.split(",") if r},
        "claims": eval_claims(),
        "meter": {"calls": METER.calls, "input_tokens": METER.input_tokens, "output_tokens": METER.output_tokens,
                  "est_cost_usd": METER.est_cost_usd(s)},
    }
    out = Path(args.out)
    if s.use_fake and out.resolve() == (ROOT / "eval" / "results").resolve():
        out = ROOT / "eval" / "results" / "offline"  # never overwrite measured results with FAKE ones
        print("no MODEL_API_KEY: writing to", out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "latest.md").write_text(to_markdown(result), encoding="utf-8")
    print(to_markdown(result))


if __name__ == "__main__":
    asyncio.run(main())
