"""Usage: python -m qct evaluate EPISODE.json [--config CONFIG.json]."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .evaluation import EvaluationError, evaluate_episode


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise EvaluationError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='QCT summary evaluator (not a robot simulator)')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('evaluate', help='Evaluate one episode summary')
    p.add_argument('episode', type=Path)
    p.add_argument('--config', type=Path, default=Path(__file__).resolve().parents[1]/'configs/benchmark_v0_1.json')
    args = parser.parse_args(argv)
    try:
        episode = json.loads(args.episode.read_text(encoding='utf-8'), object_pairs_hook=_reject_duplicate_keys)
        config = json.loads(args.config.read_text(encoding='utf-8'), object_pairs_hook=_reject_duplicate_keys)
        result = evaluate_episode(episode, config)
    except (OSError, UnicodeError, json.JSONDecodeError, EvaluationError) as exc:
        print(f'Invalid input: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    # Exit 0 means a valid evaluation, not a successful robot episode.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
