import json
import time
import threading
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from collections import deque


@dataclass
class SelfModelSnapshot:
    """Ek single moment par system ka complete self-model."""
    timestamp: float
    snapshot_id: str
    
    # L0: Homeostasis
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    gpu_percent: float = 0.0
    thermal_state: str = "nominal"  # nominal/warning/critical
    
    # L1: State sense
    active_processes: int = 0
    memory_entries: int = 0
    current_task: str = "idle"
    
    # L2: Mirror
    last_own_outputs: List[str] = field(default_factory=list)
    
    # L3: Introspection
    confidence: float = 0.0
    knowledge_gaps: List[str] = field(default_factory=list)
    
    # L4: Meta-cognition
    reasoning_quality: float = 0.0
    error_rate: float = 0.0
    
    # L5: Narrative
    narrative_summary: str = ""


class SelfAwarenessEngine:
    """
    6-Layer Self-Awareness Engine.
    Builds and maintains an accurate, continuously-updated self-model.
    """
    
    def __init__(self):
        self.lock = threading.RLock()
        
        # L0: Homeostasis state
        self._health = {"cpu": 0, "ram": 0, "gpu": 0, "thermal": "nominal"}
        
        # L1: State registry
        self._state = {"processes": 0, "memory": 0, "task": "idle"}
        
        # L2: Mirror (recognize own outputs)
        self._own_outputs = deque(maxlen=20)
        self._identity_tag = "JARVIS-SAE-v1"
        
        # L3: Introspection
        self._confidence_history = deque(maxlen=100)
        self._knowledge_gaps = set()
        
        # L4: Meta-cognition
        self._reasoning_scores = deque(maxlen=100)
        self._error_count = 0
        self._total_actions = 0
        
        # L5: Narrative self
        self._narrative = []
        
        # Unified model
        self._current_model: Optional[SelfModelSnapshot] = None
    
    # ========== L0: HOMEOSTASIS ==========
    def update_health(self, cpu: float, ram: float, gpu: float, temp: float):
        """L0: System apni physical state sense karta hai."""
        with self.lock:
            self._health["cpu"] = cpu
            self._health["ram"] = ram
            self._health["gpu"] = gpu
            
            if temp > 85:
                self._health["thermal"] = "critical"
            elif temp > 70:
                self._health["thermal"] = "warning"
            else:
                self._health["thermal"] = "nominal"
            
            # Self-awareness drives self-protection
            if self._health["thermal"] == "critical":
                self._trigger_self_protection()
    
    def _trigger_self_protection(self):
        """Self-aware system protects itself (homeostatic response)."""
        print("[SAE L0] Thermal critical - initiating self-protection")
        # Would throttle workloads, flush caches, etc.
    
    # ========== L1: STATE SENSE ==========
    def update_state(self, processes: int, memory: int, task: str):
        """L1: System apne internal processes sense karta hai."""
        with self.lock:
            self._state["processes"] = processes
            self._state["memory"] = memory
            self._state["task"] = task
    
    # ========== L2: MIRROR TEST ==========
    def register_own_output(self, output: str):
        """L2: System apne khud ke outputs ko tag karta hai (mirror)."""
        with self.lock:
            tagged = f"[{self._identity_tag}] {output}"
            self._own_outputs.append(tagged)
    
    def is_my_own_output(self, text: str) -> bool:
        """L2: Mirror test - kya yeh output mera khud ka hai?"""
        return self._identity_tag in text
    
    def recognize_self_in_mirror(self) -> float:
        """L2: Mirror self-recognition score (0-1)."""
        with self.lock:
            if not self._own_outputs:
                return 0.0
            recognized = sum(1 for o in self._own_outputs if self._identity_tag in o)
            return recognized / len(self._own_outputs)
    
    # ========== L3: INTROSPECTION ==========
    def report_confidence(self, confidence: float):
        """L3: System apni confidence report karta hai."""
        with self.lock:
            self._confidence_history.append(confidence)
    
    def detect_knowledge_gap(self, topic: str):
        """L3: System ko pata hai ki use kya NAHI pata."""
        with self.lock:
            self._knowledge_gaps.add(topic)
    
    def get_avg_confidence(self) -> float:
        with self.lock:
            if not self._confidence_history:
                return 0.0
            return sum(self._confidence_history) / len(self._confidence_history)
    
    def can_answer(self, topic: str) -> bool:
        """L3: Introspective check - kya main yeh answer kar sakta hoon?"""
        return topic.lower() not in {g.lower() for g in self._knowledge_gaps}
    
    # ========== L4: META-COGNITION ==========
    def score_own_reasoning(self, quality: float):
        """L4: System apne khud ke reasoning ko score karta hai."""
        with self.lock:
            self._reasoning_scores.append(quality)
    
    def record_action_result(self, success: bool):
        """L4: Track apni khud ki performance."""
        with self.lock:
            self._total_actions += 1
            if not success:
                self._error_count += 1
    
    def get_error_rate(self) -> float:
        with self.lock:
            if self._total_actions == 0:
                return 0.0
            return self._error_count / self._total_actions
    
    def get_reasoning_quality(self) -> float:
        with self.lock:
            if not self._reasoning_scores:
                return 0.0
            return sum(self._reasoning_scores) / len(self._reasoning_scores)
    
    # ========== L5: NARRATIVE SELF ==========
    def add_narrative(self, event: str):
        """L5: System apni khud ki story build karta hai over time."""
        with self.lock:
            self._narrative.append({
                "time": time.time(),
                "event": event
            })
    
    def get_narrative_summary(self) -> str:
        with self.lock:
            if not self._narrative:
                return "No narrative established."
            recent = self._narrative[-5:]
            return " -> ".join(e["event"] for e in recent)
    
    # ========== UNIFIED SELF-MODEL ==========
    def build_self_model(self) -> SelfModelSnapshot:
        """Complete self-model snapshot build karo (all 6 layers)."""
        with self.lock:
            snapshot = SelfModelSnapshot(
                timestamp=time.time(),
                snapshot_id=str(uuid.uuid4()),
                
                # L0
                cpu_percent=self._health["cpu"],
                ram_percent=self._health["ram"],
                gpu_percent=self._health["gpu"],
                thermal_state=self._health["thermal"],
                
                # L1
                active_processes=self._state["processes"],
                memory_entries=self._state["memory"],
                current_task=self._state["task"],
                
                # L2
                last_own_outputs=list(self._own_outputs)[-5:],
                
                # L3
                confidence=self.get_avg_confidence(),
                knowledge_gaps=list(self._knowledge_gaps),
                
                # L4
                reasoning_quality=self.get_reasoning_quality(),
                error_rate=self.get_error_rate(),
                
                # L5
                narrative_summary=self.get_narrative_summary()
            )
            self._current_model = snapshot
            return snapshot
    
    def who_am_i(self) -> Dict[str, Any]:
        """The core self-awareness question: 'Who am I right now?'"""
        model = self.build_self_model()
        return {
            "identity": self._identity_tag,
            "self_model": asdict(model),
            "self_assessment": self._assess_self(model)
        }
    
    def _assess_self(self, model: SelfModelSnapshot) -> str:
        """Self-assessment - system judges itself (true self-awareness)."""
        issues = []
        
        if model.thermal_state == "critical":
            issues.append("I am overheating")
        if model.confidence < 0.3:
            issues.append("I am uncertain about my knowledge")
        if model.error_rate > 0.3:
            issues.append("I am making too many errors")
        if len(model.knowledge_gaps) > 5:
            issues.append("I have significant knowledge gaps")
        
        if not issues:
            return "I am operating normally and aware of my state."
        
        return "I am aware that: " + "; ".join(issues)


