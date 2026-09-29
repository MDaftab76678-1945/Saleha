"""
Saleha Core: Smart Model Router -- catalog + runtime Ollama probing.

Routing works by scoring candidate models and picking the best. Candidates
come from a static catalog, narrowed to what is actually installed when
`probe_runtime` is on (BaseAgent's "auto" mode enables it; direct users get
deterministic behavior). An unreachable Ollama falls back to the full
catalog rather than routing to nothing. History lives in
`~/.saleha/router_history.json`, not the repo root.

## Catalog sizes are load-bearing, so they are measured

`_score_model()` adds `10.0 / size_gb`, so a wrong size directly changes
which model is chosen. Every size here was read from this machine's
`/api/tags` rather than estimated. The previous values were guesses and all
four overlapping entries were wrong -- `qwen3.5:4b` was listed at 0.8 GB
against a real 3.4 GB, giving it a size score of 12.50 instead of 2.94, a
**4.2x inflation** that biased selection toward it on every scored call.

The catalog also carried five models that are not installed here
(`qwen3-coder:30b`, `devstral:24b`, `deepseek-r1:8b`, `qwen2.5-coder:7b`,
`qwen3:4b`) while omitting `qwen3:8b`, which is installed -- so the most
capable general model on the box was unroutable, and half the candidate
lists resolved to nothing. Entries for uninstalled models are kept
deliberately (a different machine may have them, and `_filter_installed`
drops them when probing), but their sizes are now marked as unverified.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import psutil

INSTALL_PROBE_TTL_SEC = 60.0
_OLLAMA_TAGS_URL = os.getenv("SALEHA_OLLAMA_URL", "http://localhost:11434") + "/api/tags"
_probe_cache_at: float = 0.0
_probe_cache_models: Set[str] = set()

# Laya "choice" question for classify_task_tier's hybrid step. Verbatim --
# criteria wording is part of what was measured (25/30 on the 30-task
# hand-labelled set vs. 21/30 keyword-only, 23/30 Laya-only).
_LAYA_TIER_QUESTION: Dict[str, Any] = {
    "tier": {
        "type": "choice",
        "instructions": "How much reasoning does this coding task need?",
        "criteria": {
            "fast": "trivial one-line or cosmetic edit: typo, rename, comment, format",
            "standard": "normal feature or bug fix in one area of the code",
            "reasoning": "architecture, concurrency, security, cross-service debugging or algorithm design",
        },
    }
}

# Module-level cache so the (421M parameter) model loads at most once per
# process, and only on first actual use -- never at import time.
_laya_agent_cache: Any = None
_laya_load_failed: Optional[str] = None


def _laya_enabled() -> bool:
    """Whether classify_task_tier should even attempt to consult Laya.

    Off in the test suite (SALEHA_TEST_MODE=1, set repo-wide by
    saleha/tests/conftest.py) so the ~421M model never loads under pytest,
    and off when the operator explicitly opts out with SALEHA_LAYA=0.
    """
    if os.getenv("SALEHA_TEST_MODE") == "1":
        return False
    return os.getenv("SALEHA_LAYA") != "0"


def _get_laya_agent() -> Tuple[Any, Optional[str]]:
    """Lazily load and cache the Laya decision-model agent.

    Returns (agent, None) on success, or (None, reason) when Laya cannot be
    used -- import failed or load raised. Never raises: a broken Laya
    install must degrade to the keyword answer, not crash routing.
    """
    global _laya_agent_cache, _laya_load_failed
    if _laya_agent_cache is not None:
        return _laya_agent_cache, None
    if _laya_load_failed is not None:
        return None, _laya_load_failed

    try:
        import laya
    except ImportError as err:
        _laya_load_failed = f"laya import failed: {err}"
        return None, _laya_load_failed

    try:
        _laya_agent_cache = laya.load("convaiinnovations/laya")
    except Exception as err:  # model load can fail in many ways; never crash routing
        _laya_load_failed = f"laya load failed: {err}"
        return None, _laya_load_failed

    return _laya_agent_cache, None


def get_installed_ollama_models(force_refresh: bool = False) -> Set[str]:
    """Installed model names from Ollama's /api/tags, TTL-cached.

    An empty set means Ollama is down or unreachable, and callers should fall
    back to the static catalog.

    Note the returned set carries a bare base name beside every tagged one
    ("qwen3.5" as well as "qwen3.5:9b") so an untagged request still matches.
    That makes it a matching index, not an inventory -- counting it reported
    15 models on a box with 8 (see `saleha doctor`, pass 62).
    """
    global _probe_cache_at, _probe_cache_models
    now = time.time()
    if not force_refresh and (now - _probe_cache_at) < INSTALL_PROBE_TTL_SEC:
        return set(_probe_cache_models)

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

    _probe_cache_at = now
    _probe_cache_models = set(models)
    return models


def _clean_verified(raw: Any) -> Dict[str, Dict[str, float]]:
    """The history file's "verified" section, keeping only well-formed, non-negative entries."""
    clean: Dict[str, Dict[str, float]] = {}
    if not isinstance(raw, dict):
        return clean
    for model, v in raw.items():
        if not isinstance(v, dict):
            continue
        try:
            passed, failed, seconds = int(v.get("passed", 0)), int(v.get("failed", 0)), float(v.get("seconds", 0.0))
        except (TypeError, ValueError):
            continue
        if min(passed, failed, seconds) >= 0:
            clean[str(model)] = {"passed": passed, "failed": failed, "seconds": seconds}
    return clean


