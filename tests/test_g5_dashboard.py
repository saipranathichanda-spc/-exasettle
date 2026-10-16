"""
Gate G5 Verification Tests: Dashboard API, Live State Transitions & Panel Separation
"""

from starlette.testclient import TestClient
from exasettle.dashboard.app import app

client = TestClient(app)


def test_dashboard_health_endpoint():
    """Verify health endpoint returns valid preflight statuses."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "timestamp_utc" in data
    assert len(data["services"]) == 5


def test_dashboard_run_and_status_transitions():
    """Verify running a scenario triggers status progression and produces valid results."""
    run_payload = {
        "scenario_id": "SCN_CORE_8PACK",
        "seed": 42,
        "extra_matched_count": 0,
        "settlement_delay_threshold_hours": 24,
        "engine_preference": "FALLBACK",
        "simulation_mode": "PRERECORDED"
    }

    resp = client.post("/api/run", json=run_payload)
    assert resp.status_code == 200
    data = resp.json()

    run_id = data["report_metadata"]["run_id"]
    assert run_id.startswith("run_")
    assert data["reconciliation_summary"]["total_transactions"] >= 8
    assert data["reconciliation_summary"]["ground_truth_accuracy"]["accuracy_percent"] == 100.0

    # Test evidence retrieval
    evidence_resp = client.get(f"/api/evidence/{run_id}/TXN_SYN_101")
    assert evidence_resp.status_code == 200
    ev_data = evidence_resp.json()
    assert ev_data["transaction_id"] == "TXN_SYN_101"
    assert ev_data["reconciliation_result"]["classification"] == "MATCHED"
    assert "RULE_CLEAN_MATCH" in ev_data["reconciliation_result"]["applied_rule"]

    # Test separation of simulation outputs
    assert "simulation_events" in ev_data
    assert len(ev_data["simulation_events"]) == 3
    for ev in ev_data["simulation_events"]:
        assert ev["simulation_label"] == "AI-simulated scenario — not real customer feedback"
        assert ev["status"] == "PRERECORDED"

    # Test CSV export endpoint
    csv_resp = client.get(f"/api/export/csv/{run_id}")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "TXN_SYN_101" in csv_resp.text

    # Test JSON export endpoint
    json_resp = client.get(f"/api/export/json/{run_id}")
    assert json_resp.status_code == 200
    assert "application/json" in json_resp.headers["content-type"]
    assert json_resp.json()["report_metadata"]["run_id"] == run_id


def test_static_dashboard_html_served():
    """Verify index.html is served with title and disclosure bar."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ExaSettle" in resp.text
    assert "AI-simulated scenario" in resp.text
    assert "ExaThon India 2026" in resp.text
