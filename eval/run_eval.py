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
from app.pipeline.verifier import FIXED_PHRASES, check_rules  # noqa: E402
from app.pipeline.visit import new_session  # noqa: E402
from app.providers.llm import METER, router_provider, spark_provider  # noqa: E402
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
    blocked_before = 0
    replies = 0
    calls_per_visit = []
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
            if res["ask_back"] and t.get("patient_answer"):
                out = await sess.patient_answer(res["ask_back"]["id"], t["patient_answer"])
                calls += 1 + (1 if s.verifier_model_check else 0)
                _ = out
        blocked_before += len(sess.blocked_log)
        calls_per_visit.append(calls)
    return {
        "router": router_name, "visits": len(plays),
        "decision_escalation": f"{escalated}/{decisions}",
        "unsupported_claims_after_verifier": unsupported_after, "spoken_replies": replies,
        "replies_blocked_by_verifier": blocked_before,
        "latency_ms": {k: {"p50": pct(v, 0.5), "p95": pct(v, 0.95)} for k, v in stage.items()},
        "api_calls_per_visit_mean": round(statistics.mean(calls_per_visit), 2) if calls_per_visit else None,
    }


# ---------------- prescription fields ----------------


async def eval_rx() -> dict:
    s = get_settings()
    if s.use_fake:
        return {"skipped": "no MODEL_API_KEY"}
    slips = json.loads((MOCK / "prescriptions" / "slips.json").read_text(encoding="utf-8"))["slips"]
    fields = ["drug_name_ko", "dose", "times_per_day", "days", "instructions_ko"]
    total = right = 0
    lat = []
    for slip in slips:
        img = MOCK / "prescriptions" / f"{slip['id']}.png"
        if not img.exists():
            return {"skipped": "run `make mock-docs` first"}
        t0 = time.perf_counter()
        reading = await documents.read_prescription(img.read_bytes(), "image/png", "en", spark_provider(s))
        lat.append((time.perf_counter() - t0) * 1000)
        for i, truth in enumerate(slip["items"]):
            got = reading.items[i].model_dump() if i < len(reading.items) else {}
            for f in fields:
                total += 1
                right += _norm(got.get(f)) == _norm(truth[f])
    return {"slips": len(slips), "fields": total, "field_accuracy": round(right / total, 3) if total else None,
            "latency_p50_ms": pct(lat, 0.5)}


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
              f"- Unsupported claims after verifier: **{v['unsupported_claims_after_verifier']}** "
              f"of {v['spoken_replies']} spoken replies",
              f"- Replies blocked by the verifier (became ask-backs): {v['replies_blocked_by_verifier']}",
              f"- Meta API calls per visit (mean): {v['api_calls_per_visit_mean']}", "",
              "| Stage | p50 ms | p95 ms |", "|---|---|---|"]
        for k, s in v["latency_ms"].items():
            L.append(f"| {k} | {s['p50']} | {s['p95']} |")
        L.append("")
    rx = r["prescription"]
    L += ["## Prescription fields", "",
          f"- {'skipped: ' + rx['skipped'] if 'skipped' in rx else str(rx['fields']) + ' fields on ' + str(rx['slips']) + ' MOCK slips, exact-match accuracy ' + format(rx['field_accuracy'], '.1%')}",
          "", "## Claim completeness (deterministic matcher)", "",
          f"- `missing` matched the known gaps in **{r['claims']['exact_match']}** MOCK receipt sets", ""]
    L += ["## Not measured here", "", "- Transcription quality: spot-check recorded role-plays by hand (see docs/api-notes.md).", ""]
    return "\n".join(L)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--routers", default="rules,spark")
    ap.add_argument("--visit-routers", default=None, help="routers for full visits (default: same, minus rules)")
    ap.add_argument("--no-rx", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results"))
    args = ap.parse_args()
    s = get_settings()
    cases = load_cases()
    utts = [json.loads(l) for l in (MOCK / "utterances.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert all(u["label"] in TURN_CLASSES for u in utts)
    routers = [x for x in args.routers.split(",") if x]
    visit_routers = [x for x in (args.visit_routers or ",".join(r for r in routers if r != "rules") or "spark").split(",") if x]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fake": s.use_fake, "spark_model": s.spark_model,
        "router": [await eval_router(n, cases, utts) for n in routers],
        "visits": [await eval_visits(n, cases) for n in visit_routers],
        "prescription": {"skipped": "--no-rx"} if args.no_rx else await eval_rx(),
        "claims": eval_claims(),
        "meter": {"calls": METER.calls, "input_tokens": METER.input_tokens, "output_tokens": METER.output_tokens,
                  "est_cost_usd": METER.est_cost_usd(s)},
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "latest.md").write_text(to_markdown(result), encoding="utf-8")
    print(to_markdown(result))


if __name__ == "__main__":
    asyncio.run(main())
