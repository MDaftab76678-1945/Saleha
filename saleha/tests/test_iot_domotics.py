import pytest

from saleha.core.iot_domotics import FocusEnvironmentState, IoTDomoticsEngine


def test_focus_environment_state():
    # Test the FocusEnvironmentState class with a realistic input
    state = FocusEnvironmentState(
        is_deep_focus_active=True,
        ambient_color_hex="#38bdf8",  # Cyberpunk Neon Cyan
        brightness_percent=35,        # Dim ambient room
        audio_preset="LO_FI_SYNTHWAVE",
        notifications_muted=True,
    )
    
    assert state.is_deep_focus_active == True
    assert state.ambient_color_hex == "#38bdf8"
    assert state.brightness_percent == 35
    assert state.audio_preset == "LO_FI_SYNTHWAVE"
    assert state.notifications_muted == True


def test_trigger_cyberpunk_focus_mode():
    # Test the trigger_cyberpunk_focus_mode method with a realistic input
    iot_engine = IoTDomoticsEngine()
    
    result = iot_engine.trigger_cyberpunk_focus_mode(active=True)
    
    assert result.is_deep_focus_active == True
    assert result.ambient_color_hex == "#38bdf8"
    assert result.brightness_percent == 35
    assert result.audio_preset == "LO_FI_SYNTHWAVE"
    assert result.notifications_muted == True


def test_set_device_state():
    # Test the set_device_state method with a realistic input
    iot_engine = IoTDomoticsEngine()
    
    device_id = "bedroom_light"
    state = "ON"
    
    response = iot_engine.set_device_state(device_id, state)
    
    assert response["device_id"] == device_id
    assert response["state"] == state.upper()
    assert response["mqtt_topic"] == f"saleha/home/{device_id}"
    assert response["status"] == "PUBLISHED"