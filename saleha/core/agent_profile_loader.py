"""
Saleha Core: Agent Profile Loader & Registry

Dynamically discovers, parses, and instantiates agent profiles from markdown
specifications in `saleha/skills/` (and custom directories).

Features:
1. Parses YAML frontmatter and markdown body from `agent_*.md` files.
2. Provides `AgentProfileRegistry` to index, query, and search profiles.
3. Provides `ProfileAgent` which inherits from `BaseAgent` and injects
   the profile's system prompt, goals, and constraints into LLM generations.
"""

import os
import re
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from saleha.agents.base_agent import BaseAgent, AgentResponse


@dataclass
class AgentProfile:
    id: str
    name: str
    type: str = "agent_profile"
    version: str = "1.0.0"
    runtime_target: List[str] = field(default_factory=list)
    llm_routing: Dict[str, Any] = field(default_factory=dict)
    system_prompt: str = ""
    goals: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    body: str = ""
    source_file: str = ""

    def format_persona_prompt(self) -> str:
        """Constructs a consolidated persona prompt for this agent profile."""
        lines = [f"[AGENT ROLE: {self.name} (ID: {self.id}) ({self.version})]"]
        if self.system_prompt:
            lines.append(f"\n[SYSTEM INSTRUCTIONS]:\n{self.system_prompt.strip()}")
        if self.goals:
            lines.append("\n[PRIMARY GOALS]:")
            for g in self.goals:
                lines.append(f"- {g}")
        if self.constraints:
            lines.append("\n[CONSTRAINTS & RULES]:")
            for c in self.constraints:
                lines.append(f"- {c}")
        if self.allowed_tools:
            lines.append(f"\n[AUTHORIZED TOOLS]: {', '.join(self.allowed_tools)}")
        if self.body.strip():
            # Include technical guidelines from markdown body
            lines.append(f"\n[TECHNICAL SPECIFICATIONS & HEURISTICS]:\n{self.body.strip()[:1500]}")
        return "\n".join(lines)


class AgentProfileRegistry:
    """Registry that manages all discovered agent profiles."""

    def __init__(self, search_dir: Optional[str] = None):
        self._profiles: Dict[str, AgentProfile] = {}
        if search_dir is None:
            search_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'skills'))
        self.search_dir = search_dir
        self.reload()

    def reload(self, directory: Optional[str] = None):
        """Scans directory and loads all agent_*.md profiles."""
        target_dir = directory or self.search_dir
        self._profiles.clear()

        if not os.path.isdir(target_dir):
            return

        for filename in os.listdir(target_dir):
            if filename.startswith("agent_") and filename.endswith(".md"):
                file_path = os.path.join(target_dir, filename)
                try:
                    profile = self.parse_profile_file(file_path)
                    if profile:
                        self.register(profile)
                except Exception as e:
                    # Ignore invalid files to prevent crash
                    continue

    @staticmethod
    def parse_profile_file(file_path: str) -> Optional[AgentProfile]:
        """Parses a markdown profile with YAML frontmatter."""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            return None

        frontmatter_raw, body = match.groups()
        try:
            metadata = yaml.safe_load(frontmatter_raw) or {}
        except Exception:
            metadata = {}

        if not isinstance(metadata, dict):
            return None

        agent_id = metadata.get("id") or os.path.splitext(os.path.basename(file_path))[0]
        name = metadata.get("name") or agent_id.replace("_", " ").title()

        return AgentProfile(
            id=str(agent_id),
            name=str(name),
            type=str(metadata.get("type", "agent_profile")),
            version=str(metadata.get("version", "1.0.0")),
            runtime_target=list(metadata.get("runtime_target", [])),
            llm_routing=dict(metadata.get("llm_routing", {})),
            system_prompt=str(metadata.get("system_prompt", "")),
            goals=list(metadata.get("goals", [])),
            constraints=list(metadata.get("constraints", [])),
            allowed_tools=list(metadata.get("allowed_tools", [])),
            input_schema=dict(metadata.get("input_schema", {})),
            output_schema=dict(metadata.get("output_schema", {})),
            body=body.strip(),
            source_file=file_path,
        )

    def register(self, profile: AgentProfile):
        self._profiles[profile.id] = profile

    def get(self, id_or_name: str) -> Optional[AgentProfile]:
        """Looks up a profile by exact ID, normalized ID, or substring match."""
        if not id_or_name:
            return None

        # 1. Exact ID
        if id_or_name in self._profiles:
            return self._profiles[id_or_name]

        # 2. Normalized ID (e.g. "security_engineer" -> "agent_security_engineer")
        with_prefix = f"agent_{id_or_name}" if not id_or_name.startswith("agent_") else id_or_name
        if with_prefix in self._profiles:
            return self._profiles[with_prefix]

        # 3. Match against name (case-insensitive)
        query = id_or_name.lower().replace("-", "_").replace(" ", "_")
        for pid, p in self._profiles.items():
            if query in pid.lower() or query in p.name.lower().replace(" ", "_"):
                return p

        return None

    def list_profiles(self) -> List[AgentProfile]:
        return list(self._profiles.values())

    def match_profile_for_task(self, task: str) -> Optional[AgentProfile]:
        """Automatically suggests the best profile for a task if applicable."""
        task_lower = task.lower()
        keyword_map = {
            "agent_security_engineer": ["security", "secret", "private key", "vulnerability", "auth token", "semgrep", "sast"],
            "agent_data_engineer": ["spark", "pyspark", "kafka", "delta lake", "streaming", "lakehouse", "etl pipeline", "dataframe"],
            "agent_cloud_architect": ["terraform", "aws", "vpc", "subnet", "nat gateway", "multi-region", "infrastructure"],
            "agent_devops_engineer": ["dockerfile", "distroless", "ci/cd", "container", "gitops", "deployment yaml"],
            "agent_hardware_engineer": ["hardware", "pdn", "impedance", "transient", "esd", "bom", "derating", "capacitor"],
            "agent_pcb_designer": ["pcb", "gerber", "stack-up", "layer", "controlled-impedance", "routing", "trace width"],
            "agent_sde": ["distributed lock", "raft", "paxos", "concurrency", "redis lock", "split-brain", "mutex"],
            "agent_software_designer": ["lld", "low-level design", "mermaid", "class diagram", "uml", "domain aggregate", "ddd"],
            "agent_performance_tester": ["k6", "load test", "stress test", "latency p95", "throughput", "breakpoint test"],
            "agent_test_automation_engineer": ["playwright", "e2e test", "selenium", "integration test", "ui test", "idempotency test"],
            "agent_ai_engineer": ["langgraph", "rag", "vector db", "guardrail", "embedding", "agent workflow"],
            "agent_sre": ["slo", "sli", "prometheus", "burn rate", "5xx", "alerting rule", "error budget"],
            "agent_ui_ux_designer": ["design token", "spacing", "color palette", "w3c", "typography", "css variable"],
            "agent_compliance_officer": ["soc 2", "gdpr", "compliance", "data privacy", "fido2", "audit control"],
            "agent_product_manager": ["prd", "product requirements", "user persona", "rice scoring", "north star"],
            "agent_project_manager": ["risk register", "mitigation plan", "timeline", "milestone", "project plan"],
            "agent_scrum_master": ["scrum", "sprint", "velocity", "say-do ratio", "story points", "cycle time"],
            "agent_business_analyst": ["bpmn", "business process", "inventory workflow", "use case specification"],
        }

        for pid, keywords in keyword_map.items():
            if any(kw in task_lower for kw in keywords):
                return self.get(pid)

        return None


