"""
Chain-Spike Engine (CSE) - Course Edition
-----------------------------------------
A teaching extract of the studied research engine ``chain_spike_phase0.py``
(SHA-256 433f9a66... with LF line endings; 66b3e7fe... as the Windows CRLF
working copy; last changed in commit 68e3d81).

Kept (the parts the course uses):
- Hebbian learning of direct edges (+ optional distance-2 context edges)
- activation injection, decay, cap, and Top-K spreading
- activation-history term, refractory inhibition
- capacity-limited ordered pair context (previous two symbols)
- optional slow context trace + projection
- softmax / linear Top-K probabilities, greedy and sampled generation,
  teacher-forced scoring

Research-engine features that the course does not use are omitted; all of them
are off by default in the research engine. For the configurations used in the
course, this file computes exactly the same values as the research engine
(checked bit-for-bit by a separate equivalence test).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class CSEConfig:
    max_nodes: int = 50
    learning_rate: float = 0.10
    max_edge_weight: float = 10.0
    weight_decay: float = 0.9995
    weight_decay_scope: str = "global"
    activation_decay: float = 0.60
    activation_cap: float = 0.0
    threshold: float = 0.05
    top_k_edges: int = 3
    temperature: float = 0.8
    probability_mode: str = "softmax"
    history_boost: float = 0.35
    refractory_steps: int = 2
    max_consecutive_repeats: int = 2
    temporal_learning_window: int = 1
    direct_learning_window: int = 2
    temporal_learning_decay: float = 0.50
    context_trace_decay: float = 0.0
    context_projection_boost: float = 0.0
    normalize_direct_scores: bool = False
    pair_context_capacity: int = 0
    pair_context_boost: float = 0.0
    seed: int = 42


class ChainSpikeEngine:
    def __init__(self, config: Optional[CSEConfig] = None):
        self.cfg = config or CSEConfig()
        if self.cfg.max_edge_weight <= 0.0:
            raise ValueError("max_edge_weight must be positive")
        if self.cfg.activation_cap < 0.0:
            raise ValueError("activation_cap must be non-negative")
        if self.cfg.pair_context_capacity < 0:
            raise ValueError("pair_context_capacity must be non-negative")
        if self.cfg.pair_context_boost < 0.0:
            raise ValueError("pair_context_boost must be non-negative")
        random.seed(self.cfg.seed)
        np.random.seed(self.cfg.seed)

        self.symbol_to_id: Dict[str, int] = {}
        self.id_to_symbol: List[str] = []

        self.weights = np.zeros(
            (self.cfg.max_nodes, self.cfg.max_nodes), dtype=np.float32
        )
        self.context_weights = np.zeros(
            (self.cfg.max_nodes, self.cfg.max_nodes), dtype=np.float32
        )
        self.activation = np.zeros(self.cfg.max_nodes, dtype=np.float32)
        self.context_trace = np.zeros(self.cfg.max_nodes, dtype=np.float32)
        self.frequency = np.zeros(self.cfg.max_nodes, dtype=np.int64)
        self.pair_context_weights: Dict[Tuple[int, int], np.ndarray] = {}

        self.total_training_steps = 0
        self.recent_fired: List[int] = []

        for symbol in ["<START>", "<END>", "<UNK>"]:
            self._ensure_node(symbol)

    @property
    def node_count(self) -> int:
        return len(self.id_to_symbol)

    def _ensure_node(self, symbol: str) -> int:
        if symbol in self.symbol_to_id:
            return self.symbol_to_id[symbol]

        if self.node_count >= self.cfg.max_nodes:
            return self.symbol_to_id["<UNK>"]

        idx = self.node_count
        self.symbol_to_id[symbol] = idx
        self.id_to_symbol.append(symbol)
        return idx

    def encode(self, text: str, allow_new: bool = True) -> List[int]:
        ids = []
        for symbol in text:
            if symbol in self.symbol_to_id:
                ids.append(self.symbol_to_id[symbol])
            elif allow_new:
                ids.append(self._ensure_node(symbol))
            else:
                ids.append(self.symbol_to_id["<UNK>"])
        return ids

    # ------------------------------------------------------------------ learning

    def train_text(self, text: str, epochs: int = 1) -> None:
        if not text:
            return

        start = self.symbol_to_id["<START>"]
        end = self.symbol_to_id["<END>"]
        seq = [start] + self.encode(text, allow_new=True) + [end]

        for _ in range(epochs):
            for position in range(1, len(seq)):
                b = seq[position]
                effective_learning_rate = self.cfg.learning_rate

                # Forget globally, or only within recently eligible source rows.
                if self.cfg.weight_decay_scope == "global":
                    self.weights *= self.cfg.weight_decay
                    self.context_weights *= self.cfg.weight_decay
                elif self.cfg.weight_decay_scope == "active_rows":
                    window = max(1, self.cfg.temporal_learning_window)
                    active_sources = {
                        seq[position - distance]
                        for distance in range(1, min(window, position) + 1)
                    }
                    for source_id in active_sources:
                        self.weights[source_id, :] *= self.cfg.weight_decay
                        self.context_weights[source_id, :] *= self.cfg.weight_decay
                else:
                    raise ValueError(
                        "weight_decay_scope must be 'global' or 'active_rows'"
                    )

                # Local Hebbian reinforcement. A window greater than one adds a
                # weak eligibility trace from recent non-control nodes.
                window = max(1, self.cfg.temporal_learning_window)
                for distance in range(1, min(window, position) + 1):
                    a = seq[position - distance]
                    if distance > 1:
                        source_is_control = self.id_to_symbol[a].startswith("<")
                        target_is_control = self.id_to_symbol[b].startswith("<")
                        if source_is_control or target_is_control:
                            continue
                    delta = effective_learning_rate * (
                        self.cfg.temporal_learning_decay ** (distance - 1)
                    )
                    direct_window = max(1, self.cfg.direct_learning_window)
                    matrix = (
                        self.weights
                        if distance <= direct_window
                        else self.context_weights
                    )
                    matrix[a, b] += delta
                    matrix[a, b] = min(
                        matrix[a, b], self.cfg.max_edge_weight
                    )

                if self.cfg.pair_context_capacity > 0 and position >= 2:
                    pair = (seq[position - 2], seq[position - 1])
                    if pair not in self.pair_context_weights:
                        if (
                            len(self.pair_context_weights)
                            >= self.cfg.pair_context_capacity
                        ):
                            weakest = min(
                                self.pair_context_weights,
                                key=lambda item: (
                                    float(self.pair_context_weights[item].sum()),
                                    item,
                                ),
                            )
                            self.pair_context_weights.pop(weakest)
                        self.pair_context_weights[pair] = np.zeros(
                            self.cfg.max_nodes, dtype=np.float32
                        )
                    pair_row = self.pair_context_weights[pair]
                    pair_row[b] = min(
                        pair_row[b] + effective_learning_rate,
                        self.cfg.max_edge_weight,
                    )

                a = seq[position - 1]
                self.frequency[a] += 1
                self.frequency[b] += 1
                self.total_training_steps += 1

    def train_corpus(self, texts: List[str], epochs: int = 1) -> None:
        for _ in range(epochs):
            for text in texts:
                self.train_text(text, epochs=1)

    # ----------------------------------------------------------------- dynamics

    def reset_state(self) -> None:
        self.activation.fill(0.0)
        self.context_trace.fill(0.0)
        self.recent_fired.clear()

    def effective_activation_cap(self) -> float:
        """Return the explicit cap or a conservative dtype-safe automatic cap."""
        if self.cfg.activation_cap < 0.0:
            raise ValueError("activation_cap must be non-negative")
        if self.cfg.activation_cap > 0.0:
            return float(self.cfg.activation_cap)

        denominator = (
            abs(self.cfg.activation_decay)
            + self.cfg.max_nodes * self.cfg.max_edge_weight
        )
        if not math.isfinite(denominator) or denominator <= 0.0:
            raise ValueError("automatic activation cap requires a finite positive bound")
        return float(
            0.5 * np.finfo(self.activation.dtype).max / denominator
        )

    def _remember_context(self, node_id: int) -> None:
        self.context_trace *= self.cfg.context_trace_decay
        self.context_trace[node_id] += 1.0

    def _inject(self, node_id: int, strength: float = 1.0) -> None:
        self.activation[node_id] += strength
        self.activation[node_id] = min(
            self.activation[node_id], self.effective_activation_cap()
        )

    def _propagate_once(self) -> np.ndarray:
        k = self.cfg.top_k_edges
        if (self.weights.dtype != np.float32
                or self.activation.dtype != np.float32
                or not isinstance(k, (int, np.integer)) or k < 0):
            return self._propagate_once_scalar()
        activation_cap = self.effective_activation_cap()
        np.clip(self.activation, 0.0, activation_cap, out=self.activation)
        old = self.activation.copy()
        self.activation *= self.cfg.activation_decay
        contribution = np.zeros_like(self.activation)
        active_sources = np.where(old >= self.cfg.threshold)[0]
        rows = self.weights[active_sources, :self.node_count]
        selected = rows > 0
        counts = selected.sum(axis=1)
        # k=0 selects every positive edge. For k>=count, selection order
        # within a source is irrelevant because each destination occurs once.
        if k > 0:
            for count in np.unique(counts[counts > k]):
                group = np.flatnonzero(counts == count)
                positive = np.nonzero(selected[group])[1].reshape(len(group), int(count))
                local = np.take_along_axis(rows[group], positive, axis=1)
                top = np.argpartition(local, -k, axis=1)[:, -k:]
                destinations = np.take_along_axis(positive, top, axis=1)
                selected[group] = False
                selected[group[:, None], destinations] = True
        source_rows, targets = np.nonzero(selected)
        sources = active_sources[source_rows]
        products = old[sources] * self.weights[sources, targets]
        # nonzero visits source rows in ascending order. add.at accumulates
        # repeated destinations in that order without a reassociated reduction.
        np.add.at(contribution, targets, products)
        self.activation += contribution
        np.clip(self.activation, 0.0, activation_cap, out=self.activation)
        return contribution

    def _propagate_once_scalar(self) -> np.ndarray:
        activation_cap = self.effective_activation_cap()
        np.clip(self.activation, 0.0, activation_cap, out=self.activation)
        old = self.activation.copy()
        self.activation *= self.cfg.activation_decay

        contribution = np.zeros_like(self.activation)
        active_sources = np.where(old >= self.cfg.threshold)[0]

        for src in active_sources:
            row = self.weights[src, : self.node_count]
            positive = np.where(row > 0)[0]
            if len(positive) == 0:
                continue

            k = min(self.cfg.top_k_edges, len(positive))
            local = row[positive]
            top_local = np.argpartition(local, -k)[-k:]
            destinations = positive[top_local]

            for dst in destinations:
                contribution[dst] += old[src] * row[dst]

        self.activation += contribution
        np.clip(self.activation, 0.0, activation_cap, out=self.activation)
        return contribution

    def _candidate_scores(self, current_id: int) -> np.ndarray:
        scores = self.weights[current_id, : self.node_count].astype(np.float64).copy()
        if self.cfg.normalize_direct_scores:
            score_total = scores[scores > 0].sum()
            if score_total > 0:
                scores /= score_total
        history = self.activation[: self.node_count].astype(np.float64).copy()

        # Control nodes may be selected through a learned direct edge, but their
        # residual activation is not linguistic context and must not be boosted.
        for symbol in ("<START>", "<UNK>"):
            history[self.symbol_to_id[symbol]] = 0.0
        end_id = self.symbol_to_id["<END>"]
        if scores[end_id] <= 0:
            history[end_id] = 0.0
        scores += self.cfg.history_boost * history

        if self.cfg.pair_context_boost > 0.0:
            if len(self.recent_fired) >= 2:
                pair = (self.recent_fired[-2], self.recent_fired[-1])
            elif len(self.recent_fired) == 1:
                pair = (self.symbol_to_id["<START>"], self.recent_fired[-1])
            else:
                pair = None
            pair_row = self.pair_context_weights.get(pair) if pair else None
            if pair_row is not None:
                pair_scores = pair_row[: self.node_count].astype(np.float64)
                pair_total = pair_scores[pair_scores > 0].sum()
                if pair_total > 0.0:
                    scores += self.cfg.pair_context_boost * (
                        pair_scores / pair_total
                    )

        if self.cfg.context_projection_boost > 0:
            reachable = scores > 0
            trace = self.context_trace[: self.node_count].astype(np.float64).copy()
            trace[current_id] = 0.0
            for symbol in ("<START>", "<END>", "<UNK>"):
                trace[self.symbol_to_id[symbol]] = 0.0
            direct = self.weights[: self.node_count, : self.node_count].astype(
                np.float64
            ).copy()
            context = self.context_weights[: self.node_count, : self.node_count].astype(
                np.float64
            ).copy()
            projection = trace @ (direct + context)
            projection[~reachable] = 0.0
            for symbol in ("<START>", "<END>", "<UNK>"):
                projection[self.symbol_to_id[symbol]] = 0.0
            scores += self.cfg.context_projection_boost * projection

        # START never appears as output.
        scores[self.symbol_to_id["<START>"]] = 0.0

        # Refractory inhibition prevents immediate re-selection loops.
        if self.cfg.refractory_steps > 0:
            for node_id in self.recent_fired[-self.cfg.refractory_steps:]:
                if 0 <= node_id < len(scores):
                    learned_self_edge = self.weights[current_id, node_id]
                    if node_id == current_id and learned_self_edge > 0:
                        consecutive = 0
                        for fired_id in reversed(self.recent_fired):
                            if fired_id != current_id:
                                break
                            consecutive += 1
                        if consecutive < self.cfg.max_consecutive_repeats:
                            continue
                    scores[node_id] = 0.0

        return scores

    def _probabilities(self, scores: np.ndarray) -> np.ndarray:
        """Convert candidate scores to the Top-K distribution used by generation."""
        if self.cfg.probability_mode not in {"softmax", "linear"}:
            raise ValueError("probability_mode must be 'softmax' or 'linear'")

        probabilities = np.zeros_like(scores, dtype=np.float64)
        positive = np.where(scores > 0)[0]
        if len(positive) == 0:
            probabilities[self.symbol_to_id["<END>"]] = 1.0
        else:
            k = min(self.cfg.top_k_edges, len(positive))
            local_scores = scores[positive]
            top_local = np.argpartition(local_scores, -k)[-k:]
            candidates = positive[top_local]
            cand_scores = scores[candidates]

            if self.cfg.probability_mode == "linear":
                probs = cand_scores / cand_scores.sum()
            else:
                t = max(self.cfg.temperature, 1e-6)
                logits = cand_scores / t
                logits -= np.max(logits)
                probs = np.exp(logits)
                probs /= probs.sum()
            probabilities[candidates] = probs

        return probabilities

    def _sample(self, scores: np.ndarray) -> int:
        probabilities = self._probabilities(scores)
        positive = np.where(probabilities > 0)[0]
        if len(positive) == 0:
            return self.symbol_to_id["<END>"]
        return int(np.random.choice(positive, p=probabilities[positive]))

    # -------------------------------------------------------------- public API

    def prime(self, prompt: str) -> int:
        self.reset_state()
        current = self.symbol_to_id["<START>"]
        for node_id in self.encode(prompt, allow_new=False):
            self._inject(current, 1.0)
            self._propagate_once()

            self._inject(node_id, 1.0)
            self._remember_context(node_id)
            current = node_id
            self.recent_fired.append(node_id)
        return current

    def next_node_distribution(self, prompt: str = "") -> Dict[str, float]:
        """Return the next-node distribution without sampling."""
        current = self.prime(prompt)
        self._inject(current, 1.0)
        self._propagate_once()
        probabilities = self._probabilities(self._candidate_scores(current))
        return {
            self.id_to_symbol[node_id]: float(probability)
            for node_id, probability in enumerate(probabilities)
            if probability > 0
        }

    def predict_next(self, prompt: str = "") -> str:
        """Return the deterministic argmax next node."""
        distribution = self.next_node_distribution(prompt)
        if not distribution:
            return "<END>"
        return max(distribution.items(), key=lambda item: item[1])[0]

    def score_text(
        self,
        text: str,
        *,
        probability_floor: float = 1e-9,
        include_end: bool = True,
    ) -> dict:
        """Teacher-force a text, one state transition per target."""
        if not 0.0 < probability_floor <= 1.0:
            raise ValueError("probability_floor must be in (0, 1]")
        targets = [*text, *(["<END>"] if include_end else [])]
        log_probability_sum = 0.0
        covered = 0
        correct = 0
        rows = []

        self.reset_state()
        current = self.symbol_to_id["<START>"]
        unk = self.symbol_to_id["<UNK>"]
        for position, target in enumerate(targets):
            self._inject(current, 1.0)
            self._propagate_once()
            probabilities = self._probabilities(self._candidate_scores(current))
            target_id = self.symbol_to_id.get(target, unk)
            probability = float(probabilities[target_id])
            positive = np.where(probabilities > 0.0)[0]
            predicted = (
                self.id_to_symbol[int(positive[np.argmax(probabilities[positive])])]
                if len(positive)
                else "<END>"
            )
            if probability > 0.0:
                covered += 1
            if predicted == target:
                correct += 1
            log_probability_sum += math.log(max(probability, probability_floor))
            rows.append(
                {
                    "position": position,
                    "target": target,
                    "predicted": predicted,
                    "probability": probability,
                }
            )

            if target != "<END>":
                self._inject(target_id, 1.0)
                self._remember_context(target_id)
                current = target_id
                self.recent_fired.append(target_id)

        count = len(targets)
        mean_nll = -log_probability_sum / count if count else 0.0
        return {
            "node_count": count,
            "mean_nll": mean_nll,
            "clipped_perplexity": math.exp(mean_nll),
            "next_node_accuracy": correct / count if count else 0.0,
            "target_coverage": covered / count if count else 1.0,
            "probability_floor": probability_floor,
            "rows": rows,
        }

    def generate(self, prompt: str = "", max_new_chars: int = 80) -> str:
        current = self.prime(prompt)
        output = list(prompt)
        end = self.symbol_to_id["<END>"]
        unk = self.symbol_to_id["<UNK>"]

        for _ in range(max_new_chars):
            self._inject(current, 1.0)
            self._propagate_once()
            next_id = self._sample(self._candidate_scores(current))
            if next_id == end:
                break
            if next_id != unk:
                symbol = self.id_to_symbol[next_id]
                if not symbol.startswith("<"):
                    output.append(symbol)
            current = next_id
            self._remember_context(next_id)
            self.recent_fired.append(next_id)

        return "".join(output)

    def generate_greedy(self, prompt: str = "", max_new_nodes: int = 80) -> str:
        """Generate deterministically, always taking the most probable node."""
        current = self.prime(prompt)
        output = list(prompt)
        end = self.symbol_to_id["<END>"]
        unk = self.symbol_to_id["<UNK>"]

        for _ in range(max_new_nodes):
            self._inject(current, 1.0)
            self._propagate_once()
            probabilities = self._probabilities(self._candidate_scores(current))
            next_id = int(np.argmax(probabilities))
            if probabilities[next_id] <= 0 or next_id == end:
                break
            if next_id != unk:
                symbol = self.id_to_symbol[next_id]
                if not symbol.startswith("<"):
                    output.append(symbol)
            current = next_id
            self._remember_context(next_id)
            self.recent_fired.append(next_id)

        return "".join(output)

    def pair_context_stats(self) -> dict:
        return {
            "enabled": self.cfg.pair_context_capacity > 0,
            "capacity": self.cfg.pair_context_capacity,
            "pair_count": len(self.pair_context_weights),
        }

    def stats(self) -> dict:
        view = self.weights[: self.node_count, : self.node_count]
        nonzero_edges = int(np.count_nonzero(view))
        total_possible = self.node_count * self.node_count
        return {
            "nodes": self.node_count,
            "nonzero_edges": nonzero_edges,
            "sparsity": round(
                1.0 - (nonzero_edges / total_possible if total_possible else 0.0), 4
            ),
            "training_steps": self.total_training_steps,
        }

    def strongest_edges(self, n: int = 20) -> List[Tuple[str, str, float]]:
        edges = []
        for i in range(self.node_count):
            for j in range(self.node_count):
                w = float(self.weights[i, j])
                if w > 0:
                    edges.append((self.id_to_symbol[i], self.id_to_symbol[j], w))
        edges.sort(key=lambda x: x[2], reverse=True)
        return edges[:n]
