import re

from saleha.core.nexus_mobile_bridge import MobileCommandResponse, NexusMobileBridge


def test_status_reports_real_system_numbers() -> None:
    import psutil

    response = NexusMobileBridge().process_incoming_mobile_message("100293849", "status")
    assert isinstance(response, MobileCommandResponse)
    assert response.command == "status"
    assert response.execution_success
    assert isinstance(response.timestamp, float)
    match = re.fullmatch(r"CPU: \d+% \| RAM: ([\d.]+)GB / ([\d.]+)GB", response.reply_text)
    assert match, response.reply_text
    # The old reply was the constant "3.2GB / 16GB" whatever the machine was.
    assert abs(float(match.group(2)) - psutil.virtual_memory().total / 1024 ** 3) < 0.1


def test_unregistered_chat_id_is_rejected() -> None:
    response = NexusMobileBridge().process_incoming_mobile_message("999", "status")
    assert not response.execution_success
    assert "Unauthorized" in response.reply_text
    assert "CPU" not in response.reply_text


def test_commands_that_do_nothing_are_not_acknowledged() -> None:
    bridge = NexusMobileBridge()
    for cmd in ("deploy", "shutdown", "benchmark", "do something"):
        response = bridge.process_incoming_mobile_message("100293849", cmd)
        assert not response.execution_success, cmd
        assert "Unsupported" in response.reply_text
        assert "netlify" not in response.reply_text.lower()


def test_format_intruder_push_alert() -> None:
    alert = NexusMobileBridge().format_intruder_push_alert("John Doe")
    assert isinstance(alert, dict)
    assert {"title", "body", "priority", "timestamp"} <= set(alert)
    assert "locked" not in alert["body"].lower()
