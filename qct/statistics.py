"""Conservative batch reporting: unknown episodes remain in the denominator."""
from __future__ import annotations
import math
from collections import defaultdict
from .evaluation import evaluate_episode


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if type(n) is not int or type(successes) is not int or not 0 <= successes <= n or not math.isfinite(z) or z <= 0:
        raise ValueError('Invalid binomial counts/confidence parameter')
    if n == 0:
        return None
    p, z2 = successes/n, z*z
    center = (p+z2/(2*n))/(1+z2/n)
    half = z*math.sqrt(p*(1-p)/n+z2/(4*n*n))/(1+z2/n)
    return (max(0.0, center-half), min(1.0, center+half))


def summarize(episodes: list[dict], config: dict) -> list[dict]:
    groups, seen = defaultdict(list), set()
    for e in episodes:
        key = (e['data_kind'], e['observation_mode'], e['task_version'], e['method_id'])
        identity = (*key, e['episode_id'])
        if identity in seen:
            raise ValueError('Duplicate episode; refusing to double count')
        seen.add(identity)
        groups[key].append(evaluate_episode(e, config)['metrics']['strict_success'])
    result = []
    for key, values in sorted(groups.items()):
        n, good = len(values), sum(v is True for v in values)
        unknown = sum(v is None for v in values)
        result.append(dict(data_kind=key[0], observation_mode=key[1], task_version=key[2], method_id=key[3],
                           episodes=n, observed_successes=good, observed_failures=n-good-unknown, unknown=unknown,
                           success_fraction_all_attempts=good/n,
                           missingness_bounds=(good/n, (good+unknown)/n),
                           wilson95_unknown_as_failure=wilson(good,n),
                           note='No pooling across methods/tracks; Wilson assumes independent attempts, not paired layouts.'))
    return result
