"""CPU numerical/unit tests. Artificial trajectories below are NOT robot experiments."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from qct.scene import Scene, Obstacle, generate_scene, digest
from qct.geometry import (Capsule, capsule_clearance, swept_capsule_clearance, point_distance,
                          scene_distance, quat_angle_deg, rotate, support_margin)
from qct.planning import plan_body_route, plan_foot_swing, choose_foothold
from qct.perception import Pinhole, unproject, VoxelMemory
from qct.recording import EpisodeRecorder, empty_outcome, audit_trace
from qct.contacts import ContactClassifier, under
from qct.control import RouteFollower, PolicyContract
from qct.statistics import wilson, summarize
from qct.evaluation import evaluate_episode

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/'configs/benchmark_v0_1.json').read_text())


class SceneTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(generate_scene(7).sha256, generate_scene(7).sha256)
    def test_split_changes_layout(self):
        a,b = generate_scene(7,'train'), generate_scene(7,'test')
        self.assertNotEqual(a.obstacles[0].position,b.obstacles[0].position)
    def test_roundtrip(self):
        s = generate_scene(8)
        self.assertEqual(s.sha256,Scene.from_dict(json.loads(json.dumps(s.to_dict()))).sha256)
    def test_save_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            s=generate_scene(0,count=0); p=Path(d)/'s.json'; s.save(p)
            with self.assertRaises(FileExistsError): s.save(p)
    def test_packing(self):
        for seed in range(20):
            s=generate_scene(seed,count=32)
            self.assertEqual(len(s.obstacles),32)
            self.assertEqual(s.feasibility,'unknown')
    def test_bad_count(self):
        for count in (-1,129,True,1.5):
            with self.subTest(count=count), self.assertRaises(ValueError): generate_scene(0,count=count)
    def test_bad_seed(self):
        for seed in (-1,False,1.2):
            with self.subTest(seed=seed), self.assertRaises(ValueError): generate_scene(seed)
    def test_invalid_dimensions(self):
        for width in (float('nan'),0,.5):
            with self.subTest(width=width), self.assertRaises(ValueError): generate_scene(0,width_m=width)
    def test_overlap_rejected(self):
        o=Obstacle('a','box',(2,0,.1),(.1,.1,.2))
        p=Obstacle('b','box',(2,0,.1),(.1,.1,.2))
        with self.assertRaises(ValueError): Scene(0,'test',6,2,(.5,0,.4),(5,0,.4),(o,p))
    def test_no_fixed_fragile_object(self):
        with self.assertRaises(ValueError): Obstacle('a','box',(2,0,.1),(.1,.1,.2),mass_kg=0)
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError): digest({'bad':float('nan')})
    def test_no_feasibility_claim(self):
        d=generate_scene(0,count=0).to_dict(); d['feasibility']='witness'
        with self.assertRaises(ValueError): Scene.from_dict(d)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.box=Obstacle('box','box',(2,0,.5),(1,1,1))
    def test_box_sdf(self):
        self.assertAlmostEqual(point_distance((2,0,.5),self.box),-.5)
        self.assertAlmostEqual(point_distance((3,0,.5),self.box),.5)
    def test_cylinder_sdf(self):
        c=Obstacle('c','cylinder',(2,0,.5),(.2,.2,1))
        self.assertAlmostEqual(point_distance((2,0,.5),c),-.1)
        self.assertAlmostEqual(point_distance((2,0,1.5),c),.5)
    def test_yawed_box(self):
        b=Obstacle('b','box',(2,0,.5),(.2,1,1),yaw=math.pi/2)
        self.assertAlmostEqual(point_distance((2.4,0,.5),b),-.1)
    def test_quaternion_double_cover(self):
        self.assertAlmostEqual(quat_angle_deg((1,0,0,0),(-1,0,0,0)),0)
    def test_quaternion_rotation(self):
        self.assertAlmostEqual(rotate((0,1,0,0),(0,0,1))[2],-1)
    def test_bad_quaternion(self):
        with self.assertRaises(ValueError): rotate((0,0,0,0),(0,0,1))
    def test_capsule_between_samples(self):
        # Samples at x=0 and 1 alone would miss the thin rod at .5.
        c=Capsule('calf',(0,0,0),(1,0,0),.01)
        bound=capsule_clearance(c,lambda p:math.hypot(p[0]-.5,p[1])-.001,resolution=1)
        self.assertLess(bound,0)
    def test_unknown_capsule(self):
        self.assertIsNone(capsule_clearance(Capsule('a',(0,0,0),(1,0,0),.1),lambda _:None))
    def test_sweep_catches_between_keyframes(self):
        a=Capsule('a',(-1,0,0),(-1,0,1),.01); b=Capsule('a',(1,0,0),(1,0,1),.01)
        result=swept_capsule_clearance(a,b,lambda p:math.hypot(p[0],p[1])-.01,steps=1)
        self.assertLess(result,0)
    def test_sweep_unknown(self):
        c=Capsule('a',(0,0,0),(0,0,1),.1)
        self.assertIsNone(swept_capsule_clearance(c,c,lambda _:None))
    def test_link_mismatch(self):
        with self.assertRaises(ValueError):
            swept_capsule_clearance(Capsule('a',(0,0,0),(1,0,0),.1),Capsule('b',(0,0,0),(1,0,0),.1),lambda _:1)
    def test_support_polygon(self):
        self.assertGreater(support_margin((0,0),[(-1,-1),(1,-1),(0,1)]),0)
        self.assertLess(support_margin((3,0),[(-1,-1),(1,-1),(0,1)]),0)
    def test_degenerate_support(self):
        self.assertEqual(support_margin((0,0),[(0,0),(1,0)]),-math.inf)


class PlanningTests(unittest.TestCase):
    def test_empty_route(self):
        s=generate_scene(0,count=0); p=plan_body_route(s,resolution=.2)
        self.assertEqual(p.status,'found'); self.assertEqual(p.points[0],s.start); self.assertEqual(p.points[-1],s.goal)
    def test_budget_no_fake_infeasible(self):
        p=plan_body_route(generate_scene(0,count=0),max_expansions=1)
        self.assertEqual(p.status,'budget_exhausted')
    def test_swing_around_low_block(self):
        o=Obstacle('b','box',(.5,0,.05),(.1,.1,.1))
        p=plan_foot_swing((0,0,.03),(1,0,.03),lambda p:point_distance(p,o))
        self.assertEqual(p.status,'found')
    def test_unknown_swing_rejected(self):
        self.assertNotEqual(plan_foot_swing((0,0,.1),(1,0,.1),lambda _:None).status,'found')
    def test_foothold_reachability(self):
        self.assertIsNone(choose_foothold((0,0,0),lambda _:1,reachable=lambda _:False))
    def test_foothold_unknown(self):
        self.assertIsNone(choose_foothold((0,0,0),lambda _:None))
    def test_route_follower_turns(self):
        c=RouteFollower([(0,1,0)]).command((0,0,0),0)
        self.assertGreater(c[2],0); self.assertLess(c[0],.01)
    def test_route_follower_stops(self):
        self.assertEqual(RouteFollower([(0,0,0)]).command((0,0,0),0),(0.,0.,0.))


class PerceptionTests(unittest.TestCase):
    def test_optical_unprojection(self):
        pts=unproject([[1,1]],Pinhole(2,1,1,1,0,0),(0,0,0),(1,0,0,0))
        self.assertEqual(pts,[(0.,0.,1.),(1.,0.,1.)])
    def test_invalid_depth_not_free(self):
        pts=unproject([[float('nan'),float('inf'),0,True]],Pinhole(4,1,1,1,0,0),(0,0,0),(1,0,0,0))
        self.assertEqual(pts,[])
    def test_map_occupied_free_unknown(self):
        m=VoxelMemory(resolution=.1); m.integrate((0,0,0),[(1,0,0)],0)
        self.assertEqual(m.state((1,0,0),0),'occupied')
        self.assertEqual(m.state((.5,0,0),0),'free_observed')
        self.assertEqual(m.state((1.5,0,0),0),'unknown')
    def test_age(self):
        m=VoxelMemory(max_age_s=1); m.integrate((0,0,0),[(1,0,0)],0)
        self.assertEqual(m.state((1,0,0),1.1),'unknown')
    def test_episode_reset(self):
        m=VoxelMemory(); m.integrate((0,0,0),[(1,0,0)],2); m.reset(); m.integrate((0,0,0),[],0)
        self.assertEqual(m.state((1,0,0),0),'unknown')
    def test_duplicate_frame(self):
        m=VoxelMemory(); m.integrate((0,0,0),[],0)
        with self.assertRaises(ValueError): m.integrate((0,0,0),[],0)
    def test_capacity_atomic(self):
        m=VoxelMemory(resolution=.1,max_cells=1)
        with self.assertRaises(MemoryError): m.integrate((0,0,0),[(2,0,0)],0)
        self.assertFalse(m.cells)
    def test_hits_win(self):
        m=VoxelMemory(resolution=.1); m.integrate((0,0,0),[(1,0,0),(2,0,0)],0)
        self.assertEqual(m.state((1,0,0),0),'occupied')
    def test_past_query(self):
        m=VoxelMemory();m.integrate((0,0,0),[],2)
        with self.assertRaises(ValueError): m.state((0,0,0),1)


class ContactTests(unittest.TestCase):
    def setUp(self):
        self.c=ContactClassifier('/R',{'/O/b':'b'},('/G',),('/W',),{'/R/calf/foot':'front_left_foot'})
    def test_path_boundary(self):
        self.assertFalse(under('/RobotOther','/Robot'))
    def test_specific_foot_collider(self):
        e,ok=self.c.classify('/R/calf','/G','/R/calf/foot','/G/shape')
        self.assertTrue(ok); self.assertEqual(e['robot_link'],'front_left_foot')
    def test_calf_not_foot(self):
        e,_=self.c.classify('/R/calf','/G','/R/calf/shin','/G')
        self.assertEqual(e['robot_link'],'calf')
    def test_reverse_pair(self):
        e,ok=self.c.classify('/O/b','/R/base','/O/b/s','/R/base/s')
        self.assertTrue(ok);self.assertEqual(e['counterpart_type'],'obstacle')
    def test_self_contact(self):
        e,_=self.c.classify('/R/a','/R/b','/R/a/s','/R/b/s')
        self.assertEqual(e['counterpart_type'],'self')
    def test_unknown_invalidates(self):
        e,ok=self.c.classify('/R/a','/mystery','/R/a/s','/mystery')
        self.assertIsNone(e);self.assertFalse(ok)
    def test_object_ground_ignored(self):
        self.assertEqual(self.c.classify('/O/b','/G','/O/b/s','/G'),(None,True))


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'trace.jsonl'
        self.s=generate_scene(0,count=1)
        self.r=EpisodeRecorder(self.path,self.s,CONFIG,episode_id='unit-test-artificial',method_id='unit-test',
                               observation_mode='oracle',physics_dt=.01,contact_calibration_id='unit-test-not-real-calibration')
        self.robot={'position':(.6,0,.4),'quaternion_wxyz':(1,0,0,0)}
        self.objects={o.object_id:{'position':o.position,'quaternion_wxyz':(1,0,0,0)} for o in self.s.obstacles}
    def tearDown(self):
        self.r.abort();self.tmp.cleanup()
    def finish(self,**flags):
        out=empty_outcome();out.update(goal_reached=True,goal_settled=True);out.update(flags)
        return self.r.finish(out)
    def frame(self,t,objects=None,events=None,coverage=True,reset=False):
        self.r.frame(t,self.robot,self.objects if objects is None else objects,events or [],contact_coverage=coverage,reset_detected=reset)
    def test_trace_reduction(self):
        self.frame(0);self.frame(.01);s=self.finish()
        self.assertTrue(audit_trace(self.path,s)['structural_audit_passed'])
    def test_maximum_not_final_only(self):
        self.frame(0);o=copy.deepcopy(self.objects);oid=next(iter(o));p=o[oid]['position'];o[oid]['position']=(p[0]+.02,p[1],p[2])
        self.frame(.01,o);self.frame(.02);s=self.finish()
        self.assertAlmostEqual(s['objects'][0]['max_translation_m'],.02)
        self.assertFalse(evaluate_episode(s,CONFIG)['metrics']['strict_success'])
    def test_missing_frame(self):
        self.frame(0);self.frame(.02);s=self.finish()
        self.assertFalse(s['integrity']['episode_complete'])
        self.assertFalse(audit_trace(self.path,s)['structural_audit_passed'])
    def test_missing_object(self):
        self.frame(0);self.frame(.01,objects={});s=self.finish()
        self.assertFalse(s['integrity']['object_tracking_complete'])
    def test_uncalibrated_contacts(self):
        self.r.calibration=None;self.frame(0);self.frame(.01);s=self.finish()
        self.assertIsNone(evaluate_episode(s,CONFIG)['metrics']['strict_success'])
    def test_incomplete_monitor(self):
        self.frame(0);self.frame(.01,coverage=False);s=self.finish()
        self.assertFalse(s['integrity']['contact_monitor_complete'])
    def test_contact_no_displacement(self):
        self.frame(0);self.frame(.01,events=[dict(robot_link='calf',counterpart_type='obstacle',counterpart_id='object_000')]);s=self.finish()
        self.assertFalse(evaluate_episode(s,CONFIG)['metrics']['strict_success'])
    def test_tampered_summary(self):
        self.frame(0);self.frame(.01);s=self.finish();s['objects'][0]['max_translation_m']=.123
        self.assertIn('summary_reduction_mismatch',audit_trace(self.path,s)['errors'])
    def test_tampered_trace(self):
        self.frame(0);self.frame(.01);s=self.finish()
        with self.path.open('ab') as f:f.write(b'{}\n')
        self.assertFalse(audit_trace(self.path,s)['structural_audit_passed'])
    def test_auto_reset_flag(self):
        self.frame(0);self.frame(.01,reset=True);s=self.finish()
        self.assertFalse(s['integrity']['episode_complete'])
    def test_repeated_terminal(self):
        self.frame(0);self.frame(.01);self.finish()
        with self.assertRaises(ValueError): self.r.finish(empty_outcome())
    def test_abort_not_success(self):
        self.frame(0);self.r.abort()
        self.assertNotIn('terminal',self.path.read_text())
    def test_bool_coverage_required(self):
        with self.assertRaises(ValueError):self.frame(0,coverage=1)
    def test_no_timestamp_reversal(self):
        self.frame(0);self.frame(.01)
        with self.assertRaises(ValueError):self.frame(.005)


class StatisticsTests(unittest.TestCase):
    def test_wilson_empty(self):self.assertIsNone(wilson(0,0))
    def test_wilson_perfect_not_certainty(self):self.assertLess(wilson(10,10)[0],1)
    def test_bad_counts(self):
        with self.assertRaises(ValueError):wilson(2,1)
    def test_unknown_denominator(self):
        e=json.loads((ROOT/'examples/synthetic_episode_success.json').read_text());e['integrity']['contact_monitor_complete']=False
        s=summarize([e],CONFIG)[0]
        self.assertEqual(s['unknown'],1);self.assertEqual(s['missingness_bounds'],(0.,1.))
    def test_duplicate_rejected(self):
        e=json.loads((ROOT/'examples/synthetic_episode_success.json').read_text())
        with self.assertRaises(ValueError):summarize([e,e],CONFIG)
    def test_track_separation(self):
        e=json.loads((ROOT/'examples/synthetic_episode_success.json').read_text());f=copy.deepcopy(e);f['method_id']='different'
        self.assertEqual(len(summarize([e,f],CONFIG)),2)


class PolicyTests(unittest.TestCase):
    def spec(self):
        return dict(schema_version='qct.policy.v1',joint_names=[f'j{i}' for i in range(12)],
                    observation_layout='lin3_ang3_gravity3_command3_q12_dq12_previous12',
                    observation_scale=[1]*48,action_scale=[.25]*12,default_joint_positions=[0]*12,
                    control_period_s=.02,action_clip=100.,exported_normalizer_included=True,policy_sha256='a'*64)
    def test_policy_order(self):
        s=self.spec(); c=PolicyContract(s,list(reversed(s['joint_names'])))
        self.assertEqual(c.indices,list(reversed(range(12))))
    def test_mismatched_joints(self):
        with self.assertRaises(ValueError):PolicyContract(self.spec(),['bad']*12)
    def test_missing_normalizer(self):
        s=self.spec();s['exported_normalizer_included']='true'
        with self.assertRaises(ValueError):PolicyContract(s,s['joint_names'])
    def test_bad_hash(self):
        s=self.spec();s['policy_sha256']='unknown'
        with self.assertRaises(ValueError):PolicyContract(s,s['joint_names'])
    def test_no_isaac_import_for_core(self):
        import qct.sim.runtime
        self.assertTrue(callable(qct.sim.runtime.run))
