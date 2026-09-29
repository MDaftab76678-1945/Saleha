"""
Saleha Core: learned Poincare-ball graph embeddings (Nickel & Kiela, 2017).

Trains one coordinate vector per graph node so that neighbours sit close
under a chosen metric. The same trainer runs in two geometries so they can
be compared on equal terms:

- ``poincare``: d(u, v) = arcosh(1 + 2|u-v|^2 / ((1-|u|^2)(1-|v|^2))) inside
  the unit ball, updated with Riemannian SGD (the Euclidean gradient scaled
  by (1-|x|^2)^2 / 4, then projected back inside the ball).
- ``euclidean``: d(u, v) = |u-v| with ordinary SGD -- the control.

Loss per edge (u, v): -log(exp(-d(u,v)) / sum of exp(-d(u,v')) over v and
the sampled negatives v'), negatives drawn uniformly from nodes not adjacent
to u.

Nothing here claims hyperbolic space is better. ``reconstruction_map``
measures how well a trained embedding recovers the graph it was trained on,
which compares the two geometries at the same dimension; whether that helps
any downstream task is measured separately (``cochange_bench``).

``saleha/core/research/hyperbolic_engine.py`` is unrelated: it places raw bytes in
the ball with a fixed formula and learns nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Tuple

import numpy as np

GEOMETRIES = ("poincare", "euclidean")

_BOUNDARY_EPS = 1e-5
_TINY = 1e-12


def poincare_distance(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Poincare-ball distance along the last axis (broadcasts)."""
    sq_u = np.sum(u * u, axis=-1)
    sq_v = np.sum(v * v, axis=-1)
    sq_diff = np.sum((u - v) ** 2, axis=-1)
    alpha = np.maximum(1.0 - sq_u, _TINY)
    beta = np.maximum(1.0 - sq_v, _TINY)
    gamma = 1.0 + 2.0 * sq_diff / (alpha * beta)
    return np.arccosh(np.maximum(gamma, 1.0))


