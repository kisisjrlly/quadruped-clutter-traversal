"""Single-environment Isaac Lab evaluation runner. Not a trained traversal method.

All current motion modes are explicitly oracle diagnostics. Camera capture is
separate from the actor. No automatic reset; terminal evidence precedes teardown.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess
import importlib.metadata

from qct.scene import Scene, digest
from qct.control import PolicyContract, RouteFollower
from qct.contacts import ContactClassifier
from qct.geometry import rotate
from qct.planning import plan_body_route
from qct.recording import EpisodeRecorder, empty_outcome, audit_trace
from qct.evaluation import evaluate_episode


def _json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def run(args, app):
    # Isaac dependencies must be imported AFTER AppLauncher.
    import torch
    import isaaclab.sim as sim_utils
    from isaaclab.assets import Articulation, RigidObject, RigidObjectCfg
    from isaaclab_assets import UNITREE_GO2_CFG
    from isaaclab.sensors import Camera, CameraCfg
    from pxr import UsdGeom, UsdPhysics
    from qct.sim.physx_contacts import PhysxContacts

    scene = Scene.load(args.scene)
    config = json.loads(Path(args.benchmark).read_text())
    if args.duration <= 0 or args.duration > config['timeout_s'] or args.dt <= 0 or args.dt > 0.01:
        raise ValueError('Invalid duration/dt; reference dt must be <= 10 ms')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)  # never overwrite a previous experiment
    sim_cfg = sim_utils.SimulationCfg(dt=args.dt, device=args.device)
    sim_cfg.physx.enable_ccd = True
    sim = sim_utils.SimulationContext(sim_cfg)
    sim.set_camera_view([scene.length_m/2, -scene.width_m*2, 3.0], [scene.length_m/2, 0, 0.25])
    ground_cfg = sim_utils.GroundPlaneCfg()
    ground_cfg.func('/World/Ground', ground_cfg)
    light = sim_utils.DomeLightCfg(intensity=2000)
    light.func('/World/Light', light)
    robot_cfg = UNITREE_GO2_CFG.replace(prim_path='/World/Robot')
    robot_cfg.init_state.pos = scene.start
    robot_cfg.spawn.articulation_props.enabled_self_collisions = True
    robot_cfg.spawn.articulation_props.solver_position_iteration_count = 8
    robot_cfg.spawn.articulation_props.solver_velocity_iteration_count = 2
    robot_cfg.spawn.rigid_props.enable_ccd = True
    robot = Articulation(robot_cfg)
    rigid_objects = {}
    for obstacle in scene.obstacles:
        material = sim_utils.RigidBodyMaterialCfg(static_friction=obstacle.friction,
                                                  dynamic_friction=obstacle.friction, restitution=0.0)
        common = dict(rigid_props=sim_utils.RigidBodyPropertiesCfg(enable_ccd=True),
                      collision_props=sim_utils.CollisionPropertiesCfg(),
                      mass_props=sim_utils.MassPropertiesCfg(mass=obstacle.mass_kg),
                      physics_material=material, activate_contact_sensors=True)
        spawn = (sim_utils.CuboidCfg(size=obstacle.size, **common) if obstacle.shape == 'box'
                 else sim_utils.CylinderCfg(radius=obstacle.size[0]/2, height=obstacle.size[2], **common))
        cfg = RigidObjectCfg(prim_path=f'/World/Clutter/{obstacle.object_id}', spawn=spawn,
                            init_state=RigidObjectCfg.InitialStateCfg(pos=obstacle.position,
                                rot=(math.cos(obstacle.yaw/2), 0, 0, math.sin(obstacle.yaw/2))))
        rigid_objects[obstacle.object_id] = RigidObject(cfg)
    walls = []
    wall_specs = [('Left', (scene.length_m/2, scene.width_m/2+0.025, 0.5), (scene.length_m, .05, 1.0)),
                  ('Right', (scene.length_m/2, -scene.width_m/2-.025, 0.5), (scene.length_m, .05, 1.0)),
                  ('Start', (-.025, 0, .5), (.05, scene.width_m, 1.0)),
                  ('End', (scene.length_m+.025, 0, .5), (.05, scene.width_m, 1.0))]
    for name, pos, size in wall_specs:
        path = '/World/Walls/'+name
        cfg = sim_utils.CuboidCfg(size=size, collision_props=sim_utils.CollisionPropertiesCfg())
        cfg.func(path, cfg, translation=pos)
        walls.append(path)
    camera = None
    if args.enable_cameras:
        # Front-facing optical +Z frame; source convention checked against v2.3 tutorial.
        camera = Camera(CameraCfg(prim_path='/World/Robot/base/front_cam', update_period=.1,
            width=320, height=240, data_types=['distance_to_image_plane'],
            spawn=sim_utils.PinholeCameraCfg(focal_length=12.0, horizontal_aperture=20.955,
                                           clipping_range=(.05, 5.0)),
            offset=CameraCfg.OffsetCfg(pos=(.30, 0, .05), rot=(.5, -.5, .5, -.5), convention='ros')))
    aliases = json.loads(Path(args.link_map).read_text()) if args.link_map else {}
    classifier = ContactClassifier('/World/Robot', {f'/World/Clutter/{o.object_id}':o.object_id for o in scene.obstacles},
                                   ('/World/Ground',), tuple(walls), aliases)
    monitor = PhysxContacts(sim.stage, classifier)
    sim.reset()
    robot.update(args.dt)
    for obj in rigid_objects.values():
        obj.update(args.dt)
    body_names, joint_names = list(robot.body_names), list(robot.joint_names)
    collision_inventory = []
    for prim in sim.stage.Traverse():
        if str(prim.GetPath()).startswith('/World/Robot/') and prim.HasAPI(UsdPhysics.CollisionAPI):
            collision_inventory.append(str(prim.GetPath()))
    if not collision_inventory:
        raise RuntimeError('Robot collision inventory is empty')
    try:
        commit = subprocess.check_output(['git','rev-parse','HEAD'], cwd=Path(__file__).parents[2], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git','status','--porcelain'], cwd=Path(__file__).parents[2], text=True))
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    versions = {}
    for package in ('isaaclab', 'isaacsim', 'torch'):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = 'distribution_metadata_unavailable'
    manifest = dict(schema_version='qct.run.v1', mode=args.mode, observation_mode='oracle',
                    scene_sha256=scene.sha256, benchmark_sha256=digest(config), dt=args.dt, ccd_requested=True,
                    self_collisions_requested=True, software=versions, git_commit=commit, git_dirty=dirty,
                    robot_usd=robot_cfg.spawn.usd_path, robot_asset_bytes_sha256=None,
                    physics_configuration_repr=repr(sim_cfg.to_dict()),
                    source_file_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    body_names=body_names, joint_names=joint_names, collision_inventory=collision_inventory,
                    contact_rigid_inventory=monitor.inventory, foot_aliases=aliases,
                    camera_enabled=camera is not None, contact_calibration_verified=False,
                    warning='Integration not validated by CPU tests. USD path/inventory hash is not a mesh-content hash.')
    _json(output/'run.json', manifest)
    _json(output/'scene.json', scene.to_dict())
    _json(output/'benchmark.json', config)
    policy, contract, follower, policy_hash = None, None, None, None
    action = torch.zeros((1, robot.num_joints), device=robot.device)
    targets = robot.data.default_joint_pos.clone()
    control_stride = 4
    if args.mode == 'policy-route':
        if not args.policy or not args.policy_spec:
            raise ValueError('Moving mode requires --policy and --policy-spec; no checkpoint is bundled')
        spec = json.loads(Path(args.policy_spec).read_text())
        contract = PolicyContract(spec, joint_names)
        policy_hash = hashlib.sha256(Path(args.policy).read_bytes()).hexdigest()
        if policy_hash != spec['policy_sha256']:
            raise ValueError('Policy bytes differ from policy spec')
        control_stride = round(contract.period_s/args.dt)
        if control_stride < 1 or abs(control_stride*args.dt-contract.period_s) > 1e-9:
            raise ValueError('Policy period must be an exact physics-step multiple')
        policy = torch.jit.load(args.policy, map_location=robot.device).eval()
        route = plan_body_route(scene, radius=args.body_radius)
        _json(output/'body_route.json', route.__dict__)
        if route.status != 'found':
            raise RuntimeError('Weak body planner found no route; this does not prove task infeasibility')
        follower = RouteFollower(route.points, speed=.15)
    recorder = EpisodeRecorder(output/'trace.jsonl', scene, config, episode_id=output.name,
        method_id='isaaclab-'+args.mode+'-diagnostic', observation_mode='oracle', physics_dt=args.dt,
        provenance={'git_commit':commit, 'policy_sha256':policy_hash}, contact_calibration_id=None)
    camera_dir = output/'camera'
    if camera is not None:
        camera_dir.mkdir()
    def snapshot():
        r = dict(position=robot.data.root_pos_w[0].tolist(), quaternion_wxyz=robot.data.root_quat_w[0].tolist(),
                 linear_velocity=robot.data.root_lin_vel_w[0].tolist(),
                 angular_velocity=robot.data.root_ang_vel_w[0].tolist(),
                 joint_positions=robot.data.joint_pos[0].tolist(), joint_velocities=robot.data.joint_vel[0].tolist(),
                 body_positions=robot.data.body_pos_w[0].tolist())
        objects = {oid:dict(position=obj.data.root_pos_w[0].tolist(), quaternion_wxyz=obj.data.root_quat_w[0].tolist())
                   for oid,obj in rigid_objects.items()}
        events, unknown, complete = monitor.drain()
        r['unclassified_contacts'] = unknown
        return r, objects, events, complete
    outcome, settled, completed = empty_outcome(), 0.0, False
    previous_camera_frame = -1
    try:
        r, objects, events, complete = snapshot()
        recorder.frame(0.0, r, objects, events, contact_coverage=False)  # initial contacts not yet solved
        for step in range(1, math.ceil(args.duration/args.dt)+1):
            if not app.is_running() or not sim.is_playing():
                outcome['emergency_stop'] = True
                break
            if policy is not None and (step-1) % control_stride == 0:
                q = robot.data.root_quat_w[0].tolist()
                yaw = math.atan2(2*(q[0]*q[3]+q[1]*q[2]), 1-2*(q[2]**2+q[3]**2))
                command = torch.tensor([follower.command(robot.data.root_pos_w[0].tolist(), yaw)], device=robot.device)
                ix = contract.indices
                dq = robot.data.joint_pos[:,ix] - torch.tensor([contract.default_q], device=robot.device)
                obs = torch.cat((robot.data.root_lin_vel_b, robot.data.root_ang_vel_b,
                                 robot.data.projected_gravity_b, command, dq,
                                 robot.data.joint_vel[:,ix], action[:,ix]), dim=-1)
                with torch.inference_mode():
                    result = policy(obs * torch.tensor([contract.obs_scale], device=robot.device))
                if not isinstance(result, torch.Tensor) or tuple(result.shape) != (1,12) or not torch.isfinite(result).all():
                    raise RuntimeError('Invalid policy action tensor')
                action[:,ix] = result.clamp(-contract.action_clip,contract.action_clip)
                targets[:,ix] = torch.tensor([contract.default_q],device=robot.device) + action[:,ix]*torch.tensor([contract.action_scale],device=robot.device)
                limits = robot.data.soft_joint_pos_limits
                targets = torch.maximum(torch.minimum(targets, limits[:,:,1]), limits[:,:,0])
            robot.set_joint_position_target(targets)
            robot.write_data_to_sim()
            sim.step(render=not args.headless or camera is not None)
            robot.update(args.dt)
            for obj in rigid_objects.values():
                obj.update(args.dt)
            t = step*args.dt
            if camera is not None:
                camera.update(args.dt)
                frame = int(camera.frame[0])
                if frame != previous_camera_frame:
                    import numpy as np
                    depth = camera.data.output['distance_to_image_plane'][0].detach().cpu().numpy()
                    np.savez_compressed(camera_dir/f'{frame:06d}.npz', depth=depth,
                        intrinsic=camera.data.intrinsic_matrices[0].cpu().numpy(),
                        position=camera.data.pos_w[0].cpu().numpy(),
                        quaternion_wxyz=camera.data.quat_w_ros[0].cpu().numpy(), time_s=t,
                        pose_source='simulation_ground_truth_not_estimated_odometry')
                    previous_camera_frame = frame
            r, objects, events, complete = snapshot()
            recorder.frame(t, r, objects, events, contact_coverage=complete)
            p = r['position']
            speed = math.sqrt(sum(v*v for v in r['linear_velocity']))
            spin = math.sqrt(sum(v*v for v in r['angular_velocity']))
            upright = rotate(r['quaternion_wxyz'], (0,0,1))[2]
            outcome['fallen'] |= p[2] < .15 or upright < .5
            # Check all rigid-body origins; not a full shape boundary certificate.
            outcome['boundary_violation'] |= any(not 0 <= b[0] <= scene.length_m or abs(b[1]) > scene.width_m/2 for b in r['body_positions'])
            prohibited = any(not (e['counterpart_type']=='ground' and e['robot_link'] in config['allowed_ground_contact_links']) for e in events)
            outcome['goal_reached'] = math.dist(p[:2], scene.goal[:2]) < .15
            settled = settled+args.dt if outcome['goal_reached'] and speed < .05 and spin < .1 else 0.0
            outcome['goal_settled'] = settled >= .5
            if outcome['fallen'] or outcome['boundary_violation'] or (prohibited and args.mode == 'policy-route') or outcome['goal_settled']:
                completed = True
                break
        else:
            outcome['timed_out'] = True  # execution budget, even when shorter than benchmark timeout
            completed = True
        if recorder.n >= 2:
            summary = recorder.finish(outcome, completed=completed)
            _json(output/'episode.json', summary)
            _json(output/'evaluation.json', evaluate_episode(summary, config))
            _json(output/'audit.json', audit_trace(output/'trace.jsonl', summary))
        else:
            recorder.abort()
    finally:
        recorder.abort()
        monitor.close()
    return output
