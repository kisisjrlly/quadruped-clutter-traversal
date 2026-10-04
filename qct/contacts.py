"""Pure contact attribution; collider identity is preserved, force cancellation is irrelevant."""
from __future__ import annotations
from dataclasses import dataclass


def under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix.rstrip('/') + '/')


@dataclass
class ContactClassifier:
    robot_prefix: str
    object_prefixes: dict[str, str]
    ground_prefixes: tuple[str, ...]
    wall_prefixes: tuple[str, ...]
    link_aliases: dict[str, str]

    def __post_init__(self):
        prefixes = [self.robot_prefix, *self.object_prefixes, *self.ground_prefixes, *self.wall_prefixes]
        if any(not isinstance(p, str) or not p.startswith('/') for p in prefixes):
            raise ValueError('Contact paths must be absolute USD paths')
        if len(prefixes) != len(set(prefixes)):
            raise ValueError('Duplicate contact category prefixes')
        if any(not under(p, self.robot_prefix) or not v for p, v in self.link_aliases.items()):
            raise ValueError('Invalid explicit robot link aliases')

    def link(self, collider: str, actor: str) -> str:
        # An audited foot collider alias may be more specific than its calf actor.
        for prefix, name in sorted(self.link_aliases.items(), key=lambda x: -len(x[0])):
            if under(collider, prefix) or under(actor, prefix):
                return name
        return actor.rsplit('/', 1)[-1]  # never silently label an entire calf as a foot

    def classify(self, actor0: str, actor1: str, collider0: str, collider1: str) -> tuple[dict | None, bool]:
        r0, r1 = under(actor0, self.robot_prefix), under(actor1, self.robot_prefix)
        if not r0 and not r1:
            return None, True
        if not r0:
            actor0, actor1, collider0, collider1 = actor1, actor0, collider1, collider0
        event = dict(robot_link=self.link(collider0, actor0), actor0=actor0, actor1=actor1,
                     collider0=collider0, collider1=collider1)
        if r0 and r1:
            return dict(event, counterpart_type='self', counterpart_id=actor1), True
        for prefix, oid in self.object_prefixes.items():
            if under(actor1, prefix) or under(collider1, prefix):
                return dict(event, counterpart_type='obstacle', counterpart_id=oid), True
        for kind, prefixes in (('ground', self.ground_prefixes), ('wall', self.wall_prefixes)):
            if any(under(actor1, p) or under(collider1, p) for p in prefixes):
                return dict(event, counterpart_type=kind, counterpart_id=actor1), True
        return None, False  # caller must retain unknown raw event and invalidate coverage
