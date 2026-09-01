"""
Non-Euclidean Hyperbolic Poincaré & Lorentz Dual Engine with Multi-Attractor Energy Landscape.
Implements:
- Poincaré Ball (||u|| < 1.0) and Lorentz Hyperboloid dual coordinates
- 10-Department Canonical Attractor Basins (A1..A10)
- Potential Energy Surface Minimization: E(St) = min_k ||St ⊖ Ak||_H
- S.A.M.H. Multi-Attractor Steering Vector Injection
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

HYPERBOLIC_DIM = 16
CURVATURE_C = 1.0
EPSILON_BOUNDARY = 0.9999


@dataclass
class HyperbolicVector:
    """16-Dimensional Coordinate Vector inside the Poincaré Unit Ball (||u|| < 1.0)."""

    coords: List[float] = field(default_factory=lambda: [0.0] * HYPERBOLIC_DIM)

    def __post_init__(self):
        if len(self.coords) != HYPERBOLIC_DIM:
            self.coords = (self.coords + [0.0] * HYPERBOLIC_DIM)[:HYPERBOLIC_DIM]
        self._enforce_poincare_boundary()

    def _enforce_poincare_boundary(self):
        norm_sq = sum(x * x for x in self.coords)
        if norm_sq >= (EPSILON_BOUNDARY * EPSILON_BOUNDARY):
            scale = EPSILON_BOUNDARY / math.sqrt(norm_sq + 1e-7)
            self.coords = [x * scale for x in self.coords]

    @classmethod
    def zero(cls) -> HyperbolicVector:
        return cls([0.0] * HYPERBOLIC_DIM)

    @classmethod
    def from_bytes(cls, data: bytes) -> HyperbolicVector:
        """Projects raw bytes into bounded Poincaré Ball coordinates."""
        raw_list = list(data)
        coords = [0.0] * HYPERBOLIC_DIM
        for i in range(min(12, len(raw_list))):
            coords[i] = (raw_list[i] / 255.0) - 0.5

        # Structural invariant telemetry in remaining 4 dimensions
        if len(raw_list) >= 12:
            coords[12] = (raw_list[0] ^ raw_list[11]) / 512.0
            coords[13] = (raw_list[1] ^ raw_list[10]) / 512.0
            coords[14] = (raw_list[2] ^ raw_list[9]) / 512.0
            coords[15] = (raw_list[3] ^ raw_list[8]) / 512.0

        return cls(coords)

    def inner_product(self, other: HyperbolicVector) -> float:
        return sum(a * b for a, b in zip(self.coords, other.coords))

    def norm_squared(self) -> float:
        return self.inner_product(self)

    def to_lorentz_coordinates(self) -> Tuple[float, List[float]]:
        """
        Converts Poincaré Ball vector to Lorentz Hyperboloid coordinates:
        (x_0, x_1..x_d) where x_0^2 - sum(x_i^2) = 1
        Eliminates numerical underflow near boundary.
        """
        u_sq = self.norm_squared()
        denom = max(1e-7, 1.0 - u_sq)
        x_0 = (1.0 + u_sq) / denom
        spatial = [(2.0 * u_i) / denom for u_i in self.coords]
        return x_0, spatial

    def mobius_addition(self, v: HyperbolicVector) -> HyperbolicVector:
        """
        Branchless Möbius Gyrovector Addition on Poincaré Manifold:
        u ⊕ v = [(1 + 2<u,v> + |v|^2)u + (1 - |u|^2)v] / [1 + 2<u,v> + |u|^2|v|^2]
        """
        u_dot_v = self.inner_product(v)
        u_sq = self.norm_squared()
        v_sq = v.norm_squared()

        coeff_u = 1.0 + (2.0 * u_dot_v) + v_sq
        coeff_v = 1.0 - u_sq
        denom = max(1e-7, 1.0 + (2.0 * u_dot_v) + (u_sq * v_sq))
        inv_denom = 1.0 / denom

        new_coords = [
            ((coeff_u * u_i) + (coeff_v * v_i)) * inv_denom
            for u_i, v_i in zip(self.coords, v.coords)
        ]
        return HyperbolicVector(new_coords)

    def hyperbolic_distance(self, other: HyperbolicVector) -> float:
        """
        Geodesic Distance on the Poincaré Ball:
        d_H(u, v) = arcosh(1 + 2*||u - v||^2 / ((1 - ||u||^2)(1 - ||v||^2)))
        """
        diff_sq = sum((a - b) ** 2 for a, b in zip(self.coords, other.coords))
        u_sq = self.norm_squared()
        v_sq = other.norm_squared()

        denom = max(1e-7, (1.0 - u_sq) * (1.0 - v_sq))
        delta = (2.0 * diff_sq) / denom
        val = 1.0 + delta
        # arcosh(val) = ln(val + sqrt(val^2 - 1))
        return math.log(val + math.sqrt(max(0.0, val * val - 1.0)))


class MultiAttractorLandscape:
    """
    10-Department Multi-Attractor Potential Energy Landscape:
    Assigns target basins for Kernel, Security, Math, RAG, Swarms, etc.
    """

    DEPARTMENT_ATTRACTORS: Dict[str, HyperbolicVector] = {
        "FOUNDATION_REASONING": HyperbolicVector([0.15, -0.20, 0.30, 0.05, -0.10, 0.15, -0.05, 0.20, 0.10, -0.10, 0.05, -0.05, 0.08, -0.08, 0.04, -0.04]),
        "GENAI_MULTIMODAL":     HyperbolicVector([-0.20, 0.15, -0.10, 0.25, 0.05, -0.15, 0.20, -0.10, 0.05, 0.10, -0.15, 0.05, -0.05, 0.05, -0.02, 0.02]),
        "AGENTIC_SWARMS":       HyperbolicVector([0.05, 0.25, -0.20, 0.15, -0.05, 0.10, -0.15, 0.05, 0.20, -0.05, 0.10, -0.10, 0.04, -0.04, 0.02, -0.02]),
        "ADVANCED_RAG":         HyperbolicVector([-0.10, -0.15, 0.25, -0.05, 0.20, -0.10, 0.05, -0.20, 0.15, 0.05, -0.10, 0.05, -0.03, 0.03, -0.01, 0.01]),
        "SYSTEMS_KERNEL":       HyperbolicVector([0.30, 0.05, -0.15, -0.20, 0.25, 0.10, -0.05, 0.15, -0.20, 0.05, 0.10, -0.05, 0.10, -0.10, 0.05, -0.05]),
        "AIOPS_INFRA":          HyperbolicVector([-0.25, -0.10, 0.15, 0.20, -0.15, 0.05, 0.10, -0.05, 0.25, -0.10, 0.05, -0.05, -0.08, 0.08, -0.04, 0.04]),
        "SECURITY_GOVERNANCE":  HyperbolicVector([0.10, -0.30, 0.20, 0.05, -0.25, 0.15, -0.10, 0.05, -0.15, 0.20, 0.05, -0.10, 0.06, -0.06, 0.03, -0.03]),
        "PHYSICAL_ROBOTICS":    HyperbolicVector([-0.15, 0.20, -0.25, 0.10, 0.05, -0.20, 0.15, -0.05, 0.10, -0.15, 0.20, 0.05, -0.04, 0.04, -0.02, 0.02]),
        "QUANTUM_PHYSICS":      HyperbolicVector([0.20, -0.10, 0.05, -0.25, 0.15, -0.05, 0.20, -0.15, 0.05, 0.10, -0.05, 0.25, 0.07, -0.07, 0.03, -0.03]),
        "ENTERPRISE_AI":        HyperbolicVector([0.00, 0.10, -0.05, 0.20, -0.10, 0.05, -0.20, 0.15, -0.05, 0.25, -0.10, 0.05, 0.02, -0.02, 0.01, -0.01]),
    }

    def __init__(self, default_drift_threshold: float = 1.5):
        self.drift_threshold = default_drift_threshold

    def find_nearest_attractor(self, current_state: HyperbolicVector) -> Tuple[str, HyperbolicVector, float]:
        """Calculates E(S_t) = min_k ||S_t ⊖ A_k||_H across all 10 basins."""
        best_dept = "SYSTEMS_KERNEL"
        best_attr = self.DEPARTMENT_ATTRACTORS[best_dept]
        min_dist = float("inf")

        for dept, attr in self.DEPARTMENT_ATTRACTORS.items():
            dist = current_state.hyperbolic_distance(attr)
            if dist < min_dist:
                min_dist = dist
                best_dept = dept
                best_attr = attr

        return best_dept, best_attr, min_dist

    def apply_multi_attractor_healing(
        self, current_state: HyperbolicVector, target_dept: Optional[str] = None
    ) -> Tuple[HyperbolicVector, bool, str, float]:
        """
        Steers state vector towards the designated or lowest-energy department attractor.
        """
        if target_dept and target_dept in self.DEPARTMENT_ATTRACTORS:
            dept = target_dept
            attr = self.DEPARTMENT_ATTRACTORS[dept]
            dist = current_state.hyperbolic_distance(attr)
        else:
            dept, attr, dist = self.find_nearest_attractor(current_state)

        if dist <= self.drift_threshold:
            return current_state, False, dept, dist

        # Calculate steering vector towards chosen attractor basin
        delta = [
            (attr_i - cur_i) * 0.75
            for attr_i, cur_i in zip(attr.coords, current_state.coords)
        ]
        steering_vec = HyperbolicVector(delta)
        healed_state = current_state.mobius_addition(steering_vec)
        healed_dist = healed_state.hyperbolic_distance(attr)

        return healed_state, True, dept, healed_dist


class SAMHAttractorController:
    """Backward-compatible adapter for single & multi-attractor workflows."""

    def __init__(self, drift_threshold: float = 1.5):
        self.landscape = MultiAttractorLandscape(default_drift_threshold=drift_threshold)
        self.canonical_attractor = self.landscape.DEPARTMENT_ATTRACTORS["SYSTEMS_KERNEL"]
        self.drift_threshold = drift_threshold

    def evaluate_drift(self, current_state: HyperbolicVector) -> Tuple[float, bool]:
        dist = current_state.hyperbolic_distance(self.canonical_attractor)
        return dist, dist > self.drift_threshold

    def apply_self_healing_step(self, current_state: HyperbolicVector) -> Tuple[HyperbolicVector, bool, float]:
        healed, was_healed, dept, dist = self.landscape.apply_multi_attractor_healing(
            current_state, target_dept="SYSTEMS_KERNEL"
        )
        return healed, was_healed, dist
