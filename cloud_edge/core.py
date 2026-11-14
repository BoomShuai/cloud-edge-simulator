from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import mean
import math
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Task:
    """A cloud-edge-device workload unit."""

    name: str
    workload_gops: float
    input_mb: float
    output_mb: float
    deadline_ms: float
    privacy_level: int

    def __post_init__(self):
        _name(self.name)
        for value in [self.workload_gops, self.input_mb, self.output_mb, self.deadline_ms]: _number(value)
        if type(self.privacy_level) is not int or not 1 <= self.privacy_level <= 5:
            raise ValueError('privacy_level must be 1..5')


@dataclass(frozen=True)
class Node:
    name: str
    tier: str
    compute_tops: float
    idle_queue_ms: float
    energy_per_gop_j: float

    def __post_init__(self):
        _name(self.name)
        if self.tier not in {'device','edge','cloud'}: raise ValueError('Unknown tier')
        _number(self.compute_tops, positive=True)
        _number(self.idle_queue_ms);_number(self.energy_per_gop_j)


@dataclass(frozen=True)
class Link:
    source_tier: str
    target_tier: str
    latency_ms: float
    bandwidth_mbps: float

    def __post_init__(self):
        if self.source_tier not in {'device','edge','cloud'} or self.target_tier not in {'device','edge','cloud'}:
            raise ValueError('Unknown link tier')
        _number(self.latency_ms);_number(self.bandwidth_mbps, positive=True)


@dataclass(frozen=True)
class Decision:
    task: Task
    node: Node
    latency_ms: float
    energy_j: float
    deadline_met: bool
    reason: str


def default_nodes() -> List[Node]:
    return [
        Node("synthetic-device", "device", compute_tops=5, idle_queue_ms=2.0, energy_per_gop_j=0.055),
        Node("synthetic-edge", "edge", compute_tops=45, idle_queue_ms=8.0, energy_per_gop_j=0.034),
        Node("synthetic-cloud", "cloud", compute_tops=320, idle_queue_ms=22.0, energy_per_gop_j=0.026),
    ]


def default_links() -> List[Link]:
    return [
        Link("device", "device", latency_ms=0.0, bandwidth_mbps=10_000),
        Link("device", "edge", latency_ms=7.0, bandwidth_mbps=260),
        Link("edge", "device", latency_ms=7.0, bandwidth_mbps=260),
        Link("device", "cloud", latency_ms=32.0, bandwidth_mbps=160),
        Link("cloud", "device", latency_ms=32.0, bandwidth_mbps=160),
    ]


def research_workload(seed_variant: int = 0) -> List[Task]:
    """A small deterministic synthetic workload for strategy comparison."""

    base = [
        Task("uav-low-altitude-detection", 180, 6.5, 0.4, 55, 4),
        Task("swarm-coordination-planning", 95, 2.0, 0.2, 40, 3),
        Task("moe-edge-inference-token-batch", 8200, 1.1, 0.4, 190, 2),
        Task("federated-client-update", 15000, 2.5, 18.0, 1000, 5),
        Task("medical-image-segmentation", 2600, 22.0, 3.2, 720, 5),
        Task("blockchain-fl-aggregation", 160, 4.5, 2.0, 160, 3),
        Task("serverless-llm-warmup", 30000, 3.0, 1.0, 400, 1),
        Task("traffic-forecast-gnn-window", 1600, 5.0, 1.0, 250, 2),
    ]
    if seed_variant == 0:
        return base

    factor = 1.0 + (seed_variant % 5) * 0.08
    return [
        replace(
            task,
            workload_gops=task.workload_gops * factor,
            input_mb=task.input_mb * (1.0 + (seed_variant % 3) * 0.04),
        )
        for task in base
    ]


