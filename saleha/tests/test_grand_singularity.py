"""
Master Test Suite for Saleha Grand Unified Singularity:
1. Vision & Biometric Liveness Sentinel (EAR Anti-Spoofing & Game Mode)
2. Full-Duplex Voice & Echo-Free Audio Semaphore
3. Sentinel-RS 2.0 Bare-Metal Network Scanner
4. DooM Vault 2.0 Multi-Chain FinTech & Whale Radar
5. Mukti Hallucination Insurance & Agent Economy
6. UNIMAX Silicon Co-Simulator & Ouroboros Zeroize
7. Nexus Mobile Mainframe Bridge
8. IoT Domotics & Cyberpunk Flow Mode
"""

import unittest
from saleha.core.vision_liveness import vision_liveness_engine, EyeLandmarks
from saleha.core.full_duplex_voice import full_duplex_voice
from saleha.core.sentinel_rs import sentinel_rs_engine
from saleha.core.doom_vault import doom_vault_engine
from saleha.core.mukti_economy import mukti_economy_engine
from saleha.core.unimax_bridge import unimax_bridge_engine
from saleha.core.nexus_mobile_bridge import nexus_mobile_bridge
from saleha.core.iot_domotics import iot_domotics_engine


class GrandSingularityTests(unittest.TestCase):

    # 1. Vision & Liveness Anti-Spoofing
    def test_vision_ear_liveness_and_game_mode(self):
        # Open Eye
        open_eye = EyeLandmarks(
            p1=(0, 0), p2=(2, 2), p3=(4, 2), p4=(6, 0), p5=(4, -2), p6=(2, -2)
        )
        ear_open = vision_liveness_engine.calculate_ear(open_eye)
        self.assertGreater(ear_open, 0.3)

        # Closed / Blink Eye
        closed_eye = EyeLandmarks(
            p1=(0, 0), p2=(2, 0.2), p3=(4, 0.2), p4=(6, 0), p5=(4, -0.2), p6=(2, -0.2)
        )
        ear_closed = vision_liveness_engine.calculate_ear(closed_eye)
        self.assertLess(ear_closed, 0.2)

        res = vision_liveness_engine.process_eye_frame(open_eye, is_admin_face=True)
        self.assertTrue(res.is_live_human)
        self.assertFalse(res.intruder_detected)

        # Game mode check
        self.assertTrue(vision_liveness_engine.check_game_mode(["chrome.exe", "VALORANT.exe"]))
        self.assertFalse(vision_liveness_engine.check_game_mode(["code.exe", "python.exe"]))

    # 2. Full-Duplex Voice & Audio Semaphore
    def test_full_duplex_voice_semaphore_and_bargein(self):
        full_duplex_voice.start_speaking("Hello Commander")
        self.assertTrue(full_duplex_voice.is_speaking)

        # User interrupts while AI is speaking
        interrupted = full_duplex_voice.handle_user_barge_in(user_audio_energy=0.85)
        self.assertTrue(interrupted)
        self.assertFalse(full_duplex_voice.is_speaking)

    # 3. Sentinel-RS Bare-Metal Scanner
    def test_sentinel_rs_port_scanning(self):
        res = sentinel_rs_engine.scan_target("127.0.0.1", ports=[80, 443, 8000])
        self.assertEqual(res.target_host, "127.0.0.1")
        self.assertLess(res.scan_duration_ms, 2000.0)

    # 4. DooM Vault 2.0 FinTech & Whale Radar
    def test_doom_vault_trading_and_whale_radar(self):
        prices = doom_vault_engine.get_ticker_prices()
        self.assertIn("BTC", prices)
        self.assertGreater(prices["BTC"], 50000.0)

        whale = doom_vault_engine.detect_whale_movement("BTC", 3500000.0)
        self.assertEqual(whale.risk_level, "MEDIUM")

        order = doom_vault_engine.execute_paper_trade("ETH", "BUY", 2.0)
        self.assertEqual(order.status, "FILLED")
        self.assertEqual(order.symbol, "ETH")

    # 5. Mukti Hallucination Insurance
    def test_mukti_hallucination_insurance_lifecycle(self):
        policy = mukti_economy_engine.create_insurance_policy(
            client_address="0xClient123",
            agent_address="0xAgent456",
            code="def add(a, b): return a + b",
            stake_amount=500.0,
        )
        self.assertEqual(policy.status, "ACTIVE")

        # Code is valid -> bond released
        settled = mukti_economy_engine.settle_insurance_claim(policy.policy_id, is_ast_valid=True)
        self.assertEqual(settled.status, "BOND_RELEASED_VERIFIED")

    # 6. UNIMAX Quantum Co-Simulator & Ouroboros Kill-Switch
    def test_unimax_quantum_and_ouroboros_zeroize(self):
        unimax_bridge_engine.apply_quantum_gate(0, "H")
        unimax_bridge_engine.apply_quantum_gate(0, "X")
        rep = unimax_bridge_engine.measure_quantum_state(0)
        self.assertEqual(rep.num_qubits, 64)
        self.assertGreater(rep.active_gates_applied, 0)

        vcd = unimax_bridge_engine.generate_vcd_waveform_trace(clock_cycles=4)
        self.assertIn("$timescale 1ns", vcd)

        zeroize = unimax_bridge_engine.trigger_ouroboros_zeroize()
        self.assertTrue(zeroize.hardware_killswitch_asserted)
        self.assertTrue(zeroize.all_domains_zeroized)

    # 7. Nexus Mobile Mainframe Bridge
    def test_nexus_mobile_bridge_dispatch(self):
        resp = nexus_mobile_bridge.process_incoming_mobile_message("100293849", "status")
        self.assertTrue(resp.execution_success)
        self.assertIn("CPU", resp.reply_text)

        alert = nexus_mobile_bridge.format_intruder_push_alert("Unknown Subject")
        self.assertEqual(alert["priority"], "HIGH")

    # 8. IoT Domotics & Focus Flow Mode
    def test_iot_domotics_focus_flow(self):
        flow = iot_domotics_engine.trigger_cyberpunk_focus_mode(active=True)
        self.assertTrue(flow.is_deep_focus_active)
        self.assertEqual(flow.ambient_color_hex, "#38bdf8")

        dev = iot_domotics_engine.set_device_state("studio_neon", "ON")
        self.assertEqual(dev["state"], "ON")


if __name__ == "__main__":
    unittest.main()

