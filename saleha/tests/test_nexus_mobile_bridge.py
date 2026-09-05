import pytest

from saleha.core.nexus_mobile_bridge import MobileCommandResponse, NexusMobileBridge


def test_process_incoming_mobile_message():
    bridge = NexusMobileBridge()
    response = bridge.process_incoming_mobile_message("100293849", "status")
    assert isinstance(response, MobileCommandResponse)
    assert response.command == "status"
    assert response.reply_text.startswith("🔋 CPU: 12% | 💾 RAM: 3.2GB / 16GB | 🟢 Swarm: 250 Agents Active")
    assert response.execution_success
    assert isinstance(response.timestamp, float)


def test_format_intruder_push_alert():
    bridge = NexusMobileBridge()
    alert = bridge.format_intruder_push_alert("John Doe")
    assert isinstance(alert, dict)
    assert "title" in alert
    assert "body" in alert
    assert "priority" in alert
    assert "timestamp" in alert