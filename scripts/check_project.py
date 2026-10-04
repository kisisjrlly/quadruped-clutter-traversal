"""Check local documentation links, JSON fixtures and claim/reference IDs."""
from pathlib import Path
import csv
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qct.evaluation import evaluate_episode


def main() -> int:
    errors = []
    for path in sorted(ROOT.rglob('*.md')):
        if '.git' in path.parts:
            continue
        text = path.read_text(encoding='utf-8')
        if '\ufffd' in text:
            errors.append(f'Invalid replacement character: {path.relative_to(ROOT)}')
        if 'cite' in text or 'turn741' in text:
            errors.append(f'Conversation-only citation marker: {path.relative_to(ROOT)}')
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
            if link.startswith(('https://','http://','mailto:','#')):
                continue
            target = (path.parent / link.split('#',1)[0]).resolve()
            if not target.is_relative_to(ROOT) or not target.exists():
                errors.append(f'Broken/outside local link: {path.relative_to(ROOT)} -> {link}')
    try:
        for path in ROOT.rglob('*.json'):
            json.loads(path.read_text(encoding='utf-8'))
        config=json.loads((ROOT/'configs/benchmark_v0_1.json').read_text())
        a=evaluate_episode(json.loads((ROOT/'examples/synthetic_episode_success.json').read_text()),config)
        b=evaluate_episode(json.loads((ROOT/'examples/synthetic_episode_contact.json').read_text()),config)
        assert a['metrics']['strict_success'] is True and a['is_fixture']
        assert b['metrics']['strict_success'] is False and b['metrics']['non_disturbing_success'] is True
        sources=json.loads((ROOT/'references/verified_sources.json').read_text())
        assert len({s['id'] for s in sources}) == len(sources)
        assert all(s['review_depth'] and s['url'].startswith('https://') and not s['code_reproduced'] for s in sources)
        with (ROOT/'paper/claims.csv').open(encoding='utf-8',newline='') as f:
            claims=list(csv.DictReader(f))
        assert len({row['claim_id'] for row in claims})==len(claims)
    except (OSError,ValueError,KeyError,AssertionError) as exc:
        errors.append(f'Data consistency check failed: {exc}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print('PASS: local links, JSON, synthetic fixture semantics, references and claim IDs.')
    print('No remote links, robot physics, sensors or real evidence have been validated.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
