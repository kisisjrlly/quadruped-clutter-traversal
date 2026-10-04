"""Launch Isaac Lab/Sim; no fallback physics backend and no real robot code."""
from pathlib import Path
import argparse
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', required=True)
    parser.add_argument('--benchmark', default=str(ROOT/'configs/benchmark_v0_1.json'))
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=('stand','policy-route'), default='stand')
    parser.add_argument('--duration', type=float, default=5.0)
    parser.add_argument('--dt', type=float, default=.005)
    parser.add_argument('--body-radius', type=float, default=.28)
    parser.add_argument('--link-map', help='Audited USD collider paths -> canonical foot identities')
    parser.add_argument('--policy')
    parser.add_argument('--policy-spec')
    try:
        from isaaclab.app import AppLauncher
    except ImportError as exc:
        raise SystemExit('Isaac Lab is required. Run with the pinned Isaac Lab isaaclab.sh -p launcher; no simulation was executed.') from exc
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    launcher = AppLauncher(args)
    try:
        from qct.sim.runtime import run
        print(run(args, launcher.app))
    finally:
        launcher.app.close()


if __name__ == '__main__':
    main()
