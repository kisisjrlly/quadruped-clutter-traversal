"""CPU project commands; Isaac and torch are not imported by this module."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import platform
from .scene import generate_scene, Scene
from .planning import plan_body_route
from .recording import audit_trace
from .statistics import summarize


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    gen = sub.add_parser('scene')
    gen.add_argument('--seed', type=int, default=0)
    gen.add_argument('--split', choices=('train','validation','test','ood','calibration'), default='train')
    gen.add_argument('--count', type=int, default=16)
    gen.add_argument('--output', required=True)
    plan = sub.add_parser('plan')
    plan.add_argument('scene'); plan.add_argument('--radius', type=float, default=.28)
    audit = sub.add_parser('audit')
    audit.add_argument('trace'); audit.add_argument('summary')
    batch = sub.add_parser('summarize')
    batch.add_argument('--config', default='configs/benchmark_v0_1.json')
    batch.add_argument('episodes', nargs='+')
    sub.add_parser('doctor')
    args = parser.parse_args(argv)
    try:
        if args.command == 'scene':
            scene = generate_scene(args.seed, args.split, args.count)
            scene.save(args.output)
            result = dict(path=args.output, scene_sha256=scene.sha256, feasibility='unknown')
        elif args.command == 'plan':
            result = asdict(plan_body_route(Scene.load(args.scene), radius=args.radius))
        elif args.command == 'audit':
            result = audit_trace(args.trace, json.loads(Path(args.summary).read_text()))
        elif args.command == 'summarize':
            result = summarize([json.loads(Path(p).read_text()) for p in args.episodes], json.loads(Path(args.config).read_text()))
        else:
            result = dict(python=platform.python_version(), platform=platform.platform(),
                          packages={p:importlib.util.find_spec(p) is not None for p in ('isaaclab','isaacsim','torch','numpy')},
                          isaac_runtime_executed=False, note='Package presence is not runtime compatibility or GPU validation.')
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0 if args.command != 'audit' or result['structural_audit_passed'] else 1
    except (OSError,ValueError,KeyError,TypeError) as exc:
        parser.exit(2, str(exc)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