def get_default_history_path() -> str:
    saleha_dir = os.path.join(os.path.expanduser("~"), ".saleha")
    with contextlib.suppress(OSError):
        os.makedirs(saleha_dir, exist_ok=True)
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
    """
    Picks an installed model by keyword fit, size, and -- the largest term --
    how often the model's output has actually passed an independent check.

    That last term used to be the share of calls where Ollama returned any
    text at all (`record_result`, fed by every `BaseAgent.think`). Measured in
    this machine's history: qwen2.5-coder:3b at 94% "success" and 0.72 s per
    call, while its real repair tries passed tests plus a brute-force check 2
    times in 34 at ~11 s each; qwen2.5-coder:7b, not even installed, at 100%
    over 345 calls averaging 0.00 s -- test-suite mock calls written into the
    real history file. An answer that exists is not an answer that works.

    Quality now comes only from `record_verdict`: an outcome some check
    outside the model decided (tests, a brute-force comparison). A model with
    no verdicts is scored as the average of the models that have them, so it
    can compete without displacing a proven one. The term is pass rate times a
    speed factor, so a small model that passes less often but tries five times
    faster is not ranked below a big one per attempt -- small beating large
    has to show up in the arithmetic, not only in the slogan.
    """

    # Pass-rate prior when no model has a verdict yet.
    _UNTRIED_SUCCESS_PRIOR = 0.75
    # Pseudo-observations pulling a model's pass rate toward the prior, so two
    # lucky verdicts do not read as a 100% model.
    _PRIOR_WEIGHT = 2.0
    # A verified try that takes this long or less earns the full speed factor;
    # slower tries scale down in proportion (a 60 s try earns a quarter).
    _FAST_TRY_SECONDS = 15.0

    def __init__(
        self,
        history_file: Optional[str] = None,
        probe_runtime: bool = False,
        laya_agent: Any = None,
    ):
        # The test suite constructs routers with the default path through
        # every "auto" agent; persisting those mock calls is how 345 fake
        # qwen2.5-coder:7b runs reached the real history file.
        self._persist = history_file is not None or os.environ.get("SALEHA_TEST_MODE") != "1"
        self.history_file = history_file or get_default_history_path()
        self.probe_runtime = probe_runtime
        self.models = self._init_models()
        # Test injection point: setting this to a fake object (with a
        # .predict(task, questions) method) bypasses the real lazy-loaded
        # Laya agent. Leave None for production, where classify_task_tier
        # lazily loads and caches the real agent at module level.
        self.laya_agent = laya_agent
        self.task_history: List[TaskResult] = []
        self.model_performance: Dict[str, Dict] = defaultdict(lambda: {
            "success_count": 0,
            "fail_count": 0,
            "total_time": 0.0,
            "uses": 0
        })
        self.task_cache: Dict[str, str] = {}
        # model -> {"passed": n, "failed": n, "seconds": total}, from record_verdict only.
        self.verified: Dict[str, Dict[str, float]] = {}
        self._load_history()

    def _init_models(self) -> Dict[str, ModelProfile]:
        return {
            # ---------- not installed here: sizes are estimates, not measured.
            # Kept because another machine may have them; _filter_installed()
            # drops them when probing is on. ----------
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
            # ---------- installed on this machine: sizes read from /api/tags ----------
            "qwen3:8b": ModelProfile(
                name="qwen3:8b",
                size_gb=5.2,
                speed="medium",
                best_for=["reason", "plan", "analyze", "design", "architecture",
                          "system", "explain"]
            ),
            "qwen3.5:4b": ModelProfile(
                name="qwen3.5:4b",
                # Was 0.8 -- a guess, 4.2x off. It inflated this model's size
                # score to 12.50 against a true 2.94 on every scored call.
                size_gb=3.4,
                speed="medium",
                best_for=["test", "check", "validate", "simple"]
            ),
            # Was two entries (1.5b and 3b). The 1.5b model was removed from
            # this machine, so its profile is folded into 3b rather than left
            # as a duplicate dict key that silently shadowed the other.
            "qwen2.5-coder:3b": ModelProfile(
                name="qwen2.5-coder:3b",
                size_gb=1.9,
                speed="very_fast",
                best_for=["script", "small", "quick", "fix", "function",
                          "code", "api", "class", "bug"]
            ),
            "deepseek-coder:6.7b": ModelProfile(
                name="deepseek-coder:6.7b",
                size_gb=3.8,          # was 6.7 (the parameter count, not the
                                      # on-disk size of the quantized weights)
                speed="medium",
                best_for=["complex", "debug", "refactor"]
            ),
            "deepseek-r1:7b": ModelProfile(
                name="deepseek-r1:7b",
                size_gb=4.7,          # was 7.0, same parameter-count mistake
                speed="medium",
                best_for=["reason", "plan", "analyze"]
            ),
            "qwen3.5:9b": ModelProfile(
                name="qwen3.5:9b",
                size_gb=6.6,          # was 9.0, same parameter-count mistake
                speed="slow",
                best_for=["comprehensive", "massive", "full"]
            ),
        }

    def _filter_installed(self, candidates: List[str]) -> List[str]:
        """Narrow candidates to installed models when probing is enabled.

        A failed or empty probe returns the original list, so an unreachable
        Ollama degrades to catalog-only routing rather than to nothing.
        """
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
                    self.verified = _clean_verified(data.get("verified"))
            except (json.JSONDecodeError, OSError):
                pass

    def _read_disk_verified(self) -> None:
        """Take the verdicts on disk; another router may have added some since this one loaded."""
        if os.path.exists(self.history_file):
            with contextlib.suppress(json.JSONDecodeError, OSError, AttributeError), \
                    open(self.history_file, encoding="utf-8") as f:
                self.verified = _clean_verified(json.load(f).get("verified"))

    def _save_history(self, verdict_added: bool = False):
        if not self._persist:
            return
        if not verdict_added:
            # Every think() saves; a router loaded before a verdict was
            # recorded elsewhere would otherwise write the old section back.
            self._read_disk_verified()
        data = {
            "performance": dict(self.model_performance),
            "cache": self.task_cache,
            "verified": self.verified,
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
        """Candidates by complexity and thermal state.

        Larger models lead each list; `_filter_installed()` drops the ones
        this machine does not have, so a box with `qwen3-coder:30b` uses it
        and a box without falls through to what it does have.

        Every mid-tier list previously named only models absent from this
        machine plus `qwen2.5-coder:3b`, so a complexity-6 task -- squarely
        mid-tier work -- routed to the smallest model installed. `qwen3:8b`
        was installed the whole time and appeared in no list at all.
        """

        if thermal_state == "hot":
            # Hot: prefer smaller models; the machine is already loaded.
            if complexity >= 9.0:
                return self._filter_installed(["qwen3-coder:30b", "deepseek-r1:8b", "deepseek-coder:6.7b"])
            elif complexity >= 5.0:
                return self._filter_installed(["deepseek-coder:6.7b", "qwen2.5-coder:7b", "qwen2.5-coder:3b"])
            else:
                return self._filter_installed(["qwen2.5-coder:3b"])

        elif thermal_state == "warm":
            if complexity >= 9.0:
                return self._filter_installed(["qwen3-coder:30b", "deepseek-r1:8b", "qwen3.5:9b", "qwen3.5:4b"])
            elif complexity >= 5.0:
                return self._filter_installed(["deepseek-coder:6.7b", "qwen2.5-coder:7b", "qwen3.5:4b", "qwen2.5-coder:3b"])
            else:
                return self._filter_installed(["qwen2.5-coder:3b"])

        else:
            if complexity >= 9.0:
                return self._filter_installed(["qwen3-coder:30b", "deepseek-r1:8b", "qwen3.5:9b", "qwen3.5:4b", "deepseek-coder:6.7b"])
            elif complexity >= 5.0:
                return self._filter_installed(["devstral:24b", "qwen3.5:4b", "deepseek-coder:6.7b", "qwen2.5-coder:7b", "qwen2.5-coder:3b"])
            elif complexity >= 2.0:
                return self._filter_installed(["qwen2.5-coder:3b", "qwen3.5:4b", "qwen3:4b"])
            else:
                return self._filter_installed(["qwen2.5-coder:3b"])

    def _speed_factor(self, seconds_per_try: float) -> float:
        """1.0 up to _FAST_TRY_SECONDS per verified try, falling in proportion after."""
        return min(1.0, self._FAST_TRY_SECONDS / max(0.001, seconds_per_try))

    def _verified_priors(self) -> Tuple[float, float]:
        """
        (pass rate, speed factor) for a model with no verdicts: every verdict
        so far pooled, pulled toward _UNTRIED_SUCCESS_PRIOR. Not the raw
        average -- measured, qwen2.5-coder:3b went 0 for 6 on a real repair,
        and a raw average of 0 would score every untried model as failing too,
        so the router could never try another arm when the incumbent keeps
        missing.
        """
        judged = [v for v in self.verified.values() if v["passed"] + v["failed"] > 0]
        if not judged:
            return self._UNTRIED_SUCCESS_PRIOR, 1.0
        passed = sum(v["passed"] for v in judged)
        tries = sum(v["passed"] + v["failed"] for v in judged)
        rate = (passed + self._UNTRIED_SUCCESS_PRIOR * self._PRIOR_WEIGHT) / (tries + self._PRIOR_WEIGHT)
        speeds = [self._speed_factor(v["seconds"] / (v["passed"] + v["failed"])) for v in judged]
        return rate, sum(speeds) / len(speeds)

    def verified_quality(self, model_name: str) -> Dict[str, float]:
        """Pass rate, speed factor and their product for a model, from verdicts or the priors."""
        prior_rate, prior_speed = self._verified_priors()
        v = self.verified.get(model_name, {"passed": 0, "failed": 0, "seconds": 0.0})
        tries = v["passed"] + v["failed"]
        if tries:
            rate = (v["passed"] + prior_rate * self._PRIOR_WEIGHT) / (tries + self._PRIOR_WEIGHT)
            speed = self._speed_factor(v["seconds"] / tries)
        else:
            rate, speed = prior_rate, prior_speed
        return {"tries": tries, "pass_rate": rate, "speed_factor": speed, "quality": rate * speed}

    def _score_model(self, model_name: str, task: str, _complexity: float) -> float:
        profile = self.models[model_name]
        # Up to 40 for verified quality. A model with no verdicts gets the
        # average of those that have them: scored as failing, a new model
        # could never be picked, and never being picked kept it unscored
        # (qwen3:8b once lost "design a distributed system" 9.92 to 59.47).
        score = self.verified_quality(model_name)["quality"] * 40.0

        task_lower = task.lower()
        keyword_matches = sum(1 for kw in profile.best_for if kw in task_lower)
        score += keyword_matches * 4.0

        size_gb = max(0.1, profile.size_gb)
        size_score = 10.0 / size_gb
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

    def select_model_for_task(self, task: str, complexity_score: float = 0.0) -> str:
        return self.select_model(task, complexity_score=complexity_score)

    def record_verdict(self, model: str, passed: bool, seconds: float) -> None:
        """
        Record one output of `model` that a check outside the model judged:
        `passed` only when that check accepted it. Output nobody checked, or a
        check that did not run, is not a verdict and must not be recorded.
        """
        name = (model or "").strip()
        if not name or name in ("mock", "auto"):
            return
        # Several routers share the file (one per "auto" agent); start from
        # what is on disk so one does not overwrite another's verdicts.
        if self._persist:
            self._read_disk_verified()
        v = self.verified.setdefault(name, {"passed": 0, "failed": 0, "seconds": 0.0})
        v["passed" if passed else "failed"] += 1
        v["seconds"] += max(0.0, float(seconds))
        self._save_history(verdict_added=True)

    def record_result(self, task: str, complexity: float, model_used: str,
                     response_time: float, success: bool):
        """
        Record that a call returned (`success`: the provider gave any text).
        Kept for usage stats only; it says nothing about whether the output
        worked, so routing does not read it -- see `record_verdict`.
        """
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
        """
        `success_rate` is the share of calls that returned text, not of
        outputs that worked; `verified_*` counts outputs an outside check
        judged, and is what routing uses.
        """
        perf = self.model_performance[model_name]
        v = self.verified.get(model_name, {"passed": 0, "failed": 0, "seconds": 0.0})
        judged = {"verified_passed": int(v["passed"]), "verified_failed": int(v["failed"])}
        if perf["uses"] == 0:
            return {
                "uses": 0,
                "success_rate": 0.0,
                "avg_time": 0.0,
                **judged,
            }

        return {
            "uses": perf["uses"],
            "success_rate": perf["success_count"] / perf["uses"],
            "avg_time": perf["total_time"] / perf["uses"],
            **judged,
        }

    def classify_task_tier(self, task: str) -> Dict[str, Any]:
        """Classifies task intent into fast, standard, or reasoning tier.

        Hybrid with Laya (an open 421M local decision model): the keyword
        classifier below runs first and its answer is the default. Laya is
        then asked a single "how much reasoning does this need" question
        and consulted only for an upgrade -- if it answers "reasoning", the
        result becomes the reasoning tier regardless of what the keywords
        said; any other Laya answer, or no usable Laya at all, leaves the
        keyword answer untouched.

        This asymmetric combination is what was actually measured on 30
        hand-labelled tasks: keyword alone 21/30 (reasoning recall only
        4/10), Laya alone 23/30 (9/10 on reasoning, but worse on fast and
        standard), "Laya upgrades to reasoning, else keep keyword" 25/30.
        Replacing the keyword answer outright with Laya's, instead of only
        upgrading, was the worse of the two combinations on the same data.
        """
        result = self._classify_task_tier_keyword(task)
        result["decided_by"] = "keyword"

        # An explicitly injected agent (tests) is used regardless of the
        # test-mode gate below -- that gate exists to stop the real 421M
        # model from being lazily loaded under pytest, not to block a fake
        # agent a test deliberately wired in.
        agent = self.laya_agent
        if agent is None:
            if not _laya_enabled():
                return result
            agent, load_reason = _get_laya_agent()
            if agent is None:
                result["laya_note"] = load_reason
                return result

        try:
            answer = agent.predict(task, _LAYA_TIER_QUESTION)["answers"]["tier"]["choice"]
        except Exception as err:
            result["laya_note"] = f"laya predict raised: {err}"
            return result

        if answer == "reasoning" and result["tier"] != "reasoning":
            result = {
                "tier": "reasoning",
                "estimated_complexity": 8.5,
                "recommended_model": self.select_model(task, complexity_score=8.5),
                "rationale": "Laya decision model judged this task to need architectural reasoning.",
                "decided_by": "laya+keyword",
            }
        else:
            result["decided_by"] = "laya+keyword"

        return result

    def _classify_task_tier_keyword(self, task: str) -> Dict[str, Any]:
        """The original keyword-only tier classifier, unchanged.

        Kept as its own method so classify_task_tier can compute the
        keyword answer once and use it both as the default result and as
        the thing Laya's answer is measured against.
        """
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

    def classify_tier_via_rust(
        self,
        task: str,
        privacy_required: bool = False,
        max_budget_usd: float = 0.0,
    ) -> Dict[str, Any]:
        """Ask the compiled Rust router which *tier* a task belongs to, then
        pick a concrete installed model within that tier here.

        The two routers decide genuinely different things and neither
        replaces the other:

        * The Rust side (rust/crates/agent-inference-router) decides the
          execution tier -- local model, decentralized GPU node, or premium
          cloud API -- from a numeric complexity score, a privacy flag, and a
          registry of nodes with real load/latency/cost figures.
        * This class decides *which installed Ollama model* to use, from
          measured per-model history, keyword fit, and thermal state.

        So the honest composition is: Rust picks the tier, Python picks the
        model inside it. The Rust router is consulted, never obeyed blindly --
        if its answer is a tier this machine cannot serve (no decentralized
        nodes are registered in a local dev setup, and no cloud key is
        configured), the local selection still stands and the result says so.

        Returns the existing classify_task_tier() dict plus `rust_*` keys, so
        every existing caller keeps working unchanged. `rust_available` is
        False -- with a reason -- when the extension is not built, rather than
        a fabricated tier.
        """
        base = self.classify_task_tier(task)

        from saleha.core.platform.inference_router_bridge import rust_inference_router

        if not rust_inference_router.is_available():
            base["rust_available"] = False
            base["rust_reason"] = (
                rust_inference_router.import_error()
                or "inference_router extension not built"
            )
            return base

        # classify_task_tier scores 0-10; the Rust router takes 0.0-1.0.
        # Converting rather than passing the raw number is the whole reason
        # this wrapper exists -- handing 8.5 to a router that treats >0.8 as
        # "premium" would send every standard task to a paid API.
        complexity_0_to_1 = min(1.0, max(0.0, base["estimated_complexity"] / 10.0))

        try:
            decision = rust_inference_router.route(
                task_id=self._get_task_hash(task, base["estimated_complexity"]),
                prompt=task,
                complexity_score=complexity_0_to_1,
                privacy_required=privacy_required,
                max_budget_usd=max_budget_usd,
            )
        except Exception as err:  # extension present but the call failed
            base["rust_available"] = False
            base["rust_reason"] = f"rust route() raised: {err}"
            return base

        base["rust_available"] = True
        base["rust_target"] = decision["target"]
        base["rust_node_id"] = decision["node_id"]
        base["rust_estimated_latency_ms"] = decision["estimated_latency_ms"]
        base["rust_estimated_cost_usd"] = decision["estimated_cost_usd"]
        base["rust_complexity_score"] = complexity_0_to_1
        # Whether the tier the Rust side chose is one this machine can serve.
        # Only the local tier is; saying so here keeps a caller from treating
        # "Decentralized-GPU" as a thing that will actually happen.
        base["rust_tier_is_servable_locally"] = decision["target"].startswith("Local")
        return base

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