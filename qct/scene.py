"""Versioned scene manifests. A generated layout is NOT a feasibility witness."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import random
import re
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def finite(value: Any, name: str, *, minimum: float | None = None) -> float:
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return float(value)


def vector(values: Any, n: int, name: str) -> tuple[float, ...]:
    if not isinstance(values, (tuple, list)) or len(values) != n:
        raise ValueError(f"{name} must contain {n} numbers")
    return tuple(finite(x, name) for x in values)


@dataclass(frozen=True)
class Obstacle:
    object_id: str
    shape: str
    position: tuple[float, float, float]
    size: tuple[float, float, float]  # full xyz dimensions; cylinders use diameter, diameter, height
    yaw: float = 0.0
    mass_kg: float = 0.1
    friction: float = 0.6
    role: str = "protected"

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", self.object_id):
            raise ValueError("object_id must be a USD-safe identifier")
        if self.shape not in ("box", "cylinder") or self.role != "protected":
            raise ValueError("Unsupported shape or object role")
        object.__setattr__(self, "position", vector(self.position, 3, "position"))
        object.__setattr__(self, "size", vector(self.size, 3, "size"))
        if min(self.size) <= 0 or self.position[2] < self.size[2] / 2 - 1e-8:
            raise ValueError("Nonpositive dimension or initial floor penetration")
        if self.shape == "cylinder" and abs(self.size[0] - self.size[1]) > 1e-10:
            raise ValueError("A cylinder must have equal x/y diameters")
        finite(self.yaw, "yaw")
        if finite(self.mass_kg, "mass", minimum=0) == 0:
            raise ValueError("Protected objects must be dynamic with positive mass")
        finite(self.friction, "friction", minimum=0)

    @property
    def footprint_radius(self) -> float:
        return self.size[0] / 2 if self.shape == "cylinder" else math.hypot(*self.size[:2]) / 2


@dataclass(frozen=True)
class Scene:
    seed: int
    split: str
    length_m: float
    width_m: float
    start: tuple[float, float, float]
    goal: tuple[float, float, float]
    obstacles: tuple[Obstacle, ...]
    schema_version: str = "qct.scene.v1"
    feasibility: str = "unknown"

    def __post_init__(self):
        if self.schema_version != "qct.scene.v1" or self.feasibility != "unknown":
            raise ValueError("This generator cannot certify a feasible or infeasible scene")
        if type(self.seed) is not int or self.seed < 0 or self.split not in ("train", "validation", "test", "ood", "calibration"):
            raise ValueError("Invalid seed or split")
        finite(self.length_m, "length", minimum=2)
        finite(self.width_m, "width", minimum=0.4)
        object.__setattr__(self, "start", vector(self.start, 3, "start"))
        object.__setattr__(self, "goal", vector(self.goal, 3, "goal"))
        object.__setattr__(self, "obstacles", tuple(self.obstacles))
        for p in (self.start, self.goal):
            if not (0 < p[0] < self.length_m and abs(p[1]) < self.width_m / 2 and p[2] > 0):
                raise ValueError("Start/goal outside corridor")
        ids = [o.object_id for o in self.obstacles]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate object IDs")
        for i, o in enumerate(self.obstacles):
            r = o.footprint_radius
            if o.position[0] - r < 0 or o.position[0] + r > self.length_m or abs(o.position[1]) + r > self.width_m / 2:
                raise ValueError("Obstacle outside corridor")
            for other in self.obstacles[:i]:
                if math.dist(o.position[:2], other.position[:2]) < r + other.footprint_radius:
                    raise ValueError("Overlapping initial obstacle footprints")

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def sha256(self) -> str:
        return digest(self.to_dict())

    @classmethod
    def from_dict(cls, value: dict) -> "Scene":
        data = dict(value)
        data["obstacles"] = tuple(Obstacle(**x) for x in data["obstacles"])
        return cls(**data)

    @classmethod
    def load(cls, path: str | Path) -> "Scene":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as stream:
            json.dump(self.to_dict(), stream, indent=2, allow_nan=False)
            stream.write("\n")


def generate_scene(seed: int, split: str = "train", count: int = 16,
                   length_m: float = 6.0, width_m: float = 1.8) -> Scene:
    """Rejection-sample mixed dynamic primitives; fail rather than silently dropping objects."""
    if type(seed) is not int or seed < 0 or type(count) is not int or not 0 <= count <= 128:
        raise ValueError("Invalid seed/count")
    # Validate before constructing ranges. Split is part of the PRNG seed.
    empty = Scene(seed, split, length_m, width_m, (0.6, 0, 0.4), (length_m - 0.6, 0, 0.4), ())
    if length_m < 3 or width_m < 0.6:
        raise ValueError("Generator needs length >= 3 m and width >= 0.6 m")
    rng = random.Random(int(digest(["qct.generator.v1", split, seed])[:16], 16))
    objects: list[Obstacle] = []
    for i in range(count):
        shape = "cylinder" if i % 4 in (0, 1) else "box"
        if i % 4 == 0:  # thin vertical rod
            d, h = rng.uniform(0.018, 0.035), rng.uniform(0.35, 0.65)
            size, mass = (d, d, h), 0.04
        elif i % 4 == 1:  # bottle proxy, not a bottle mesh
            d, h = rng.uniform(0.05, 0.09), rng.uniform(0.12, 0.3)
            size, mass = (d, d, h), 0.15
        elif i % 4 == 2:
            size, mass = (rng.uniform(0.03, 0.05), rng.uniform(0.03, 0.06), rng.uniform(0.22, 0.48)), 0.10
        else:
            size, mass = (rng.uniform(0.08, 0.15), rng.uniform(0.04, 0.09), rng.uniform(0.025, 0.065)), 0.12
        for _ in range(5000):
            o = Obstacle(f"object_{i:03d}", shape,
                         (rng.uniform(1.3, length_m - 1.3), rng.uniform(-width_m / 2 + 0.16, width_m / 2 - 0.16), size[2] / 2 + 0.001),
                         size, rng.uniform(-math.pi, math.pi), mass)
            if all(math.dist(o.position[:2], q.position[:2]) > o.footprint_radius + q.footprint_radius + 0.025 for q in objects):
                objects.append(o)
                break
        else:
            raise ValueError(f"Packing failed at {i}/{count}; configuration is not silently relaxed")
    return Scene(seed, split, length_m, width_m, empty.start, empty.goal, tuple(objects))
