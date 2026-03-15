from fastapi.testclient import TestClient

from citypulse.main import app

client = TestClient(app)


def test_root_redirects_to_ui():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in {302, 307}
    assert response.headers["location"] == "/ui"


def test_ui_page_available():
    response = client.get("/ui")
    assert response.status_code == 200
    assert "CityPulse Dashboard" in response.text


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_latest_snapshot_shape():
    response = client.get("/v1/snapshots/latest")
    assert response.status_code == 200
    payload = response.json()
    assert "kpi" in payload
    assert 0 <= payload["kpi"]["city_pulse_index"] <= 100


def test_snapshots_hours_limit():
    response = client.get("/v1/snapshots", params={"hours": 4})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 4


def test_incidents_filtering():
    response = client.get("/v1/incidents/open", params={"min_severity": "high"})
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert all(item["severity"] in {"high", "critical"} for item in payload)


def test_manual_incident_resolve():
    open_response = client.get("/v1/incidents/open")
    assert open_response.status_code == 200
    open_payload = open_response.json()
    assert open_payload

    incident_id = open_payload[0]["id"]
    resolve_response = client.post(f"/v1/incidents/{incident_id}/resolve")
    assert resolve_response.status_code == 200
    assert resolve_response.json()["status"] == "resolved"

    after_response = client.get("/v1/incidents/open")
    assert after_response.status_code == 200
    after_payload = after_response.json()
    assert all(item["id"] != incident_id for item in after_payload)


def test_manual_incident_resolve_not_found():
    response = client.post("/v1/incidents/INC-DOES-NOT-EXIST/resolve")
    assert response.status_code == 404


def test_events_recent_shape():
    response = client.get("/v1/events/recent", params={"limit": 10, "active_seconds": 180})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) <= 10
    if payload:
        first = payload[0]
        assert "id" in first
        assert "kind" in first
        assert "message" in first
        assert "created_at" in first


def test_incident_recommendations_shape():
    response = client.get("/v1/incidents/recommendations", params={"min_severity": "medium"})
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    if payload:
        first = payload[0]
        assert "recommended_team" in first
        assert "sla_minutes" in first
        assert isinstance(first["actions"], list)


def test_analytics_overview_shape():
    response = client.get("/v1/analytics/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] in {"normal", "warning", "critical"}
    assert payload["open_incidents"] >= payload["critical_incidents"]


def test_analytics_trends_shape():
    response = client.get("/v1/analytics/trends", params={"hours": 12})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 4
    assert all(item["direction"] in {"up", "down", "stable"} for item in payload)


def test_analytics_report_shape_and_reliability_range():
    response = client.get("/v1/analytics/report", params={"hours": 12})
    assert response.status_code == 200
    payload = response.json()
    assert payload["window_hours"] == 12
    assert payload["min_index"] <= payload["average_index"] <= payload["max_index"]
    assert len(payload["domain_pressure"]) == 3

    latest = client.get("/v1/snapshots/latest")
    assert latest.status_code == 200
    reliability = latest.json()["kpi"]["reliability_score"]
    assert 0 <= reliability <= 100
