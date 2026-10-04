"""CPU reference depth unprojection and observed-only sparse voxel memory.

No scene manifest is accepted here. Invalid/no-return pixels are NOT free space.
This map is an algorithmic reference, not a real-time GPU mapper.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from .geometry import Vec3, rotate
from .scene import finite, vector


@dataclass(frozen=True)
class Pinhole:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    near: float = 0.05
    far: float = 5.0

    def __post_init__(self):
        if type(self.width) is not int or type(self.height) is not int or min(self.width,self.height) < 1:
            raise ValueError("Invalid image dimensions")
        for name in ("fx","fy","near","far"):
            if finite(getattr(self,name),name,minimum=0) == 0:
                raise ValueError(f"{name} must be positive")
        finite(self.cx,"cx"); finite(self.cy,"cy")
        if self.far <= self.near:
            raise ValueError("Invalid clipping range")


def unproject(depth, camera: Pinhole, position: Vec3, quaternion_wxyz, stride: int = 1) -> list[Vec3]:
    """Optical-frame +Z depth (distance_to_image_plane), +X right, +Y down.

    T_world_camera must use that optical convention. Euclidean/range depth is
    a different quantity and must be converted before calling this function.
    """
    if type(stride) is not int or stride < 1 or len(depth) != camera.height or any(len(row) != camera.width for row in depth):
        raise ValueError("Invalid depth dimensions/stride")
    position = vector(position,3,"position")
    rotate(quaternion_wxyz,(0,0,0))  # validate even if every pixel is invalid
    points = []
    for v in range(0,camera.height,stride):
        for u in range(0,camera.width,stride):
            z = depth[v][u]
            if isinstance(z,bool):
                continue
            try:
                z = float(z)
            except (TypeError,ValueError):
                continue
            if not math.isfinite(z) or not camera.near < z < camera.far:
                continue
            p = rotate(quaternion_wxyz,((u-camera.cx)*z/camera.fx,(v-camera.cy)*z/camera.fy,z))
            points.append(tuple(a+b for a,b in zip(position,p)))
    return points


@dataclass(frozen=True)
class Cell:
    occupied: bool
    timestamp_s: float


class VoxelMemory:
    """Observed free/occupied/unknown with explicit age and per-episode reset.

    Endpoints win over free rays in the same frame. No claim of a calibrated
    occupancy probability or complete visibility inside a voxel is made.
    """
    def __init__(self, resolution: float = 0.025, max_age_s: float = 2.0, max_cells: int = 200000):
        if finite(resolution,"resolution",minimum=0) == 0 or finite(max_age_s,"max_age",minimum=0) == 0:
            raise ValueError("Resolution and max_age must be positive")
        if type(max_cells) is not int or max_cells < 1:
            raise ValueError("Invalid max_cells")
        self.resolution, self.max_age_s, self.max_cells = resolution,max_age_s,max_cells
        self.cells: dict[tuple[int,int,int],Cell] = {}
        self.last_timestamp = -math.inf

    def reset(self) -> None:
        self.cells.clear()
        self.last_timestamp = -math.inf

    def key(self,p) -> tuple[int,int,int]:
        return tuple(math.floor(v/self.resolution) for v in vector(p,3,"point"))

    def integrate(self,origin: Vec3,points:list[Vec3],timestamp_s:float) -> None:
        finite(timestamp_s,"timestamp",minimum=0)
        if timestamp_s <= self.last_timestamp:
            raise ValueError("A sensor frame may be integrated once, in time order")
        origin = vector(origin,3,"origin")
        free, hits = set(), set()
        for point in points:
            point = vector(point,3,"point")
            length = math.dist(origin,point)
            if length > 100:
                raise ValueError("Ray exceeds reference mapper's 100 m safety cap")
            n = max(1,math.ceil(length/(self.resolution/2)))
            endpoint = self.key(point)
            hits.add(endpoint)
            for i in range(n):
                k = self.key(tuple(a+(b-a)*i/n for a,b in zip(origin,point)))
                if k != endpoint:
                    free.add(k)
        retained = {k:v for k,v in self.cells.items() if timestamp_s-v.timestamp_s <= self.max_age_s}
        if len(set(retained) | free | hits) > self.max_cells:
            raise MemoryError("Voxel capacity exceeded; frame not partially integrated")
        retained.update({k:Cell(False,timestamp_s) for k in free-hits})
        retained.update({k:Cell(True,timestamp_s) for k in hits})
        self.cells, self.last_timestamp = retained, timestamp_s

    def state(self,p,timestamp_s:float) -> str:
        finite(timestamp_s,"timestamp",minimum=0)
        if timestamp_s < self.last_timestamp:
            raise ValueError("Queries cannot precede the latest sensor frame")
        cell = self.cells.get(self.key(p))
        if cell is None or timestamp_s-cell.timestamp_s > self.max_age_s:
            return "unknown"
        return "occupied" if cell.occupied else "free_observed"

    def occupied_centers(self,timestamp_s:float) -> list[Vec3]:
        finite(timestamp_s,"timestamp",minimum=0)
        if timestamp_s < self.last_timestamp:
            raise ValueError("Query timestamp is in the past")
        return [tuple((i+0.5)*self.resolution for i in k) for k,v in sorted(self.cells.items())
                if v.occupied and timestamp_s-v.timestamp_s <= self.max_age_s]

    def neighborhood(self,p,radius:float,timestamp_s:float) -> dict:
        """Report coverage, not an invented positive clearance in unobserved space."""
        finite(radius,"radius",minimum=0)
        k, n = self.key(p), math.ceil(radius/self.resolution)
        states = [self.state(tuple((a+d+0.5)*self.resolution for a,d in zip(k,(i,j,l))),timestamp_s)
                  for i in range(-n,n+1) for j in range(-n,n+1) for l in range(-n,n+1)]
        return {"occupied":states.count("occupied"),"free_observed":states.count("free_observed"),
                "unknown":states.count("unknown"),"scope":"voxel_coverage_not_continuous_clearance"}