class CollaborativeSimulator:
    def __init__(self, nodes: Sequence[Node], links: Sequence[Link]):
        self.nodes = list(nodes)
        self.links = {(link.source_tier, link.target_tier): link for link in links}
        if not self.nodes or len(self.links) != len(links): raise ValueError('Empty nodes or duplicate links')
        if len({node.tier for node in self.nodes}) != len(self.nodes): raise ValueError('One node per tier is supported')
        if len({node.name for node in self.nodes}) != len(self.nodes): raise ValueError('Duplicate node names')
        for node in self.nodes:
            if ('device',node.tier) not in self.links or (node.tier,'device') not in self.links:
                raise ValueError('Missing round-trip link')

    def estimate(self, task: Task, node: Node) -> Tuple[float, float]:
        if node not in self.nodes: raise ValueError('Unknown node')
        link_up = self.links[("device", node.tier)]
        link_down = self.links[(node.tier, "device")]
        upload_ms = self._transfer_ms(task.input_mb, link_up.bandwidth_mbps) + link_up.latency_ms
        download_ms = self._transfer_ms(task.output_mb, link_down.bandwidth_mbps) + link_down.latency_ms
        compute_ms = task.workload_gops / node.compute_tops
        latency_ms = node.idle_queue_ms + upload_ms + compute_ms + download_ms
        energy_j = task.workload_gops * node.energy_per_gop_j
        return latency_ms, energy_j

    def run(
        self,
        tasks: Iterable[Task],
        strategy: Callable[["CollaborativeSimulator", Task], Decision],
    ) -> List[Decision]:
        return [strategy(self, task) for task in tasks]

    @staticmethod
    def _transfer_ms(size_mb: float, bandwidth_mbps: float) -> float:
        return size_mb * 8 * 1000 / bandwidth_mbps


def device_only(sim: CollaborativeSimulator, task: Task) -> Decision:
    node = _node_by_tier(sim.nodes, "device")
    latency_ms, energy_j = sim.estimate(task, node)
    return Decision(task, node, latency_ms, energy_j, latency_ms <= task.deadline_ms, "local-only baseline")


def cloud_only(sim: CollaborativeSimulator, task: Task) -> Decision:
    node = _node_by_tier(sim.nodes, "cloud")
    latency_ms, energy_j = sim.estimate(task, node)
    return Decision(task, node, latency_ms, energy_j, latency_ms <= task.deadline_ms, "cloud-only baseline")


def latency_greedy(sim: CollaborativeSimulator, task: Task) -> Decision:
    node, latency_ms, energy_j = min(_estimates(sim, task), key=lambda item: item[1])
    return Decision(task, node, latency_ms, energy_j, latency_ms <= task.deadline_ms, "minimum predicted latency")


def privacy_aware(sim: CollaborativeSimulator, task: Task) -> Decision:
    candidates = sim.nodes
    if task.privacy_level >= 5:
        candidates = [node for node in sim.nodes if node.tier != "cloud"]
    elif task.privacy_level >= 4:
        candidates = [node for node in sim.nodes if node.tier in {"device", "edge"}]

    if not candidates: raise ValueError('No node satisfies the privacy constraint')
    estimates = [(node, *sim.estimate(task, node)) for node in candidates]
    feasible = [item for item in estimates if item[1] <= task.deadline_ms]
    pool = feasible or estimates
    node, latency_ms, energy_j = min(pool, key=lambda item: item[1] + 18 * item[2])
    reason = "privacy constrained, then latency-energy score"
    return Decision(task, node, latency_ms, energy_j, latency_ms <= task.deadline_ms, reason)


def summarize(decisions: Sequence[Decision]) -> Dict[str, object]:
    if not decisions:
        raise ValueError("decisions must not be empty")

    placements: Dict[str, int] = {}
    for decision in decisions:
        placements[decision.node.tier] = placements.get(decision.node.tier, 0) + 1

    return {
        "tasks": len(decisions),
        "avg_latency_ms": round(mean(item.latency_ms for item in decisions), 2),
        "p95_latency_ms": round(_percentile([item.latency_ms for item in decisions], 0.95), 2),
        "deadline_hit_rate": round(sum(item.deadline_met for item in decisions) / len(decisions), 3),
        "total_energy_j": round(sum(item.energy_j for item in decisions), 2),
        "placements": placements,
    }


def strategy_catalog() -> Dict[str, Callable[[CollaborativeSimulator, Task], Decision]]:
    return {
        "device_only": device_only,
        "cloud_only": cloud_only,
        "latency_greedy": latency_greedy,
        "privacy_aware": privacy_aware,
    }


def _estimates(sim: CollaborativeSimulator, task: Task) -> Iterable[Tuple[Node, float, float]]:
    for node in sim.nodes:
        latency_ms, energy_j = sim.estimate(task, node)
        yield node, latency_ms, energy_j


def _node_by_tier(nodes: Sequence[Node], tier: str) -> Node:
    for node in nodes:
        if node.tier == tier:
            return node
    raise ValueError(f"missing node tier: {tier}")


def _percentile(values: Sequence[float], ratio: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * ratio)))
    return ordered[index]


def _name(value):
    if not isinstance(value,str) or not value.strip() or len(value)>128:
        raise ValueError('Invalid name')


def _number(value, positive=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (value<=0 if positive else value<0):
        raise ValueError('Expected a finite positive/nonnegative number')
