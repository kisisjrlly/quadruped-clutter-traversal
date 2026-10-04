"""Append-only physics-step evidence and conversion to the existing v0.1 evaluator.

The recorder refuses to certify uncalibrated contact instrumentation. Raw traces
and summaries are separate artifacts. Never call reset before finish().
"""
from __future__ import annotations
import hashlib
import json
import math
import tempfile
from pathlib import Path
from .geometry import quat_angle_deg, rotate
from .scene import Scene, canonical_bytes, digest, finite, vector


class EpisodeRecorder:
    def __init__(self, path: str | Path, scene: Scene, config: dict, *, episode_id: str,
                 method_id: str, observation_mode: str, physics_dt: float,
                 provenance: dict | None = None, contact_calibration_id: str | None = None):
        if observation_mode not in ("oracle","onboard"):
            raise ValueError("A simulation recorder must declare its observation mode")
        if finite(physics_dt,"physics_dt",minimum=0) == 0:
            raise ValueError("physics_dt must be positive")
        if not episode_id or not method_id:
            raise ValueError("Missing episode/method ID")
        self.path, self.scene, self.config = Path(path),scene,dict(config)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream = self.path.open("xb")
        self.hash = hashlib.sha256()
        self.episode_id, self.method_id, self.mode = episode_id,method_id,observation_mode
        self.dt, self.calibration = physics_dt,contact_calibration_id
        self.provenance = dict(provenance or {})
        self.n, self.last_t, self.closed = 0,None,False
        self.contacts, self.initial, self.maxima = [],{},{}
        self.contact_complete, self.object_complete = True,True
        self.discontinuity = False
        self._write({"record":"header","schema_version":"qct.trace.v1","episode_id":episode_id,
                     "method_id":method_id,"data_kind":"simulation","observation_mode":observation_mode,
                     "scene":scene.to_dict(),"scene_sha256":scene.sha256,"benchmark":config,
                     "physics_dt":physics_dt,"contact_calibration_id":contact_calibration_id,
                     "provenance":self.provenance})

    def _write(self,value):
        data = canonical_bytes(value)+b"\n"
        self.stream.write(data)
        self.stream.flush()
        self.hash.update(data)

    def frame(self,time_s:float,robot:dict,objects:dict,contacts:list[dict],*,contact_coverage:bool,
              reset_detected:bool=False) -> None:
        if self.closed:
            raise ValueError("Episode already finalized")
        finite(time_s,"time",minimum=0)
        if type(contact_coverage) is not bool or type(reset_detected) is not bool:
            raise ValueError("Coverage/reset flags must be booleans")
        if self.last_t is not None and time_s <= self.last_t:
            raise ValueError("Nonmonotonic physics timestamps")
        if self.last_t is None:
            if abs(time_s) > 1e-9:
                self.discontinuity = True
        elif abs(time_s-self.last_t-self.dt) > max(1e-8,self.dt*1e-3):
            self.discontinuity = True
        if reset_detected:
            self.discontinuity = True
        expected = {o.object_id for o in self.scene.obstacles}
        if set(objects)-expected:
            raise ValueError("Unknown object in trace")
        self.object_complete &= set(objects) == expected
        self.contact_complete &= contact_coverage
        clean_objects = {}
        for oid,pose in objects.items():
            p = vector(pose["position"],3,"object position")
            q = vector(pose["quaternion_wxyz"],4,"object quaternion")
            rotate(q,(0,0,1))
            clean_objects[oid] = {"position":p,"quaternion_wxyz":q}
            if oid not in self.initial:
                # A late first observation is not the true initial pose.
                if self.n != 0:
                    self.object_complete = False
                self.initial[oid] = (p,q)
                self.maxima[oid] = {"object_id":oid,"max_translation_m":0.0,"max_rotation_deg":0.0,"toppled":False}
            p0,q0 = self.initial[oid]
            m = self.maxima[oid]
            m["max_translation_m"] = max(m["max_translation_m"],math.dist(p,p0))
            m["max_rotation_deg"] = max(m["max_rotation_deg"],quat_angle_deg(q,q0))
            m["toppled"] |= rotate(q,(0,0,1))[2] < math.cos(math.radians(45))
        robot_pos = vector(robot["position"],3,"robot position")
        robot_quat = vector(robot["quaternion_wxyz"],4,"robot quaternion")
        rotate(robot_quat,(0,0,1))
        clean_contacts = []
        for event in contacts:
            counterpart = event["counterpart_type"]
            if counterpart not in ("ground","obstacle","wall","self") or not event["robot_link"]:
                raise ValueError("Unclassified contact")
            if counterpart == "obstacle" and event["counterpart_id"] not in expected:
                raise ValueError("Contact with undeclared object")
            item = dict(event)
            item["time_s"] = time_s
            clean_contacts.append(item)
        self.contacts.extend(clean_contacts)
        self._write({"record":"frame","index":self.n,"time_s":time_s,
                     "robot":dict(robot,position=robot_pos,quaternion_wxyz=robot_quat),
                     "objects":clean_objects,"contacts":clean_contacts,
                     "contact_coverage":contact_coverage,"reset_detected":reset_detected})
        self.n += 1
        self.last_t = time_s

    def finish(self,outcome:dict,*,completed:bool=True) -> dict:
        if self.closed or self.n < 2 or self.last_t is None or self.last_t <= 0:
            raise ValueError("Cannot finalize an empty/already closed episode")
        required = ("goal_reached","goal_settled","fallen","emergency_stop","manual_intervention",
                    "boundary_violation","prohibited_airborne","obstacle_supported","timed_out")
        if set(outcome) != set(required) or any(type(v) is not bool for v in outcome.values()) or type(completed) is not bool:
            raise ValueError("Outcome must explicitly contain all boolean flags")
        self._write({"record":"terminal","time_s":self.last_t,"outcome":outcome,"completed":completed})
        self.stream.close()
        self.closed = True
        provenance = {k:self.provenance.get(k) for k in ("git_commit","geometry_sha256","policy_sha256")}
        provenance.update(config_sha256=digest(self.config),scene_sha256=self.scene.sha256,evidence_sha256=self.hash.hexdigest())
        return {"schema_version":"qct.episode.v0.1","task_version":self.config["task_version"],
                "episode_id":self.episode_id,"scene_id":self.scene.sha256,"method_id":self.method_id,
                "seed":self.scene.seed,"data_kind":"simulation","observation_mode":self.mode,
                "scene_feasibility":"unknown","duration_s":self.last_t,
                "expected_object_ids":[o.object_id for o in self.scene.obstacles],
                "integrity":{"episode_complete":completed and not self.discontinuity,
                             "contact_monitor_complete":self.contact_complete and bool(self.calibration) and not self.discontinuity,
                             "object_tracking_complete":self.object_complete and not self.discontinuity},
                "outcome":outcome,"contacts":self.contacts,"objects":list(self.maxima.values()),"provenance":provenance}

    def abort(self) -> None:
        """Leave an incomplete raw trace, never fabricate a terminal success."""
        if not self.closed:
            self.stream.close()
            self.closed = True


