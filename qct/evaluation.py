"""Pure summary evaluator, NOT a sensor monitor, simulator, or safety proof.

Incomplete evidence is represented by None. Input completeness flags are
assertions made by a future recorder; this module cannot audit raw evidence.
"""
from __future__ import annotations

import math
import re
from typing import Any


class EvaluationError(ValueError):
    """Malformed, incompatible or internally contradictory episode data."""


def _obj(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise EvaluationError(f"{label} must be an object")
    return value


def _get(mapping: dict, key: str) -> Any:
    if key not in mapping:
        raise EvaluationError(f"Missing required field: {key}")
    return mapping[key]


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{label} must be a non-empty string")
    return value


def _bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise EvaluationError(f"{label} must be boolean")
    return value


def _num(value: Any, label: str, *, positive: bool = False) -> float:
    if type(value) not in (int, float):
        raise EvaluationError(f"{label} must be a finite number, not boolean")
    try:
        number = float(value)
    except OverflowError as exc:
        raise EvaluationError(f"{label} is outside finite floating-point range") from exc
    if not math.isfinite(number):
        raise EvaluationError(f"{label} must be finite")
    if number < 0 or (positive and number == 0):
        raise EvaluationError(f"{label} has invalid sign")
    return number


def _strings(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise EvaluationError(f"{label} must be a list with the required cardinality")
    for item in value:
        _text(item, label)
    if len(value) != len(set(value)):
        raise EvaluationError(f"{label} has duplicates")
    return value


def _and(*values: bool | None) -> bool | None:
    if False in values:
        return False
    if None in values:
        return None
    return True


def evaluate_episode(episode: dict, config: dict) -> dict:
    """Validate and evaluate one completed/partially recorded episode summary.

    Contact events must have been classified by a calibrated recorder. Hashes
    are format-checked only, never interpreted as proof of raw-data validity.
    """
    e, c = _obj(episode, 'episode'), _obj(config, 'config')
    if _get(e, 'schema_version') != 'qct.episode.v0.1':
        raise EvaluationError('Unsupported episode schema')
    if _get(c, 'schema_version') != 'qct.benchmark.v0.1':
        raise EvaluationError('Unsupported benchmark schema')
    if _text(_get(e, 'task_version'), 'episode task_version') != _text(_get(c, 'task_version'), 'config task_version'):
        raise EvaluationError('Task version mismatch')
    timeout = _num(_get(c, 'timeout_s'), 'timeout_s', positive=True)
    translation_limit = _num(_get(c, 'max_object_translation_m'), 'translation limit')
    rotation_limit = _num(_get(c, 'max_object_rotation_deg'), 'rotation limit')
    allowed_feet = _strings(_get(c, 'allowed_ground_contact_links'), 'allowed feet')
    if len(allowed_feet) != 4:
        raise EvaluationError('Exactly four allowed foot links are required')
    for key in ('episode_id', 'scene_id', 'method_id'):
        _text(_get(e, key), key)
    if type(_get(e, 'seed')) is not int or e['seed'] < 0:
        raise EvaluationError('seed must be a nonnegative integer')
    kind = _get(e, 'data_kind')
    mode = _get(e, 'observation_mode')
    if kind not in ('synthetic_fixture', 'simulation', 'real_robot'):
        raise EvaluationError('Unsupported data_kind')
    if mode not in ('synthetic_fixture', 'onboard', 'oracle'):
        raise EvaluationError('Unsupported observation_mode')
    if (kind == 'synthetic_fixture') != (mode == 'synthetic_fixture'):
        raise EvaluationError('Fixture kind and observation mode must match')
    feasibility = _get(e, 'scene_feasibility')
    if feasibility not in ('witness', 'unknown', 'infeasible'):
        raise EvaluationError('Unsupported scene_feasibility')
    duration = _num(_get(e, 'duration_s'), 'duration_s', positive=True)
    expected = _strings(_get(e, 'expected_object_ids'), 'expected_object_ids', allow_empty=True)
    integrity = _obj(_get(e, 'integrity'), 'integrity')
    for key in ('episode_complete', 'contact_monitor_complete', 'object_tracking_complete'):
        _bool(_get(integrity, key), key)
    outcome = _obj(_get(e, 'outcome'), 'outcome')
    failure_flags = ('fallen', 'emergency_stop', 'manual_intervention',
                     'boundary_violation', 'prohibited_airborne',
                     'obstacle_supported', 'timed_out')
    for key in ('goal_reached', 'goal_settled') + failure_flags:
        _bool(_get(outcome, key), key)
    if outcome['goal_settled'] and not outcome['goal_reached']:
        raise EvaluationError('Goal cannot be settled before it is reached')
    failures = [key for key in failure_flags if outcome[key]]
    if duration > timeout:
        failures.append('duration_exceeded')
    complete = integrity['episode_complete']
    if not complete:
        completion = False if failures else None
    else:
        completion = outcome['goal_reached'] and outcome['goal_settled'] and not failures
        if not outcome['goal_reached']:
            failures.append('goal_not_reached')
        elif not outcome['goal_settled']:
            failures.append('goal_not_settled')
    if feasibility == 'infeasible' and completion:
        raise EvaluationError('Completed traversal contradicts infeasible scene label')

    contacts = _get(e, 'contacts')
    if not isinstance(contacts, list):
        raise EvaluationError('contacts must be a list, including when empty')
    forbidden = []
    for index, contact in enumerate(contacts):
        event = _obj(contact, f'contact {index}')
        time = _num(_get(event, 'time_s'), 'contact time')
        if time > duration:
            raise EvaluationError('Contact timestamp exceeds episode duration')
        link = _text(_get(event, 'robot_link'), 'robot_link')
        other = _get(event, 'counterpart_type')
        if other not in ('ground', 'obstacle', 'wall', 'self'):
            raise EvaluationError('Unsupported counterpart_type')
        other_id = _text(_get(event, 'counterpart_id'), 'counterpart_id')
        if other == 'obstacle' and other_id not in expected:
            raise EvaluationError('Contact refers to undeclared obstacle')
        if not (other == 'ground' and link in allowed_feet):
            forbidden.append(event)
    contact_complete = complete and integrity['contact_monitor_complete']
    no_contact = False if forbidden else (True if contact_complete else None)

    objects = _get(e, 'objects')
    if not isinstance(objects, list):
        raise EvaluationError('objects must be a list')
    seen, disturbed = set(), []
    for item in objects:
        obj = _obj(item, 'object record')
        oid = _text(_get(obj, 'object_id'), 'object_id')
        if oid not in expected or oid in seen:
            raise EvaluationError('Unknown or duplicated tracked object')
        seen.add(oid)
        translation = _num(_get(obj, 'max_translation_m'), 'object translation')
        rotation = _num(_get(obj, 'max_rotation_deg'), 'object rotation')
        toppled = _bool(_get(obj, 'toppled'), 'toppled')
        if translation > translation_limit or rotation > rotation_limit or toppled:
            disturbed.append(oid)
    if integrity['object_tracking_complete'] and seen != set(expected):
        raise EvaluationError('Complete tracking flag contradicts missing objects')
    object_complete = complete and integrity['object_tracking_complete'] and seen == set(expected)
    no_disturbance = False if disturbed else (True if object_complete else None)

    provenance = _obj(_get(e, 'provenance'), 'provenance')
    hash_lengths = {'git_commit': 40, 'config_sha256': 64, 'scene_sha256': 64,
                    'geometry_sha256': 64, 'policy_sha256': 64, 'evidence_sha256': 64}
    for key, length in hash_lengths.items():
        value = _get(provenance, key)
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{%d}' % length, value)):
            raise EvaluationError(f'{key} must be null or a lowercase {length}-digit hash')
    provenance_complete = all(provenance[key] is not None for key in hash_lengths)
    strict = _and(completion, no_contact, no_disturbance)
    non_disturbing = _and(completion, no_disturbance)
    if forbidden:
        failures.append('forbidden_contact')
    if disturbed:
        failures.append('object_disturbed')
    unknown = []
    if not complete:
        unknown.append('episode_incomplete')
    if not contact_complete:
        unknown.append('contact_coverage_incomplete')
    if not object_complete:
        unknown.append('object_coverage_incomplete')
    if not provenance_complete:
        unknown.append('provenance_incomplete')
    onboard = kind in ('simulation', 'real_robot') and mode == 'onboard'
    real = kind == 'real_robot' and onboard
    return {
        'episode_id': e['episode_id'], 'data_kind': kind, 'observation_mode': mode,
        'scene_feasibility': feasibility, 'is_fixture': kind == 'synthetic_fixture',
        'metrics': {
            'completion_success': completion,
            'non_disturbing_success': non_disturbing,
            'strict_success': strict,
            'no_forbidden_contact_observed': no_contact,
            'no_object_disturbance_observed': no_disturbance,
            'forbidden_contact_events_observed': len(forbidden),
            'disturbed_object_ids_observed': disturbed,
        },
        'evidence': {
            'contact_coverage_complete': contact_complete,
            'object_coverage_complete': object_complete,
            'provenance_fields_complete': provenance_complete,
            'raw_evidence_independently_verified': False,
        },
        'scope': {
            'eligible_for_onboard_track': onboard,
            'eligible_for_real_robot_track': real,
            'onboard_recorded_success': strict if onboard and provenance_complete else None,
            'real_robot_recorded_success': strict if real and provenance_complete else None,
        },
        'failure_reasons': failures,
        'unknown_reasons': unknown,
        'warning': 'Summary-only verdict; raw evidence is not audited. Synthetic fixtures do not demonstrate robot capability.',
    }
