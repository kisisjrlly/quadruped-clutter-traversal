"""Weak oracle route follower and strict, explicit 48-observation policy contract."""
from __future__ import annotations
import math
from .scene import finite, vector


class RouteFollower:
    def __init__(self, points, speed=0.15, yaw_gain=1.5, tolerance=0.12):
        if not points:
            raise ValueError('An empty route cannot be followed')
        self.points = [vector(p, 3, 'waypoint') for p in points]
        self.speed = finite(speed, 'speed', minimum=0)
        self.yaw_gain = finite(yaw_gain, 'yaw_gain', minimum=0)
        self.tolerance = finite(tolerance, 'tolerance', minimum=0)
        self.index = 0

    def command(self, position, yaw):
        position = vector(position, 3, 'position'); finite(yaw, 'yaw')
        while self.index < len(self.points)-1 and math.dist(position[:2], self.points[self.index][:2]) < self.tolerance:
            self.index += 1
        target = self.points[self.index]
        if self.index == len(self.points)-1 and math.dist(position[:2], target[:2]) < self.tolerance:
            return (0.0, 0.0, 0.0)
        angle = math.atan2(target[1]-position[1], target[0]-position[0]) - yaw
        angle = math.atan2(math.sin(angle), math.cos(angle))
        return (self.speed * max(0.0, math.cos(angle)), 0.0, max(-0.4, min(0.4, self.yaw_gain*angle)))


class PolicyContract:
    """No automatic compatibility guesses for exported third-party controllers."""
    def __init__(self, data: dict, joint_names):
        if data.get('schema_version') != 'qct.policy.v1' or data.get('observation_layout') != 'lin3_ang3_gravity3_command3_q12_dq12_previous12':
            raise ValueError('Unsupported policy observation contract')
        self.names = list(data['joint_names'])
        if len(self.names) != 12 or len(set(self.names)) != 12 or set(self.names) != set(joint_names):
            raise ValueError('Policy joints must match the 12 simulated joints exactly')
        self.indices = [list(joint_names).index(n) for n in self.names]
        self.obs_scale = vector(data['observation_scale'], 48, 'observation_scale')
        self.action_scale = vector(data['action_scale'], 12, 'action_scale')
        self.default_q = vector(data['default_joint_positions'], 12, 'default_joint_positions')
        self.action_clip = finite(data['action_clip'], 'action_clip', minimum=0)
        if self.action_clip == 0:
            raise ValueError('Action clipping must match training and be positive')
        self.period_s = finite(data['control_period_s'], 'control_period_s', minimum=0)
        if not 0 < self.period_s <= 0.1 or data.get('exported_normalizer_included') is not True:
            raise ValueError('Control period and exported observation normalizer must be verified')
        # Spec must bind to actual bytes. The runner verifies this before loading.
        sha = data.get('policy_sha256', '')
        if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('Policy file hash required')
