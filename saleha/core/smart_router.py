"""
Saleha Core: Smart Model Router (Level 3 -- 2026 Catalog + Runtime Probing)

Naya vs pehle:
1. Model catalog me 2026-generation local models add kiye gaye hain
   (qwen3-coder:30b, devstral:24b, deepseek-r1:8b, qwen2.5-coder:7b,
   qwen3:4b) -- purane models ab bhi legacy fallback ke liye hain.
2. Runtime Ollama probing (`/api/tags`) -- agar probe enabled hai to
   router sirf actually-installed models hi choose karta hai, aur
   install-status ke hisaab se candidate list adapt ho jaati hai.
3. History file ab CWD-relative nahi -- default `~/.saleha/router_history.json`
   (pehle repo root me `router_history.json` pollute hota tha).
4. Probe opt-in hai (BaseAgent "auto" mode ise enable karta hai) taaki
   direct SmartRouter use karne wala behavior deterministic rahe.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import psutil
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Any, Tuple, Callable
from collections import defaultdict
import hashlib
INSTALL_PROBE_TTL_SEC = 60.0
_OLLAMA_TAGS_URL = os.getenv("SALEHA_OLLAMA_URL", "http://localhost:11434") + "/api/tags"
_probe_cache: Dict[str, object] = {"at": 0.0, "models": frozenset()}


def get_installed_ollama_models(force_refresh: bool = False) -> Set[str]:
    """Ollama /api/tags se installed model names laata hai (TTL-cached).

    Return empty set ka matlab: Ollama down ya unreachable -- is case me
    router ko static catalog pe fall back karna chahiye.
    """
    global _probe_cache
    now = time.time()
    if not force_refresh and (now - float(_probe_cache["at"])) < INSTALL_PROBE_TTL_SEC:
        return set(_probe_cache["models"])  # type: ignore[arg-type]

    models: Set[str] = set()
    try:
        req = urllib.request.Request(_OLLAMA_TAGS_URL, method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for entry in data.get("models", []):
            name = (entry.get("name") or "").strip()
            if not name:
                continue
            models.add(name)
            # ":latest" alias normalization -- base name se bhi match kare
            if ":" in name:
                models.add(name.split(":", 1)[0])
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        models = set()

    _probe_cache = {"at": now, "models": frozenset(models)}
    return models


def get_default_history_path() -> str:
    saleha_dir = os.path.join(os.path.expanduser("~"), ".saleha")
    try:
        os.makedirs(saleha_dir, exist_ok=True)
    except OSError:
        pass
    return os.path.join(saleha_dir, "router_history.json")


@dataclass
class ModelProfile:
    name: str
    size_gb: float
    speed: str
    best_for: List[str]
    avg_response_time: float = 0.0
    success_rate: float = 1.0
    total_uses: int = 0


@dataclass
class TaskResult:
    task_hash: str
    model_used: str
    response_time: float
    success: bool
    timestamp: float


class SmartRouter:
    def __init__(self, history_file: Optional[str] = None, probe_runtime: bool = False):
        self.history_file = history_file or get_default_history_path()
        self.probe_runtime = probe_runtime
        self.models = self._init_models()
        self.task_history: List[TaskResult] = []
        self.model_performance: Dict[str, Dict] = defaultdict(lambda: {
            "success_count": 0,
            "fail_count": 0,
            "total_time": 0.0,
            "uses": 0
        })
        self.task_cache: Dict[str, str] = {}
        self._load_history()

    def _init_models(self) -> Dict[str, ModelProfile]:
        return {
            # ---------- 2026 generation catalog ----------
            "qwen3-coder:30b": ModelProfile(
                name="qwen3-coder:30b",
                size_gb=18.0,
                speed="slow",
                best_for=["architecture", "system", "distributed", "large"]
            ),
            "devstral:24b": ModelProfile(
                name="devstral:24b",
                size_gb=14.0,
                speed="slow",
                best_for=["agent", "tool", "multi-file", "swe"]
            ),
            "deepseek-r1:8b": ModelProfile(
                name="deepseek-r1:8b",
                size_gb=5.0,
                speed="medium",
                best_for=["reason", "plan", "analyze", "design", "project"]
            ),
            "qwen2.5-coder:7b": ModelProfile(
                name="qwen2.5-coder:7b",
                size_gb=4.7,
                speed="medium",
                best_for=["service", "implement", "module", "optimize"]
            ),
            "qwen3:4b": ModelProfile(
                name="qwen3:4b",
                size_gb=2.6,
                speed="fast",
                best_for=["utility", "convert", "parse", "medium"]
            ),
            # ---------- legacy catalog (backward compatibility) ----------
            "qwen3.5:0.8b": ModelProfile(
                name="qwen3.5:0.8b",
                size_gb=0.8,
                speed="ultra_fast",
                best_for=["test", "check", "validate", "simple"]
            ),
            "qwen2.5-coder:1.5b": ModelProfile(
                name="qwen2.5-coder:1.5b",
                size_gb=1.5,
                speed="very_fast",
                best_for=["script", "small", "quick", "fix", "function"]
            ),
            "qwen2.5-coder:3b": ModelProfile(
                name="qwen2.5-coder:3b",
                size_gb=3.0,
                speed="fast",
                best_for=["code", "api", "class", "bug"]
            ),
            "deepseek-coder:6.7b": ModelProfile(
                name="deepseek-coder:6.7b",
                size_gb=6.7,
                speed="medium",
                best_for=["complex", "debug", "refactor"]
            ),
            "deepseek-r1:7b": ModelProfile(
                name="deepseek-r1:7b",
                size_gb=7.0,
                speed="medium",
                best_for=["reason", "plan", "analyze"]
            ),
            "qwen3.5:9b": ModelProfile(
                name="qwen3.5:9b",
                size_gb=9.0,
                speed="slow",
                best_for=["comprehensive", "massive", "full"]
            ),
        }

    def _filter_installed(self, candidates: List[str]) -> List[str]:
        """Agar runtime probing on hai aur Ollama reachable hai, to candidate
        list ko sirf installed models tak simit karo. Probe fail / empty hone
        par original list wapas (offline-safe behavior)."""
        if not self.probe_runtime:
            return candidates
        installed = get_installed_ollama_models()
        if not installed:
            return candidates
        available = [c for c in candidates if c in installed]
        return available or candidates

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.model_performance = defaultdict(lambda: {
                        "success_count": 0,
                        "fail_count": 0,
                        "total_time": 0.0,
                        "uses": 0
                    }, data.get("performance", {}))
                    self.task_cache = data.get("cache", {})
            except (json.JSONDecodeError, OSError):
                pass

    def _save_history(self):
        data = {
            "performance": dict(self.model_performance),
            "cache": self.task_cache,
            "last_updated": time.time()
        }
        try:
            dirname = os.path.dirname(self.history_file)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, OSError):
            pass

    def _get_task_hash(self, task: str, complexity: float) -> str:
        task_key = f"{task[:100]}_{complexity}"
        return hashlib.sha256(task_key.encode()).hexdigest()

    def _get_thermal_state(self) -> str:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if cpu_percent > 80:
                return "hot"
            elif cpu_percent > 60:
                return "warm"
            else:
                return "cool"
        except Exception:
            return "cool"

    def _get_candidate_models(self, complexity: float, thermal_state: str) -> List[str]:
        """Complexity aur thermal state ke hisaab se candidate models.
        2026-generation models ko prefer kiya gaya hai jab wo installed hain
        (probe_runtime), warna legacy list deterministic fallback hai."""

        if thermal_state == "hot":
            if complexity >= 9.0:
                return self._filter_installed(["qwen3-coder:30b", "deepseek-r1:8b", "deepseek-coder:6.7b"])
            elif complexity >= 5.0:
                return self._filter_installed(["deepseek-coder:6.7b", "qwen2.5-coder:7b"])
            else:
                return self._filter_installed(["qwen2.5-coder:1.5b", "qwen2.5-coder:3b"])

        elif thermal_state == "warm":
            if complexity >= 9.0:
                return self._filter_installed(["qwen3-coder:30b", "deepseek-r1:8b", "qwen3.5:9b"])
            elif complexity >= 5.0:
                return self._filter_installed(["deepseek-coder:6.7b", "qwen2.5-coder:7b", "qwen2.5-coder:3b"])
            else:
                return self._filter_installed(["qwen2.5-coder:3b", "qwen2.5-coder:1.5b"])

        else:
            if complexity >= 9.0:
                return self._filter_installed(["qwen3-coder:30b", "deepseek-r1:8b", "qwen3.5:9b", "deepseek-coder:6.7b"])
            elif complexity >= 5.0:
                return self._filter_installed(["devstral:24b", "deepseek-coder:6.7b", "qwen2.5-coder:7b", "qwen2.5-coder:3b"])
            elif complexity >= 2.0:
                return self._filter_installed(["qwen2.5-coder:3b", "qwen3:4b", "qwen2.5-coder:1.5b"])
            else:
                return self._filter_installed(["qwen2.5-coder:1.5b", "qwen2.5-coder:3b"])

    def _score_model(self, model_name: str, task: str, complexity: float) -> float:
        profile = self.models[model_name]
        perf = self.model_performance[model_name]
        score = 0.0

        if perf["uses"] > 0:
            success_rate = perf["success_count"] / perf["uses"]
            score += success_rate * 40.0

        if perf["uses"] > 0:
            avg_time = perf["total_time"] / perf["uses"]
            time_score = max(1.0, 10.0 / avg_time)
            score += time_score * 3.0

        task_lower = task.lower()
        keyword_matches = sum(1 for kw in profile.best_for if kw in task_lower)
        score += keyword_matches * 4.0

        size_score = 10.0 / profile.size_gb
        score += size_score

        return score

    def select_model(self, task: str, complexity_score: float = 0.0) -> str:
        task_hash = self._get_task_hash(task, complexity_score)
        if task_hash in self.task_cache:
            cached_model = self.task_cache[task_hash]
            if cached_model in self.models:
                return cached_model

        thermal_state = self._get_thermal_state()
        candidates = self._get_candidate_models(complexity_score, thermal_state)

        model_scores = []
        for model_name in candidates:
            score = self._score_model(model_name, task, complexity_score)
            model_scores.append((model_name, score))

        model_scores.sort(key=lambda x: x[1], reverse=True)
        selected_model = model_scores[0][0]

        self.task_cache[task_hash] = selected_model

        if len(self.task_cache) > 1000:
            self.task_cache.clear()

        return selected_model

    def route_task(self, task: str, complexity: float = 0.0) -> str:
        return self.select_model(task, complexity_score=complexity)

    def record_result(self, task: str, complexity: float, model_used: str, 
                     response_time: float, success: bool):
        task_hash = self._get_task_hash(task, complexity)
        
        result = TaskResult(
            task_hash=task_hash,
            model_used=model_used,
            response_time=response_time,
            success=success,
            timestamp=time.time()
        )
        self.task_history.append(result)

        perf = self.model_performance[model_used]
        perf["uses"] += 1
        perf["total_time"] += response_time
        if success:
            perf["success_count"] += 1
        else:
            perf["fail_count"] += 1

        self._save_history()

    def get_model_stats(self, model_name: str) -> Dict:
        perf = self.model_performance[model_name]
        if perf["uses"] == 0:
            return {
                "uses": 0,
                "success_rate": 0.0,
                "avg_time": 0.0
            }
        
        return {
            "uses": perf["uses"],
            "success_rate": perf["success_count"] / perf["uses"],
            "avg_time": perf["total_time"] / perf["uses"]
        }

    def classify_task_tier(self, task: str) -> Dict[str, Any]:
        """Classifies task intent into fast, standard, or reasoning tier."""
        task_lower = task.lower()

        # 1. Reasoning / Architecture Tier
        reasoning_keywords = [
            "architect", "design", "distributed", "microservice", "security audit",
            "vulnerability", "refactor whole", "concurrency", "deadlock", "algorithm",
            "optimize complexity", "high throughput", "database schema", "self-healing"
        ]
        if any(w in task_lower for w in reasoning_keywords) or len(task.split()) > 40:
            return {
                "tier": "reasoning",
                "estimated_complexity": 8.5,
                "recommended_model": self.select_model(task, complexity_score=8.5),
                "rationale": "High-complexity architectural reasoning required."
            }

        # 2. Fast Tier
        fast_keywords = [
            "docstring", "comment", "rename", "typo", "quick fix", "syntax",
            "convert", "format", "uppercase", "lowercase", "is_prime", "fibonacci",
            "two sum", "simple helper", "unit test outline"
        ]
        if any(w in task_lower for w in fast_keywords) and len(task.split()) < 15:
            return {
                "tier": "fast",
                "estimated_complexity": 2.0,
                "recommended_model": self.select_model(task, complexity_score=2.0),
                "rationale": "Low-complexity syntactic/helper task suitable for ultra-fast local tier."
            }

        # 3. Standard Tier
        return {
            "tier": "standard",
            "estimated_complexity": 5.0,
            "recommended_model": self.select_model(task, complexity_score=5.0),
            "rationale": "Standard implementation and modular engineering task."
        }

    def get_failover_chain(self, task: str, max_cost_usd: float = 0.0) -> List[str]:
        """Synthesizes prioritized multi-tier failover chain from Local Ollama to Cloud APIs."""
        primary = self.select_model(task)
        tier_info = self.classify_task_tier(task)
        chain = [primary]

        # Tier 1 fallback: secondary local model
        if primary != "qwen2.5-coder:7b":
            chain.append("qwen2.5-coder:7b")
        elif "deepseek-r1:8b" not in chain:
            chain.append("deepseek-r1:8b")

        # Tier 2 fallback: High-speed low-cost Cloud API
        chain.append("deepseek/deepseek-chat")

        # Tier 3 fallback: Frontier Reasoning Cloud API
        if tier_info.get("tier") == "reasoning":
            chain.append("anthropic/claude-3-7-sonnet")
        else:
            chain.append("openai/gpt-4o")

        return list(dict.fromkeys(chain))

    def execute_with_failover(
        self,
        task: str,
        invoke_fn: Callable[[str], Any],
        max_retries: int = 3
    ) -> Tuple[Any, str, float]:
        """Executes a task across the prioritized failover chain with latency tracking."""
        chain = self.get_failover_chain(task)
        last_err: Optional[Exception] = None

        for model in chain[:max_retries]:
            start = time.time()
            try:
                result = invoke_fn(model)
                elapsed = time.time() - start
                self.record_result(task, 5.0, model, elapsed, success=True)
                return result, model, elapsed
            except Exception as e:
                elapsed = time.time() - start
                self.record_result(task, 5.0, model, elapsed, success=False)
                last_err = e
                continue

        if last_err:
            raise last_err
        raise RuntimeError(f"All failover providers exhausted for task: {task}")

    def get_all_stats(self) -> Dict[str, Dict]:
        return {name: self.get_model_stats(name) for name in self.models}


# Global Singleton Instance
smart_router = SmartRouter()