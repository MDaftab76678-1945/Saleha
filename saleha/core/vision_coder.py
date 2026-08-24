"""
Saleha Core: Multimodal UI-to-Code & Wireframe Synthesizer

Synthesizes production-ready, accessible, and responsive UI components (React + Tailwind CSS,
HTML5/CSS, Flutter) from wireframe descriptions, UI design specifications, and visual layout metadata.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from saleha.orchestrator import SalehaOrchestrator


@dataclass
class VisionCodeResult:
    framework: str  # 'react', 'html', 'flutter'
    component_name: str
    code: str
    dependencies: List[str] = field(default_factory=list)
    used_vision: bool = False          # B-naya: real multimodal model use hua?
    model_used: str = ""               # kaunsa vision/LLM model laga
    source_note: str = ""              # template | llm-text | llm-vision | file:xyz


class VisionCoder:
    """Synthesizes pixel-perfect UI code from wireframe specs, layout prompts,
    aur (naya) ACTUAL screenshots via local Ollama vision models."""

    FRAMEWORK_PROMPTS = {
        "react": (
            "You are an expert React frontend engineer. Generate a clean, responsive, accessible "
            "React component using Tailwind CSS utility classes. Use modern React hooks (useState, useEffect). "
            "Return only valid TypeScript/TSX code."
        ),
        "html": (
            "You are an expert web frontend engineer. Generate semantic HTML5 with modern CSS (Flexbox/Grid, "
            "custom properties, responsive layout) and vanilla JavaScript. Return single clean HTML document."
        ),
        "flutter": (
            "You are an expert Flutter mobile developer. Generate a clean Material 3 Flutter Widget tree. "
            "Use Stateless or Stateful widgets with proper layout constraints. Return valid Dart code."
        )
    }

    def __init__(self, model: str = "auto"):
        self.model = model
        self.orchestrator = SalehaOrchestrator(model=model)

    def synthesize_ui(self, layout_spec: str, framework: str = "react", component_name: str = "GeneratedComponent", dry_run: bool = False,
                      image_source: Optional[str] = None, use_llm: bool = False) -> VisionCodeResult:
        """Generates frontend component code based on layout specification.

        Naya priority order:
        1. `image_source` (file path / base64 / data-URL) diya ho -> REAL
           vision model (llava/qwen-vl) screenshot analyze karta hai.
        2. Warna `use_llm=True` ho to text-spec se orchestrator LLM path.
        3. Warna fast template preview (dry_run behavior -- web studio ka
           default, deterministic aur instant).
        """
        clean_fw = framework.lower().strip()
        if clean_fw not in self.FRAMEWORK_PROMPTS:
            clean_fw = "react"

        deps = []
        if clean_fw == "react":
            deps = ["react", "lucide-react", "tailwindcss"]
            template_code = (
                f"import React from 'react';\n\n"
                f"export default function {component_name}() {{\n"
                f"  return (\n"
                f"    <div className='p-6 max-w-md mx-auto bg-white rounded-xl shadow-md space-y-4'>\n"
                f"      <h2 className='text-xl font-bold text-gray-900'>{layout_spec[:40]}</h2>\n"
                f"      <p className='text-gray-500'>Synthesized by Saleha Vision Engine</p>\n"
                f"    </div>\n"
                f"  );\n"
                f"}}"
            )
        elif clean_fw == "flutter":
            deps = ["flutter/material.dart"]
            template_code = (
                f"import 'package:flutter/material.dart';\n\n"
                f"class {component_name} extends StatelessWidget {{\n"
                f"  const {component_name}({{super.key}});\n\n"
                f"  @override\n"
                f"  Widget build(BuildContext context) {{\n"
                f"    return Card(\n"
                f"      child: Padding(\n"
                f"        padding: const EdgeInsets.all(16.0),\n"
                f"        child: Text('{layout_spec[:40]}'),\n"
                f"      ),\n"
                f"    );\n"
                f"  }}\n"
                f"}}"
            )
        else:
            deps = []
            template_code = (
                f"<!DOCTYPE html>\n<html>\n<head>\n  <title>{component_name}</title>\n</head>\n"
                f"<body>\n  <div class='container'>\n    <h1>{layout_spec[:40]}</h1>\n  </div>\n</body>\n</html>"
            )

        if dry_run and not image_source:
            return VisionCodeResult(
                framework=clean_fw,
                component_name=component_name,
                code=template_code,
                dependencies=deps,
                used_vision=False,
                source_note="template",
            )

        # ------------------------------------------------------------------
        # REAL VISION PATH (naya): image diya gaya hai
        # ------------------------------------------------------------------
        if image_source:
            from saleha.core import vision_backend
            try:
                image_b64, media_note = vision_backend.load_image_b64(image_source)
            except ValueError as img_err:
                return VisionCodeResult(
                    framework=clean_fw, component_name=component_name,
                    code=template_code, dependencies=deps,
                    used_vision=False, source_note=f"template (image error: {img_err})",
                )
            system_prompt = self.FRAMEWORK_PROMPTS[clean_fw]
            code, model_used = vision_backend.generate_code_from_image(
                image_b64, layout_spec, system_prompt
            )
            if code:
                return VisionCodeResult(
                    framework=clean_fw, component_name=component_name,
                    code=code, dependencies=deps,
                    used_vision=True, model_used=model_used,
                    source_note=f"llm-vision via {media_note}",
                )
            # Vision unavailable/fail -> text-LLM fallback niche fall-through
            fallback_note = "vision model unavailable"

        system_instruction = self.FRAMEWORK_PROMPTS[clean_fw]
        prompt = (
            f"{system_instruction}\n\n"
            f"Component Name: {component_name}\n"
            f"UI Wireframe / Layout Specification:\n{layout_spec}\n\n"
            f"Generate the complete, production-grade {clean_fw} implementation."
        )

        try:
            orch_res = self.orchestrator.execute_task(prompt)
            code = orch_res.final_code if orch_res.success else template_code
            llm_ok = orch_res.success
        except Exception:
            code = template_code
            llm_ok = False

        if llm_ok:
            note = "llm-text"
        elif image_source:
            note = "template (vision unavailable, LLM fallback failed)"
        else:
            note = "template (LLM unavailable)"

        return VisionCodeResult(
            framework=clean_fw,
            component_name=component_name,
            code=code,
            dependencies=deps,
            used_vision=False,
            source_note=note,
        )


# Global instance
vision_coder = VisionCoder()