def euclidean_distance(u: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Plain Euclidean distance along the last axis (broadcasts)."""
    return np.sqrt(np.sum((u - v) ** 2, axis=-1))


def distance(u: np.ndarray, v: np.ndarray, geometry: str) -> np.ndarray:
    if geometry == "poincare":
        return poincare_distance(u, v)
    if geometry == "euclidean":
        return euclidean_distance(u, v)
    raise ValueError(f"unknown geometry {geometry!r}; expected one of {GEOMETRIES}")


def _poincare_dist_and_grads(
    u: np.ndarray, v: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Distance plus its Euclidean gradients w.r.t. u and v (same shapes)."""
    sq_u = np.sum(u * u, axis=-1, keepdims=True)
    sq_v = np.sum(v * v, axis=-1, keepdims=True)
    uv = np.sum(u * v, axis=-1, keepdims=True)
    sq_diff = np.sum((u - v) ** 2, axis=-1, keepdims=True)
    alpha = np.maximum(1.0 - sq_u, _TINY)
    beta = np.maximum(1.0 - sq_v, _TINY)
    gamma = np.maximum(1.0 + 2.0 * sq_diff / (alpha * beta), 1.0)
    denom = np.sqrt(np.maximum(gamma * gamma - 1.0, _TINY))
    grad_u = (4.0 / (beta * denom)) * ((sq_v - 2.0 * uv + 1.0) / (alpha * alpha) * u - v / alpha)
    grad_v = (4.0 / (alpha * denom)) * ((sq_u - 2.0 * uv + 1.0) / (beta * beta) * v - u / beta)
    return np.arccosh(gamma[..., 0]), grad_u, grad_v


def _euclidean_dist_and_grads(
    u: np.ndarray, v: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    diff = u - v
    dist = np.sqrt(np.sum(diff * diff, axis=-1, keepdims=True))
    grad_u = diff / np.maximum(dist, _TINY)
    return dist[..., 0], grad_u, -grad_u


def _project_into_ball(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    limit = 1.0 - _BOUNDARY_EPS
    scale = np.where(norms >= limit, limit / np.maximum(norms, _TINY), 1.0)
    return x * scale


def _symmetric_pairs(edges: Iterable[Tuple[int, int]], n_nodes: int) -> np.ndarray:
    seen = set()
    for a, b in edges:
        if not (0 <= a < n_nodes and 0 <= b < n_nodes):
            raise ValueError(f"edge ({a}, {b}) out of range for {n_nodes} nodes")
        if a == b:
            continue
        seen.add((a, b))
        seen.add((b, a))
    return np.array(sorted(seen), dtype=np.int64).reshape(-1, 2)


@dataclass
class EmbeddingResult:
    geometry: str
    dim: int
    lr: float
    epochs: int
    coords: np.ndarray
    loss_history: List[float]

    @property
    def final_loss(self) -> float:
        return self.loss_history[-1]


def train_embedding(
    edges: Iterable[Tuple[int, int]],
    n_nodes: int,
    dim: int,
    geometry: str = "poincare",
    epochs: int = 200,
    lr: float = 0.3,
    negatives: int = 20,
    batch_size: int = 256,
    burn_in: int = 10,
    seed: int = 0,
) -> EmbeddingResult:
    """Train node coordinates on ``edges`` (treated as undirected).

    Raises instead of returning an embedding when there is nothing to learn
    from (no edges) or training diverges (non-finite loss) -- an untrained
    or broken embedding must never look like a trained one.
    """
    if geometry not in GEOMETRIES:
        raise ValueError(f"unknown geometry {geometry!r}; expected one of {GEOMETRIES}")
    if n_nodes < 2 or dim < 1 or epochs < 1 or negatives < 1 or batch_size < 1:
        raise ValueError("need n_nodes >= 2 and positive dim, epochs, negatives, batch_size")

    pairs = _symmetric_pairs(edges, n_nodes)
    if len(pairs) == 0:
        raise ValueError("no edges between distinct nodes; nothing to train on")
    adjacency_keys = np.unique(pairs[:, 0] * n_nodes + pairs[:, 1])

    rng = np.random.default_rng(seed)
    coords = rng.uniform(-1e-3, 1e-3, size=(n_nodes, dim))
    dist_and_grads = (
        _poincare_dist_and_grads if geometry == "poincare" else _euclidean_dist_and_grads
    )

    history: List[float] = []
    for epoch in range(epochs):
        step_lr = lr / 10.0 if epoch < burn_in else lr
        order = rng.permutation(len(pairs))
        epoch_loss = 0.0
        for start in range(0, len(order), batch_size):
            batch = pairs[order[start:start + batch_size]]
            u_idx = batch[:, 0]
            neg = rng.integers(0, n_nodes, size=(len(batch), negatives))
            cand = np.concatenate([batch[:, 1:2], neg], axis=1)
            # A "negative" that is u itself or one of u's neighbours is not a
            # negative; masking it (distance -> inf) removes it from the loss.
            invalid = (neg == u_idx[:, None]) | np.isin(u_idx[:, None] * n_nodes + neg, adjacency_keys)
            invalid = np.concatenate([np.zeros((len(batch), 1), dtype=bool), invalid], axis=1)

            u_vec = np.broadcast_to(coords[u_idx][:, None, :], (len(batch), cand.shape[1], dim))
            dists, grad_u, grad_c = dist_and_grads(u_vec, coords[cand])
            dists = np.where(invalid, np.inf, dists)

            nearest = dists.min(axis=1, keepdims=True)
            weights = np.exp(-(dists - nearest))
            totals = weights.sum(axis=1, keepdims=True)
            probs = weights / totals
            # loss = d_0 + logsumexp(-d), computed shift-stable
            epoch_loss += float(np.sum(dists[:, 0] - nearest[:, 0] + np.log(totals[:, 0])))

            # dL/dd_j = [j == 0] - p_j
            d_loss = -probs
            d_loss[:, 0] += 1.0
            grad = np.zeros_like(coords)
            np.add.at(grad, u_idx, np.sum(d_loss[..., None] * grad_u, axis=1))
            np.add.at(grad, cand.ravel(), (d_loss[..., None] * grad_c).reshape(-1, dim))

            if geometry == "poincare":
                scale = ((1.0 - np.sum(coords * coords, axis=1, keepdims=True)) ** 2) / 4.0
                coords = _project_into_ball(coords - step_lr * scale * grad)
            else:
                coords = coords - step_lr * grad

        mean_loss = epoch_loss / len(pairs)
        if not np.isfinite(mean_loss) or not np.all(np.isfinite(coords)):
            raise RuntimeError(
                f"{geometry} training diverged at epoch {epoch} (lr={lr}, dim={dim})"
            )
        history.append(mean_loss)

    return EmbeddingResult(geometry, dim, lr, epochs, coords, history)


def distances_from(coords: np.ndarray, index: int, geometry: str) -> np.ndarray:
    """Distance from node ``index`` to every node (itself included, at 0)."""
    return distance(coords[index][None, :], coords, geometry)


def reconstruction_map(
    coords: np.ndarray, geometry: str, edges: Iterable[Tuple[int, int]], chunk: int = 128
) -> float:
    """Mean average precision of each node's true neighbours when every
    other node is ranked by embedding distance. 1.0 = graph recovered
    exactly. Raises when the graph has no edges -- there is nothing to score.
    """
    n_nodes = coords.shape[0]
    pairs = _symmetric_pairs(edges, n_nodes)
    if len(pairs) == 0:
        raise ValueError("no edges; reconstruction MAP is undefined")
    neighbours: List[List[int]] = [[] for _ in range(n_nodes)]
    for a, b in pairs:
        neighbours[a].append(int(b))

    ap_values: List[float] = []
    for start in range(0, n_nodes, chunk):
        rows = np.arange(start, min(start + chunk, n_nodes))
        block = distance(coords[rows][:, None, :], coords[None, :, :], geometry)
        for offset, node in enumerate(rows):
            true = neighbours[node]
            if not true:
                continue
            row = block[offset].copy()
            row[node] = np.inf  # never rank a node against itself
            order = np.argsort(row, kind="stable")
            position = np.empty(n_nodes, dtype=np.int64)
            position[order] = np.arange(n_nodes)
            hits = np.sort(position[true])
            ap_values.append(float(np.mean(np.arange(1, len(hits) + 1) / (hits + 1))))
    return float(np.mean(ap_values))
