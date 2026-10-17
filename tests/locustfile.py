"""
Locust load test script for ExaSettle.
Tests concurrent throughput, response latency, and error rates at 10, 50, and 100 users.
"""

from locust import HttpUser, task, between


class ExaSettleUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(3)
    def test_health(self):
        self.client.get("/api/health")

    @task(2)
    def test_monthly_analytics(self):
        self.client.get("/api/analytics/monthly")

    @task(1)
    def test_reconciliation_run(self):
        payload = {
            "scenario_id": "SCN_CORE_8PACK",
            "seed": 42,
            "engine_preference": "FALLBACK",
            "simulation_mode": "PRERECORDED"
        }
        resp = self.client.post("/api/run", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            run_id = data.get("report_metadata", {}).get("run_id")
            if run_id:
                self.client.get(f"/api/export/json/{run_id}")