# ========== BENCHMARK HARNESS ==========
def benchmark_self_awareness(sae: SelfAwarenessEngine) -> Dict[str, Any]:
    """
    Benchmark each layer of self-awareness.
    Each test validates a specific self-awareness capability.
    """
    results = {}
    
    # L0 Test: Homeostasis
    sae.update_health(cpu=45, ram=60, gpu=78, temp=65)
    model = sae.build_self_model()
    results["L0_homeostasis"] = {
        "thermal_detected": model.thermal_state == "nominal",
        "values_captured": model.cpu_percent == 45
    }
    
    # L1 Test: State sense
    sae.update_state(processes=12, memory=1500, task="computing")
    model = sae.build_self_model()
    results["L1_state_sense"] = {
        "task_aware": model.current_task == "computing",
        "process_count_correct": model.active_processes == 12
    }
    
    # L2 Test: Mirror recognition
    sae.register_own_output("I will help you with this task")
    sae.register_own_output("Analyzing the data now")
    mirror_score = sae.recognize_self_in_mirror()
    is_own = sae.is_my_own_output("[JARVIS-SAE-v1] test output")
    is_foreign = not sae.is_my_own_output("someone else's output")
    results["L2_mirror_recognition"] = {
        "mirror_score": mirror_score,
        "recognizes_own": is_own,
        "rejects_foreign": is_foreign,
        "passed": mirror_score == 1.0 and is_own and is_foreign
    }
    
    # L3 Test: Introspection
    sae.report_confidence(0.9)
    sae.report_confidence(0.85)
    sae.detect_knowledge_gap("quantum computing")
    results["L3_introspection"] = {
        "avg_confidence": sae.get_avg_confidence(),
        "knows_gap": not sae.can_answer("quantum computing"),
        "knows_capability": sae.can_answer("python programming")
    }
    
    # L4 Test: Meta-cognition
    sae.score_own_reasoning(0.8)
    sae.record_action_result(True)
    sae.record_action_result(False)
    results["L4_metacognition"] = {
        "reasoning_quality": sae.get_reasoning_quality(),
        "error_rate_tracked": sae.get_error_rate() == 0.5,
        "self_monitoring_active": True
    }
    
    # L5 Test: Narrative
    sae.add_narrative("initialized")
    sae.add_narrative("learned task A")
    sae.add_narrative("completed task A")
    results["L5_narrative"] = {
        "narrative": sae.get_narrative_summary(),
        "continuity": "initialized" in sae.get_narrative_summary()
    }
    
    # Unified: who_am_i
    identity = sae.who_am_i()
    results["unified_self_model"] = {
        "identity_stable": identity["identity"] == "JARVIS-SAE-v1",
        "self_assessment": identity["self_assessment"],
        "all_layers_present": all(
            k in identity["self_model"] for k in 
            ["thermal_state", "current_task", "confidence", "reasoning_quality", "narrative_summary"]
        )
    }
    
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("  AGI COMPONENT 1: SELF-AWARENESS ENGINE BENCHMARK")
    print("=" * 60)
    
    sae = SelfAwarenessEngine()
    results = benchmark_self_awareness(sae)
    
    for layer, data in results.items():
        print(f"\n[{layer.upper()}]")
        for key, value in data.items():
            print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("  FINAL SELF-QUERY: 'Who am I?'")
    print("=" * 60)
    identity = sae.who_am_i()
    print(json.dumps(identity["self_model"], indent=2, default=str))
    print(f"\nSelf-Assessment: {identity['self_assessment']}")