class ProfileAgent(BaseAgent):
    """An agent that adopts a specific AgentProfile persona.

    v1.4 wiring: profile ki ``llm_routing`` metadata ab REAL effect deti hai --
      - role ke hisaab se SmartRouter me minimum complexity floor
        (security/sde roles flagship tiers pe route hongi)
      - llm_routing.temperature provider options me jaata hai
    """

    # profile-id keyword -> min complexity floor (router candidate tier gate)
    ROLE_COMPLEXITY_FLOOR = (
        ("security", 8.0),
        ("compliance", 7.0),
        ("sre", 7.0),
        ("sde", 6.0),
        ("software_engineer", 6.0),
        ("architect", 5.0),
        ("designer", 5.0),
        ("data", 5.0),
        ("ai_engineer", 6.0),
        ("devops", 4.0),
        ("performance", 4.0),
        ("test", 3.0),
        ("product_manager", 2.0),
        ("project_manager", 2.0),
        ("business_analyst", 2.0),
        ("scrum", 1.0),
    )

    def __init__(self, profile: AgentProfile, model: str = "auto"):
        super().__init__(role=profile.name, model=model)
        self.profile = profile

        # Role-tier floor: id ke keywords se derive
        pid = profile.id.lower()
        self.complexity_floor = 0.0
        for keyword, floor in self.ROLE_COMPLEXITY_FLOOR:
            if keyword in pid:
                self.complexity_floor = floor
                break

        # Temperature: llm_routing.temperature (cloud-era metadata) ab real
        # provider option hai -- clamp 0.05..0.9
        raw_temp = (profile.llm_routing or {}).get("temperature")
        try:
            t = float(raw_temp)
            self.temperature = max(0.05, min(0.9, t))
        except (TypeError, ValueError):
            self.temperature = None  # provider default use hoga

    def think(self, prompt: str, previous_error_reflexion: Optional[str] = None,
              complexity_score: float = 0.0) -> AgentResponse:
        persona_context = self.profile.format_persona_prompt()
        enhanced_prompt = f"{persona_context}\n\n[USER TASK]:\n{prompt}"
        effective_complexity = max(complexity_score, self.complexity_floor)
        return super().think(
            prompt=enhanced_prompt,
            previous_error_reflexion=previous_error_reflexion,
            complexity_score=effective_complexity
        )


# Global profile registry instance
profile_registry = AgentProfileRegistry()

