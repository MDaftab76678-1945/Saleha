"""
Unit & Architecture tests for Saleha Unified Monorepo & Product Ecosystem.
Verifies all 7 phases:
Phase 0: Product DNA Extraction & PRODUCT_BRIEF.md
Phase 1: Unified Architecture (Turborepo, Tauri v2 Desktop, Next.js 15 Web, Astro 5 Landing)
Phase 2: Shared UI Design System (@saleha/ui Atomic Components & Tokens)
Phase 3: Database & API Layer (@saleha/db Prisma & @saleha/api tRPC v11)
Phase 4: Security & RBAC (@saleha/auth SecurityGuard)
Phase 5 & 6: CI/CD Pipeline & E2E Validation (.github/workflows/ci.yml)
Phase 7: Observability & Telemetry (@saleha/core ObservabilityEngine)
"""

import os
import json
import unittest
from pathlib import Path


class MonorepoArchitectureTests(unittest.TestCase):

    def setUp(self):
        self.root_dir = Path(__file__).resolve().parents[2]

    def test_phase0_product_brief_exists_and_complete(self):
        brief_path = self.root_dir / "PRODUCT_BRIEF.md"
        self.assertTrue(brief_path.exists())
        content = brief_path.read_text(encoding="utf-8")
        self.assertIn("Saleha AI", content)
        self.assertIn("Zero-leak", content)
        self.assertIn("LOOP_CHECK", content)

    def test_phase1_turborepo_configuration(self):
        turbo_path = self.root_dir / "turbo.json"
        self.assertTrue(turbo_path.exists())
        with open(turbo_path, "r", encoding="utf-8") as f:
            turbo_cfg = json.load(f)
        self.assertIn("tasks", turbo_cfg)
        self.assertIn("build", turbo_cfg["tasks"])
        self.assertIn("test", turbo_cfg["tasks"])

    def test_phase1_root_package_json_workspaces(self):
        pkg_path = self.root_dir / "package.json"
        self.assertTrue(pkg_path.exists())
        with open(pkg_path, "r", encoding="utf-8") as f:
            pkg_data = json.load(f)
        self.assertIn("workspaces", pkg_data)
        self.assertIn("apps/*", pkg_data["workspaces"])
        self.assertIn("packages/*", pkg_data["workspaces"])

    def test_phase1_desktop_app_tauri_and_react(self):
        desktop_pkg = self.root_dir / "apps" / "desktop" / "package.json"
        self.assertTrue(desktop_pkg.exists())
        
        tauri_conf = self.root_dir / "apps" / "desktop" / "src-tauri" / "tauri.conf.json"
        self.assertTrue(tauri_conf.exists())
        
        main_rs = self.root_dir / "apps" / "desktop" / "src-tauri" / "src" / "main.rs"
        self.assertTrue(main_rs.exists())
        rs_code = main_rs.read_text(encoding="utf-8")
        self.assertIn("check_local_ollama", rs_code)
        self.assertIn("verify_ast_offline", rs_code)

    def test_phase1_web_app_next15(self):
        web_pkg = self.root_dir / "apps" / "web" / "package.json"
        self.assertTrue(web_pkg.exists())
        
        layout_tsx = self.root_dir / "apps" / "web" / "src" / "app" / "layout.tsx"
        self.assertTrue(layout_tsx.exists())
        
        page_tsx = self.root_dir / "apps" / "web" / "src" / "app" / "page.tsx"
        self.assertTrue(page_tsx.exists())

    def test_phase1_landing_page_astro5(self):
        landing_pkg = self.root_dir / "apps" / "landing" / "package.json"
        self.assertTrue(landing_pkg.exists())
        
        astro_cfg = self.root_dir / "apps" / "landing" / "astro.config.mjs"
        self.assertTrue(astro_cfg.exists())
        
        index_astro = self.root_dir / "apps" / "landing" / "src" / "pages" / "index.astro"
        self.assertTrue(index_astro.exists())
        content = index_astro.read_text(encoding="utf-8")
        self.assertIn("Saleha AI", content)

    def test_phase2_ui_package_and_tokens(self):
        ui_pkg_path = self.root_dir / "packages" / "ui" / "package.json"
        self.assertTrue(ui_pkg_path.exists())
        with open(ui_pkg_path, "r", encoding="utf-8") as f:
            ui_pkg = json.load(f)
        self.assertEqual(ui_pkg["name"], "@saleha/ui")

        theme_ts = self.root_dir / "packages" / "ui" / "src" / "tokens" / "theme.ts"
        self.assertTrue(theme_ts.exists())
        code = theme_ts.read_text(encoding="utf-8")
        self.assertIn("Obsidian Dark Luxury", code)
        self.assertIn("Midnight OLED", code)
        self.assertIn("Cyberpunk Neon", code)

    def test_phase2_ui_atomic_components(self):
        btn_tsx = self.root_dir / "packages" / "ui" / "src" / "components" / "button.tsx"
        self.assertTrue(btn_tsx.exists())
        self.assertIn("ButtonProps", btn_tsx.read_text(encoding="utf-8"))

        badge_tsx = self.root_dir / "packages" / "ui" / "src" / "components" / "badge.tsx"
        self.assertTrue(badge_tsx.exists())
        self.assertIn("BadgeProps", badge_tsx.read_text(encoding="utf-8"))

        card_tsx = self.root_dir / "packages" / "ui" / "src" / "components" / "card.tsx"
        self.assertTrue(card_tsx.exists())
        self.assertIn("CardProps", card_tsx.read_text(encoding="utf-8"))

    def test_phase3_db_package_and_prisma_schema(self):
        db_pkg = self.root_dir / "packages" / "db" / "package.json"
        self.assertTrue(db_pkg.exists())
        
        schema_prisma = self.root_dir / "packages" / "db" / "prisma" / "schema.prisma"
        self.assertTrue(schema_prisma.exists())
        schema_text = schema_prisma.read_text(encoding="utf-8")
        self.assertIn("model User", schema_text)
        self.assertIn("model Organization", schema_text)
        self.assertIn("model MemoryTriple", schema_text)

    def test_phase3_api_package_and_trpc_routers(self):
        api_pkg = self.root_dir / "packages" / "api" / "package.json"
        self.assertTrue(api_pkg.exists())
        
        ast_router = self.root_dir / "packages" / "api" / "src" / "routers" / "ast.ts"
        self.assertTrue(ast_router.exists())
        self.assertIn("verifySnippet", ast_router.read_text(encoding="utf-8"))

        swarm_router = self.root_dir / "packages" / "api" / "src" / "routers" / "swarm.ts"
        self.assertTrue(swarm_router.exists())
        self.assertIn("getTopology", swarm_router.read_text(encoding="utf-8"))

    def test_phase4_auth_and_security_guard(self):
        auth_pkg = self.root_dir / "packages" / "auth" / "package.json"
        self.assertTrue(auth_pkg.exists())
        
        auth_src = self.root_dir / "packages" / "auth" / "src" / "index.ts"
        self.assertTrue(auth_src.exists())
        auth_text = auth_src.read_text(encoding="utf-8")
        self.assertIn("SecurityGuard", auth_text)
        self.assertIn("checkRateLimit", auth_text)
        self.assertIn("hasPermission", auth_text)

    def test_phase6_github_actions_ci_workflow(self):
        ci_yml = self.root_dir / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_yml.exists())
        ci_text = ci_yml.read_text(encoding="utf-8")
        self.assertIn("pnpm turbo run", ci_text)
        self.assertIn("pytest saleha/tests/", ci_text)

    def test_phase7_observability_engine(self):
        obs_src = self.root_dir / "packages" / "core" / "src" / "observability.ts"
        self.assertTrue(obs_src.exists())
        obs_text = obs_src.read_text(encoding="utf-8")
        self.assertIn("ObservabilityEngine", obs_text)
        self.assertIn("getSystemHealth", obs_text)


if __name__ == "__main__":
    unittest.main()
