from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_websocket_connection() -> None:
    with client.websocket_connect("/ws") as websocket:
        connected = websocket.receive_json()

        assert connected["event_type"] == "core.connected"
        assert connected["payload"]["status"] == "online"

        websocket.send_text("cybertron-test")

        echo = websocket.receive_json()

        assert echo["event_type"] == "core.echo"
        assert echo["payload"]["message"] == "cybertron-test"
