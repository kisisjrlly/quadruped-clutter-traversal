"""All cases are hand-authored SOFTWARE tests, never robot experiments."""
import copy
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path
from qct.evaluation import EvaluationError, evaluate_episode

ROOT = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.e = json.loads((ROOT/'examples/synthetic_episode_success.json').read_text())
        self.c = json.loads((ROOT/'configs/benchmark_v0_1.json').read_text())

    def evaluate(self):
        return evaluate_episode(self.e, self.c)

    def contact(self, link='rear_right_shank', kind='obstacle', oid='rod_0'):
        self.e['contacts'].append(dict(time_s=2.0, robot_link=link,
                                      counterpart_type=kind, counterpart_id=oid))

    def fill_mock_hashes(self):
        # Format-only fixtures. These hashes do NOT refer to real evidence.
        self.e['provenance'] = {k: ('a'*40 if k=='git_commit' else 'b'*64)
                                for k in self.e['provenance']}

    def test_clean_fixture_success_not_robot_result(self):
        result = self.evaluate()
        self.assertTrue(result['metrics']['strict_success'])
        self.assertTrue(result['is_fixture'])
        self.assertIsNone(result['scope']['real_robot_recorded_success'])
        self.assertFalse(result['evidence']['raw_evidence_independently_verified'])

    def test_contact_without_topple_is_not_strict_success(self):
        self.contact()
        result = self.evaluate()['metrics']
        self.assertTrue(result['non_disturbing_success'])
        self.assertFalse(result['strict_success'])

    def test_normal_foot_ground_support_allowed(self):
        self.contact('rear_left_foot', 'ground', 'floor')
        self.assertTrue(self.evaluate()['metrics']['strict_success'])

    def test_foot_on_obstacle_forbidden(self):
        self.contact('rear_left_foot')
        self.assertFalse(self.evaluate()['metrics']['strict_success'])

    def test_nonfoot_ground_contact_forbidden(self):
        self.contact('torso', 'ground', 'floor')
        self.assertFalse(self.evaluate()['metrics']['strict_success'])

    def test_wall_and_self_contacts_forbidden(self):
        for kind in ['wall', 'self']:
            with self.subTest(kind=kind):
                self.e['contacts'] = []
                self.contact('torso', kind, 'boundary_or_link')
                self.assertFalse(self.evaluate()['metrics']['strict_success'])

    def test_translation_maximum_not_final_pose(self):
        self.e['objects'][0]['max_translation_m'] = 0.01
        self.assertFalse(self.evaluate()['metrics']['strict_success'])

    def test_rotation_threshold(self):
        self.e['objects'][0]['max_rotation_deg'] = 2.1
        self.assertFalse(self.evaluate()['metrics']['strict_success'])

    def test_toppling_is_failure_even_if_position_unchanged(self):
        self.e['objects'][0]['toppled'] = True
        self.assertFalse(self.evaluate()['metrics']['strict_success'])

    def test_threshold_equality_is_allowed(self):
        self.e['objects'][0]['max_translation_m'] = self.c['max_object_translation_m']
        self.e['objects'][0]['max_rotation_deg'] = self.c['max_object_rotation_deg']
        self.assertTrue(self.evaluate()['metrics']['strict_success'])

    def test_unknown_contact_coverage_not_zero(self):
        self.e['integrity']['contact_monitor_complete'] = False
        self.assertIsNone(self.evaluate()['metrics']['strict_success'])

    def test_unknown_object_coverage_not_zero(self):
        self.e['integrity']['object_tracking_complete'] = False
        self.e['objects'] = []
        self.assertIsNone(self.evaluate()['metrics']['strict_success'])

    def test_known_collision_still_fails_with_other_missing_evidence(self):
        self.e['integrity']['contact_monitor_complete'] = False
        self.e['integrity']['object_tracking_complete'] = False
        self.contact()
        self.assertFalse(self.evaluate()['metrics']['strict_success'])

    def test_missing_object_contradicts_complete_tracking(self):
        self.e['objects'].pop()
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_incomplete_episode_cannot_pass(self):
        self.e['integrity']['episode_complete'] = False
        self.assertIsNone(self.evaluate()['metrics']['completion_success'])
        self.assertIsNone(self.evaluate()['metrics']['strict_success'])

    def test_all_prohibited_outcomes_fail(self):
        for flag in ['fallen','emergency_stop','manual_intervention','boundary_violation',
                     'prohibited_airborne','obstacle_supported','timed_out']:
            with self.subTest(flag=flag):
                self.e['outcome'][flag] = True
                self.assertFalse(self.evaluate()['metrics']['strict_success'])
                self.e['outcome'][flag] = False

    def test_safely_stopped_not_completed(self):
        self.e['outcome']['goal_reached'] = False
        self.e['outcome']['goal_settled'] = False
        self.assertFalse(self.evaluate()['metrics']['completion_success'])

    def test_goal_must_settle(self):
        self.e['outcome']['goal_settled'] = False
        self.assertFalse(self.evaluate()['metrics']['strict_success'])

    def test_duration_limit(self):
        self.e['duration_s'] = self.c['timeout_s']
        self.assertTrue(self.evaluate()['metrics']['strict_success'])
        self.e['duration_s'] += 0.001
        self.assertFalse(self.evaluate()['metrics']['strict_success'])

    def test_oracle_cannot_be_onboard_claim(self):
        self.e.update(data_kind='simulation', observation_mode='oracle')
        self.fill_mock_hashes()
        result = self.evaluate()
        self.assertTrue(result['metrics']['strict_success'])
        self.assertIsNone(result['scope']['onboard_recorded_success'])

    def test_simulation_cannot_be_real_robot_claim(self):
        self.e.update(data_kind='simulation', observation_mode='onboard')
        self.fill_mock_hashes()
        result = self.evaluate()
        self.assertTrue(result['scope']['onboard_recorded_success'])
        self.assertIsNone(result['scope']['real_robot_recorded_success'])

    def test_missing_provenance_not_ready_for_track_reporting(self):
        self.e.update(data_kind='real_robot', observation_mode='onboard')
        self.assertIsNone(self.evaluate()['scope']['real_robot_recorded_success'])

    def test_hashes_are_only_format_checked_never_evidence_verified(self):
        self.e.update(data_kind='real_robot', observation_mode='onboard')
        self.fill_mock_hashes()
        result = self.evaluate()
        self.assertTrue(result['scope']['real_robot_recorded_success'])
        self.assertFalse(result['evidence']['raw_evidence_independently_verified'])

    def test_nan_inf_negative_boolean_numeric_rejected(self):
        for value in [math.nan,math.inf,-1,True,0,'five']:
            with self.subTest(value=value):
                self.e['duration_s'] = value
                with self.assertRaises(EvaluationError):
                    self.evaluate()

    def test_out_of_range_integer_is_clean_validation_error(self):
        self.e['duration_s'] = 10 ** 1000
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_empty_calibration_scene_supported(self):
        self.e['expected_object_ids'] = []
        self.e['objects'] = []
        self.e['contacts'] = []
        self.assertTrue(self.evaluate()['metrics']['strict_success'])

    def test_matching_missing_task_versions_are_invalid(self):
        for value in [None, '', 1]:
            with self.subTest(value=value):
                self.e['task_version'] = self.c['task_version'] = value
                with self.assertRaises(EvaluationError):
                    self.evaluate()

    def test_boolean_flags_are_strict(self):
        self.e['outcome']['goal_reached'] = 1
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_schema_and_task_version_mismatch(self):
        for field in ['schema_version','task_version']:
            with self.subTest(field=field):
                old=self.e[field]; self.e[field]='invalid'
                with self.assertRaises(EvaluationError):
                    self.evaluate()
                self.e[field]=old

    def test_incompatible_fixture_mode(self):
        self.e['observation_mode']='onboard'
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_duplicate_object_rejected(self):
        self.e['objects'].append(copy.deepcopy(self.e['objects'][0]))
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_undeclared_obstacle_rejected(self):
        self.contact(oid='not_declared')
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_future_contact_rejected(self):
        self.e['contacts'][0]['time_s']=100
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_infeasible_label_conflict(self):
        self.e['scene_feasibility']='infeasible'
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_missing_required_field_rejected(self):
        del self.e['contacts']
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_bad_hash_rejected(self):
        self.e['provenance']['git_commit']='not-a-commit'
        with self.assertRaises(EvaluationError):
            self.evaluate()

    def test_cli_valid_failure_returns_json_not_task_success(self):
        run=subprocess.run([sys.executable,'-m','qct','evaluate',
                            'examples/synthetic_episode_contact.json'],
                           cwd=ROOT,text=True,capture_output=True,check=False)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertFalse(json.loads(run.stdout)['metrics']['strict_success'])

    def test_cli_missing_file_fails_cleanly(self):
        run=subprocess.run([sys.executable,'-m','qct','evaluate','no-such-file.json'],
                           cwd=ROOT,text=True,capture_output=True,check=False)
        self.assertEqual(run.returncode,2)
        self.assertIn('Invalid input',run.stderr)


if __name__ == '__main__':
    unittest.main()