def empty_outcome() -> dict:
    return {k:False for k in ("goal_reached","goal_settled","fallen","emergency_stop","manual_intervention",
                             "boundary_violation","prohibited_airborne","obstacle_supported","timed_out")}


def audit_trace(path:str | Path, summary:dict) -> dict:
    """Recompute summary from trace, check hash/order/time. Not sensor calibration.

    Uses the same recorder reduction, so this is a consistency audit, not an
    independent proof of the reduction's scientific validity.
    """
    errors, frames, header, terminal, last = [], 0, None, None, None
    hasher = hashlib.sha256()
    replay = None
    with tempfile.TemporaryDirectory() as tmp:
        try:
            with Path(path).open("rb") as stream:
                for raw in stream:
                    hasher.update(raw)
                    row = json.loads(raw)
                    if not isinstance(row, dict):
                        raise ValueError("record_is_not_object")
                    kind = row.get("record")
                    if kind == "header" and header is None and frames == 0:
                        header = row
                        scene = Scene.from_dict(row["scene"])
                        if scene.sha256 != row["scene_sha256"]:
                            errors.append("scene_hash_mismatch")
                        replay = EpisodeRecorder(Path(tmp)/"replay.jsonl", scene, row["benchmark"],
                            episode_id=row["episode_id"], method_id=row["method_id"],
                            observation_mode=row["observation_mode"], physics_dt=row["physics_dt"],
                            provenance=row["provenance"], contact_calibration_id=row["contact_calibration_id"])
                    elif kind == "frame" and replay is not None and terminal is None:
                        if row["index"] != frames:
                            errors.append("frame_index_mismatch")
                        replay.frame(row["time_s"], row["robot"], row["objects"], row["contacts"],
                                     contact_coverage=row["contact_coverage"], reset_detected=row["reset_detected"])
                        frames += 1
                        last = row["time_s"]
                    elif kind == "terminal" and replay is not None and terminal is None:
                        terminal = row
                    else:
                        errors.append("record_order")
            if replay is None or terminal is None or frames < 2:
                errors.append("incomplete_trace")
            else:
                rebuilt = replay.finish(terminal["outcome"], completed=terminal["completed"])
                if terminal["time_s"] != last:
                    errors.append("terminal_time_mismatch")
                # Evidence hash is checked against actual input bytes separately.
                expected, provided = json.loads(json.dumps(rebuilt)), json.loads(json.dumps(summary))
                expected["provenance"].pop("evidence_sha256", None)
                provided["provenance"].pop("evidence_sha256", None)
                if expected != provided:
                    errors.append("summary_reduction_mismatch")
                if replay.discontinuity:
                    errors.append("frame_discontinuity_or_reset")
        except (ValueError, KeyError, TypeError, OSError, UnicodeError) as exc:
            errors.append("invalid_trace_or_summary:"+str(exc))
        finally:
            if replay is not None:
                replay.abort()
    if hasher.hexdigest() != summary.get("provenance", {}).get("evidence_sha256"):
        errors.append("evidence_hash_mismatch")
    return {"structural_audit_passed":not errors,"frames":frames,"errors":sorted(set(errors)),
            "sensor_calibration_verified":False,
            "warning":"Structural consistency cannot prove contacts were physically detected."}
