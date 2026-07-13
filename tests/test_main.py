from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_workspace_registry_and_provider_status():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["workspaces"]) == {"texhoma", "acesn8s_dev", "personal_investments"}
    assert body["clients"] == ["texhoma"]
    assert "ollama" in body["providers"]
    assert "anthropic" in body["providers"]


def test_tasks_rejects_unknown_workspace():
    resp = client.post(
        "/tasks", json={"workspace": "not_a_real_workspace", "task_type": "draft", "payload": {}}
    )
    assert resp.status_code == 422
