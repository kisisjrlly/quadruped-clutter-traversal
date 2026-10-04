"""Execute pinned upstream flat-ground training, not a clutter-trained QCT method.

Requires a reviewed local M1 gate report. No training is started on import.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isaaclab', required=True, help='Local IsaacLab source checkout')
    parser.add_argument('--gate', required=True, help='M1 reviewed gate JSON; not a CPU test report')
    parser.add_argument('--num-envs', type=int, default=64)
    parser.add_argument('--iterations', type=int, default=1500)
    parser.add_argument('--seed', type=int, default=0)
    args = parser.parse_args()
    gate = json.loads(Path(args.gate).read_text())
    required = ('asset_audited','physics_smoke_passed','foot_contact_passed','calf_contact_passed',
                'base_contact_passed','thin_rod_temporal_test_passed','object_rest_drift_passed')
    if gate.get('schema_version') != 'qct.m1-gate.v1' or any(gate.get(k) is not True for k in required):
        parser.error('M1 gate is incomplete; do not start training')
    if not gate.get('reviewer') or not gate.get('evidence_directory'):
        parser.error('M1 needs a reviewer and trace evidence; booleans alone are not evidence')
    evidence = Path(gate['evidence_directory'])
    if not evidence.is_dir() or not any(evidence.rglob('trace.jsonl')):
        parser.error('M1 evidence directory must contain raw traces')
    if args.num_envs < 1 or args.iterations < 1:
        parser.error('Training sizes must be positive')
    root = Path(args.isaaclab).resolve()
    version = subprocess.check_output(['git','describe','--tags','--exact-match'], cwd=root, text=True).strip()
    dirty = subprocess.check_output(['git','status','--porcelain'], cwd=root, text=True).strip()
    if version != 'v2.3.0' or dirty:
        parser.error('Reference launcher requires a clean IsaacLab v2.3.0 checkout')
    script = root/'scripts/reinforcement_learning/rsl_rl/train.py'
    if not script.is_file():
        parser.error('Upstream RSL-RL train.py is absent')
    argv = [sys.executable, str(script), '--task', 'Isaac-Velocity-Flat-Unitree-Go2-v0',
            '--headless', '--num_envs', str(args.num_envs), '--max_iterations', str(args.iterations), '--seed', str(args.seed)]
    print('Starting ONLY the upstream velocity baseline. This is not a QCT clutter policy.', flush=True)
    os.chdir(root)
    os.execv(sys.executable, argv)


if __name__ == '__main__':
    main()
