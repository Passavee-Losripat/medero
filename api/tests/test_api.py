import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

DEMO = json.loads((Path(__file__).resolve().parents[2] / "data/mock/demo_case.json").read_text())
client = TestClient(app)


def _intake():
    body = {k: v for k, v in DEMO.items() if not k.startswith("_")}
    r = client.post("/intake", json=body)
    assert r.status_code == 200
    return r.json()


def test_health():
    assert client.get("/health").json()["fake_models"] is True


def test_intake_approve_visit_delete():
    data = _intake()
    sid = data["session_id"]
    ids = [f["id"] for f in [data["card"]["chief_complaint"], *data["card"]["symptoms"]]]
    r = client.post(f"/sessions/{sid}/approve", json={"approved_ids": ids + ["allergy"]})
    card = r.json()["card"]
    assert "allergy" not in card["may_answer"]
    assert card["chief_complaint"]["value_ko"]

    with client.websocket_connect(f"/sessions/{sid}/visit") as ws:
        ws.send_json({"type": "start"})
        assert ws.receive_json()["type"] == "disclosure"
        ws.send_json({"type": "consent", "accepted": True})
        assert ws.receive_json()["accepted"] is True
        ws.send_json({"type": "clinician_text", "text": "며칠 됐어요?"})
        assert ws.receive_json()["type"] == "transcript"
        res = ws.receive_json()
        assert res["type"] == "turn_result" and res["turn_class"] == "on_card"
        ws.send_json({"type": "summary"})
        assert ws.receive_json()["type"] == "summary"

    assert client.delete(f"/sessions/{sid}").json()["deleted"]
    assert client.get(f"/sessions/{sid}").status_code == 404


def test_consent_declined():
    sid = _intake()["session_id"]
    with client.websocket_connect(f"/sessions/{sid}/visit") as ws:
        ws.send_json({"type": "consent", "accepted": False})
        e = ws.receive_json()
        assert e["accepted"] is False and e["text_ko"]


def test_intake_emergency_returns_static_card():
    r = client.post("/intake", json={"chief_complaint": "severe bleeding from my arm"})
    assert r.json()["emergency"] is True
    assert r.json()["card"]["numbers"][0]["number"] == "119"


def test_insurance_pack_missing_and_card_slip():
    r = client.post("/insurance/pack", json={
        "required_docs": ["claim form", "itemized expense statement", "pharmacy receipt (card slips not accepted)"],
        "captured": [{"type": "card payment slip", "amount": "8,000"},
                     {"type": "itemized expense statement", "date": "2026-10-31"}],
        "have": ["claim form"],
    })
    body = r.json()
    assert body["missing"] == ["pharmacy receipt (card slips not accepted)"]
    assert "[your full name]" in body["draft_message"]


def test_before_leaving_only_for_claim_later_cover():
    from app import fixed_text as fx
    assert fx.before_leaving("travel")["request_ko"] == fx.DISEASE_CODE_REQUEST_KO
    assert fx.before_leaving("unknown") is not None
    assert fx.before_leaving("nhis") is None and fx.before_leaving("none") is None


def test_find_maps_body_part_to_department_never_ranks():
    from app.pipeline.find import suggest
    r = suggest("my eye hurts")
    assert [d["ko"] for d in r["suggested"]] == ["안과"]
    assert set(r["suggested"][0]["links"]) == {"naver", "kakao", "google"}
    assert suggest("near the station")["suggested"] == []          # "ear" must not match inside "near"
    assert suggest("หลังอาหาร")["suggested"] == []                   # "after meals", not back pain
    assert suggest("아이가 열이 나요")["suggested"][0]["ko"] == "소아청소년과"
    assert suggest("chest pain")["emergency"] is True


def test_find_endpoint():
    r = client.get("/find", params={"q": "twisted ankle", "lang": "th"}).json()
    assert r["suggested"][0]["ko"] == "정형외과" and r["suggested"][0]["name"] == "กระดูกและข้อ"
