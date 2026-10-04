"""Diagnostic baselines: conservative body route and explicit foot-swing search.

A route is not a locomotion controller. A clear foot sweep is not a clear leg.
"""
from __future__ import annotations
from dataclasses import dataclass
import heapq
import math
from typing import Callable
from .geometry import Capsule, Vec3, capsule_clearance
from .scene import Scene, finite, vector


@dataclass(frozen=True)
class Plan:
    status: str
    points: tuple[Vec3, ...]
    scope: str
    expanded: int = 0


def plan_body_route(scene: Scene, radius: float = 0.28, resolution: float = 0.05, max_expansions: int = 100000) -> Plan:
    """A* on a circular footprint. Uses scene truth: ORACLE ONLY.

    All object footprints are conservatively circumscribed; low objects cannot
    be stepped over by this baseline. Edges are checked, not just grid nodes.
    Failure means planner failure, not proof that the four-legged task is infeasible.
    """
    if finite(radius, "radius", minimum=0) <= 0 or finite(resolution, "resolution", minimum=0) <= 0:
        raise ValueError("radius/resolution must be positive")
    if type(max_expansions) is not int or max_expansions < 1:
        raise ValueError("max_expansions must be positive")
    def clearance(p):
        x, y, _ = p
        return min(x, scene.length_m-x, scene.width_m/2-abs(y),
                   *(math.dist((x, y), o.position[:2])-o.footprint_radius for o in scene.obstacles))
    def index(p):
        return round(p[0]/resolution), round(p[1]/resolution)
    def position(k):
        return (k[0]*resolution, k[1]*resolution, scene.start[2])
    def safe_edge(a, b):
        return capsule_clearance(Capsule("footprint", a, b, radius), clearance, resolution/2) > 0
    start, goal = index(scene.start), index(scene.goal)
    scope = "oracle_circular_body_route_not_whole_body"
    if not safe_edge(scene.start, position(start)) or not safe_edge(position(goal), scene.goal):
        return Plan("blocked_endpoint", (), scope)
    opened = [(math.dist(position(start), position(goal)), 0.0, start)]
    costs, parents, expanded = {start: 0.0}, {}, 0
    while opened and expanded < max_expansions:
        _, cost, node = heapq.heappop(opened)
        if cost != costs[node]:
            continue
        expanded += 1
        if node == goal:
            path = [position(node)]
            while node in parents:
                node = parents[node]
                path.append(position(node))
            path.reverse()
            # Include exact endpoints instead of snapping the actual robot pose.
            return Plan("found", (scene.start, *path, scene.goal), scope, expanded)
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nxt = (node[0]+dx, node[1]+dy)
            candidate = cost+resolution*math.hypot(dx,dy)
            if candidate >= costs.get(nxt, math.inf) or not safe_edge(position(node), position(nxt)):
                continue
            costs[nxt], parents[nxt] = candidate, node
            heapq.heappush(opened, (candidate+math.dist(position(nxt), position(goal)), candidate, nxt))
    return Plan("budget_exhausted" if opened else "no_route_found", (), scope, expanded)


def plan_foot_swing(start: Vec3, goal: Vec3, query: Callable[[Vec3], float | None],
                    radius: float = 0.025, margin: float = 0.01,
                    lifts=(0.06, 0.12, 0.20, 0.30), side_offsets=(0.0, -0.08, 0.08), samples: int = 40) -> Plan:
    """Choose a piecewise-linear foot sweep with endpoint + edge clearance checks.

    The field must be a lower-bounding 1-Lipschitz SDF; unknowns reject a path.
    Smoothing the returned path invalidates its checks and requires rechecking.
    """
    start, goal = vector(start, 3, "start"), vector(goal, 3, "goal")
    finite(radius, "radius", minimum=0)
    finite(margin, "margin", minimum=0)
    if type(samples) is not int or samples < 2:
        raise ValueError("samples must be >= 2")
    dx, dy = goal[0]-start[0], goal[1]-start[1]
    length = math.hypot(dx,dy)
    normal = (-dy/length, dx/length) if length > 1e-9 else (0.0,1.0)
    checked, best = 0, None
    for lift in lifts:
        finite(lift, "lift", minimum=0)
        for side in side_offsets:
            finite(side, "side")
            points = []
            for i in range(samples+1):
                t, arc = i/samples, math.sin(math.pi*i/samples)
                points.append((start[0]+t*dx+normal[0]*side*arc,
                               start[1]+t*dy+normal[1]*side*arc,
                               start[2]+t*(goal[2]-start[2])+lift*arc))
            checked += 1
            good = True
            for a, b in zip(points, points[1:]):
                bound = capsule_clearance(Capsule("foot", a, b, radius+margin), query)
                if bound is None or bound <= 0:
                    good = False
                    break
            if good:
                cost = sum(math.dist(a,b) for a,b in zip(points, points[1:]))
                if best is None or cost < best[0]:
                    best = (cost, tuple(points))
    return Plan("found" if best else "no_swing_found", best[1] if best else (), "foot_only_static_geometry_not_leg_or_dynamics", checked)


def choose_foothold(nominal: Vec3, query: Callable[[Vec3], float | None], radius: float = 0.025,
                    search_radius: float = 0.12, spacing: float = 0.02,
                    reachable: Callable[[Vec3], bool] | None = None) -> Vec3 | None:
    nominal = vector(nominal, 3, "nominal")
    finite(radius, "radius", minimum=0)
    finite(search_radius, "search_radius", minimum=0)
    if finite(spacing, "spacing", minimum=0) == 0:
        raise ValueError("spacing must be positive")
    n, choices = math.ceil(search_radius/spacing), []
    for i in range(-n,n+1):
        for j in range(-n,n+1):
            if math.hypot(i,j)*spacing > search_radius+1e-12:
                continue
            p = (nominal[0]+i*spacing, nominal[1]+j*spacing, nominal[2])
            distance = query(p)
            if distance is not None and finite(distance,"distance") > radius and (reachable is None or reachable(p)):
                choices.append((math.dist(nominal,p), p))
    return min(choices)[1] if choices else None
