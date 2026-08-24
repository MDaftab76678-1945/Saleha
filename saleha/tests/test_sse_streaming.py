import unittest
import io
from unittest.mock import patch, MagicMock

from saleha.server import web_server
from saleha.server.web_server import SalehaAPIHandler
from saleha.core.team_orchestrator import TeamResult


class SSEStreamingTests(unittest.TestCase):
    def test_sse_event_formatting_and_route(self):
        web_server.set_auth_token("sse-test-token")
        handler = SalehaAPIHandler.__new__(SalehaAPIHandler)
        handler.wfile = io.BytesIO()
        handler.path = "/api/stream/team?goal=Build+Cache"
        handler.headers = {"X-Saleha-Token": "sse-test-token"}

        captured_callbacks = []

        def fake_workflow(goal=None, on_event=None, **kwargs):
            # Real orchestrator ki tarah har stage par on_event fire karo --
            # yahi REAL streaming ka contract hai. Route ne callback pass kiya
            # ye bhi verify hota hai.
            if on_event:
                captured_callbacks.append(on_event)
                for stage_name in (
                    "Product Manager (PRD)",
                    "Software Designer (LLD Architecture)",
                    "Senior SDE (Implementation)",
                ):
                    on_event({"stage": stage_name, "content": f"{stage_name} content", "stage_index": 1})
            return TeamResult(
                success=True, goal="Build Cache", stages_completed=["prd", "arch", "code"],
                prd="PRD Spec Doc", design="Architecture LLD", code="def hello(): pass",
                security_report="Clean", test_code="def test_hello(): pass", attempts=1
            )

        with patch.object(handler, "send_response") as mock_resp, \
             patch.object(handler, "send_header") as mock_header, \
             patch.object(handler, "end_headers") as mock_end, \
             patch("saleha.server.web_server.TeamOrchestrator") as mock_orch_cls:

            mock_orch = MagicMock()
            mock_orch.run_team_workflow.side_effect = fake_workflow
            mock_orch_cls.return_value = mock_orch

            handler.do_GET()

            mock_resp.assert_called_with(200)
            self.assertEqual(len(captured_callbacks), 1)  # route ne on_event diya
            output = handler.wfile.getvalue().decode("utf-8")
            self.assertIn("data:", output)
            self.assertIn("Product Manager (PRD)", output)
            self.assertIn("Senior SDE (Implementation)", output)
            self.assertIn("Complete", output)


if __name__ == "__main__":
    unittest.main()
