"""Real Vision backend tests (mocked HTTP -- deterministic)."""
import base64
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from saleha.core import vision_backend
from saleha.core.vision_backend import (
    find_vision_model,
    generate_code_from_image,
    load_image_b64,
)
from saleha.core.vision_coder import VisionCoder


class LoadImageTests(unittest.TestCase):
    def test_file_path_loads_base64(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"pixeldata" * 10)
            path = f.name
        try:
            b64, note = load_image_b64(path)
            self.assertEqual(base64.b64decode(b64)[:4], b"\x89PNG")
            self.assertIn("file:", note)
        finally:
            os.remove(path)

    def test_data_url_parsed(self):
        raw = base64.b64encode(b"imgbytes").decode()
        b64, note = load_image_b64(f"data:image/png;base64,{raw}")
        self.assertEqual(base64.b64decode(b64), b"imgbytes")
        self.assertEqual(note, "data-url")

    def test_raw_base64_accepted(self):
        raw = base64.b64encode(b"x" * 20).decode()
        b64, note = load_image_b64(raw)
        self.assertEqual(note, "raw-base64")

    def test_garbage_rejected(self):
        with self.assertRaises(ValueError):
            load_image_b64("")
        with self.assertRaises(ValueError):
            load_image_b64("not-a-file-or-base64!!!")


class FindVisionModelTests(unittest.TestCase):
    def test_prefers_installed_vision_model(self):
        with patch("saleha.core.smart_router.get_installed_ollama_models",
                   return_value={"qwen2.5-coder:7b", "llava:13b"}):
            self.assertEqual(find_vision_model(), "llava:13b")

    def test_none_when_only_text_models(self):
        with patch("saleha.core.smart_router.get_installed_ollama_models",
                   return_value={"qwen2.5-coder:7b", "deepseek-r1:8b"}):
            self.assertIsNone(find_vision_model())


def _urlopen_cm(payload):
    class R:
        status = 200
        def read(self): return json.dumps(payload).encode()
        def json(self): return payload
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
    return MagicMock(return_value=R())


class GenerateFromImageTests(unittest.TestCase):
    def test_happy_path_returns_code_and_model(self):
        payload = {"response": "Here you go:\n```tsx\nexport default const X = 1;\n```"}
        with patch("requests.post", side_effect=_urlopen_cm(payload)) as mock_post:
            code, model = generate_code_from_image(
                "abc123", "make responsive", "You are expert.", model="llava:13b")
        self.assertTrue(code and "export default" in code)
        self.assertEqual(model, "llava:13b")
        sent = mock_post.call_args.kwargs["json"]
        self.assertEqual(sent["images"], ["abc123"])          # image b64 gaya
        self.assertIn("screenshot", sent["prompt"].lower())

    def test_no_vision_model_returns_none(self):
        with patch("saleha.core.vision_backend.find_vision_model", return_value=None):
            code, model = generate_code_from_image("abc", "spec", "sys")
        self.assertIsNone(code)
        self.assertEqual(model, "")

    def test_http_failure_returns_none_not_crash(self):
        import requests as _req
        with patch("saleha.core.vision_backend.find_vision_model",
                   return_value="llava:13b"), \
             patch("requests.post", side_effect=_req.ConnectionError("down")):
            code, model = generate_code_from_image("abc", "spec", "sys")
        self.assertIsNone(code)


class VisionCoderIntegrationTests(unittest.TestCase):
    def test_image_source_uses_vision_path(self):
        vc = VisionCoder(model="m")
        with patch("saleha.core.vision_backend.generate_code_from_image") as gen, \
             patch("saleha.core.vision_backend.load_image_b64",
                   return_value=("QUJD", "file:shot.png")):
            gen.return_value = ("export default function Hero() { return null; }", "llava:13b")
            res = vc.synthesize_ui("hero banner", framework="react",
                                   image_source="shot.png")
        self.assertTrue(res.used_vision)
        self.assertEqual(res.model_used, "llava:13b")
        self.assertIn("Hero", res.code)
        self.assertIn("vision", res.source_note)

    def test_vision_fail_falls_back_to_template(self):
        vc = VisionCoder(model="m")
        with patch("saleha.core.vision_backend.generate_code_from_image",
                   return_value=(None, "")), \
             patch("saleha.core.vision_backend.load_image_b64",
                   return_value=("QUJD", "file:shot.png")), \
             patch.object(vc.orchestrator, "execute_task",
                          side_effect=AssertionError("no LLM fallback expected here")):
            res = vc.synthesize_ui("hero", framework="react", image_source="shot.png")
        self.assertFalse(res.used_vision)
        # orchestrator fail -> template
        self.assertIn("Saleha Vision Engine", res.code)

    def test_dry_run_template_still_works(self):
        vc = VisionCoder(model="m")
        res = vc.synthesize_ui("button", dry_run=True)
        self.assertFalse(res.used_vision)
        self.assertEqual(res.source_note, "template")


if __name__ == "__main__":
    unittest.main()
