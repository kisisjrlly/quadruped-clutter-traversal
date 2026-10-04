"""Analytic primitive distances and conservative static capsule checks.

These primitives do not replace the collision meshes of a robot USD asset.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Callable
from .scene import Obstacle, Scene, finite, vector

Vec3 = tuple[float, float, float]


def quat_normalize(q) -> tuple[float, float, float, float]:
    q = vector(q, 4, "quaternion_wxyz")
    n = math.hypot(*q)
    if not math.isfinite(n) or n < 1e-12:
        raise ValueError("Zero quaternion")
    return tuple(v/n for v in q)


def rotate(q, p) -> Vec3:
    w, x, y, z = quat_normalize(q)
    a, b, c = vector(p, 3, "point")
    return ((1-2*y*y-2*z*z)*a + (2*x*y-2*w*z)*b + (2*x*z+2*w*y)*c,
            (2*x*y+2*w*z)*a + (1-2*x*x-2*z*z)*b + (2*y*z-2*w*x)*c,
            (2*x*z-2*w*y)*a + (2*y*z+2*w*x)*b + (1-2*x*x-2*y*y)*c)


def quat_angle_deg(a, b) -> float:
    # q and -q represent the same rotation.
    dot = abs(sum(x*y for x, y in zip(quat_normalize(a), quat_normalize(b))))
    return math.degrees(2 * math.acos(min(1.0, dot)))


def point_distance(p: Vec3, obstacle: Obstacle) -> float:
    px, py, pz = vector(p, 3, "point")
    dx, dy, dz = px-obstacle.position[0], py-obstacle.position[1], pz-obstacle.position[2]
    c, s = math.cos(obstacle.yaw), math.sin(obstacle.yaw)
    x, y, z = c*dx+s*dy, -s*dx+c*dy, dz
    sx, sy, sz = obstacle.size
    if obstacle.shape == "cylinder":
        a, b = math.hypot(x, y)-sx/2, abs(z)-sz/2
        return math.hypot(max(a, 0), max(b, 0)) + min(max(a, b), 0)
    d = (abs(x)-sx/2, abs(y)-sy/2, abs(z)-sz/2)
    return math.sqrt(sum(max(v, 0)**2 for v in d)) + min(max(d), 0)


def scene_distance(scene: Scene, p: Vec3) -> float:
    """Protected objects + corridor sides/ends; floor excluded for legal support."""
    x, y, _ = vector(p, 3, "point")
    return min(x, scene.length_m-x, scene.width_m/2-abs(y),
               *(point_distance(p, o) for o in scene.obstacles))


@dataclass(frozen=True)
class Capsule:
    link: str
    a: Vec3
    b: Vec3
    radius: float

    def __post_init__(self):
        if not self.link:
            raise ValueError("Missing link identity")
        object.__setattr__(self, "a", vector(self.a, 3, "capsule a"))
        object.__setattr__(self, "b", vector(self.b, 3, "capsule b"))
        finite(self.radius, "radius", minimum=0)


def capsule_clearance(capsule: Capsule, query: Callable[[Vec3], float | None], resolution: float = 0.01) -> float | None:
    """Lower bound for one static capsule against a 1-Lipschitz distance field.

    The segment is sampled at spacing <= resolution. Subtract half the actual
    spacing so even a thin obstacle between samples cannot be certified clear.
    A negative bound can be conservative; it is not necessarily a collision.
    Unknown field samples fail closed. No guarantee for a non-SDF query.
    """
    if finite(resolution, "resolution", minimum=0) == 0:
        raise ValueError("resolution must be positive")
    length = math.dist(capsule.a, capsule.b)
    n = max(1, math.ceil(length / resolution))
    values = []
    for i in range(n+1):
        p = tuple(a+(b-a)*i/n for a, b in zip(capsule.a, capsule.b))
        d = query(p)
        if d is None:
            return None
        values.append(finite(d, "distance"))
    return min(values) - capsule.radius - length/(2*n)


def support_margin(com_xy, feet_xy) -> float:
    """Signed distance to a convex support polygon; quasistatic, level-ground only."""
    points = sorted(set(tuple(vector(p, 2, "foot")) for p in feet_xy))
    if len(points) < 3:
        return -math.inf
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1]+upper[:-1]
    if len(hull) < 3:
        return -math.inf
    p = vector(com_xy, 2, "COM")
    return min(cross(a, b, p)/math.dist(a, b) for a, b in zip(hull, hull[1:]+hull[:1]))


def swept_capsule_clearance(start: Capsule, end: Capsule, query, *, steps: int = 20, resolution: float = .01):
    """Conservative bound for LINEAR endpoint interpolation in a static 1-Lipschitz field.

    This does not certify a joint-interpolated articulated trajectory. A robot
    kinematic adapter must bound nonlinear link deviation before using this bound.
    """
    if start.link != end.link or start.radius != end.radius or type(steps) is not int or steps < 1:
        raise ValueError('Swept primitive must preserve link/radius and use positive steps')
    motion = max(math.dist(start.a, end.a), math.dist(start.b, end.b))/steps
    values = []
    for i in range(steps+1):
        alpha = i/steps
        c = Capsule(start.link, tuple(x+(y-x)*alpha for x,y in zip(start.a,end.a)),
                    tuple(x+(y-x)*alpha for x,y in zip(start.b,end.b)), start.radius)
        bound = capsule_clearance(c, query, resolution)
        if bound is None:
            return None
        values.append(bound)
    return min(values)-motion/2
