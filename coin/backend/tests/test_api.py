from fastapi.testclient import TestClient

from api.routes import get_broker, required_mandate
from main import app
from tests.test_firewall import FakeBroker, mandate, proposal


def test_account_review_and_manual_execution_routes():
    broker = FakeBroker()
    app.dependency_overrides[get_broker] = lambda: broker
    app.dependency_overrides[required_mandate] = lambda: mandate()
    try:
        client = TestClient(app)
        assert client.get("/api/account").json()["positions"] == []
        trade = proposal().model_dump(mode="json")
        verdict = client.post("/api/validate", json=trade).json()["verdict"]
        assert verdict["passed"] is True
        waiting = client.post("/api/execute", json={"proposal": trade}).json()
        assert waiting["status"] == "awaiting_approval"
        assert broker.orders == []
        submitted = client.post("/api/execute", json={"proposal": trade, "approved": True}).json()
        assert submitted["status"] == "submitted"
        assert len(broker.orders) == 1
    finally:
        app.dependency_overrides.clear()
