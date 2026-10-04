"""Isaac/PhysX contact-report adapter; requires a running Kit application.

API references are in docs/ISAACLAB.md. Callback coverage is not a calibration.
"""
from __future__ import annotations
from qct.contacts import ContactClassifier


class PhysxContacts:
    def __init__(self, stage, classifier: ContactClassifier):
        from pxr import UsdPhysics, PhysxSchema
        from omni.physx import get_physx_simulation_interface
        self.classifier = classifier
        self.events, self.unknown = [], []
        self.complete = True
        self.inventory = []
        for prim in stage.Traverse():
            if prim.HasAPI(UsdPhysics.RigidBodyAPI):
                path = str(prim.GetPath())
                self.inventory.append(path)
                PhysxSchema.PhysxContactReportAPI.Apply(prim).CreatePhysxContactReportThresholdAttr().Set(0.0)
        if not any(p.startswith(classifier.robot_prefix+'/') for p in self.inventory):
            raise RuntimeError('No robot rigid bodies found; contact instrumentation unavailable')
        self.subscription = get_physx_simulation_interface().subscribe_contact_report_events(self._callback)

    def _callback(self, headers, data):
        from pxr import PhysicsSchemaTools
        from omni.physx.bindings._physx import ContactEventType
        try:
            for header in headers:
                if header.type == ContactEventType.CONTACT_LOST:
                    continue
                paths = [str(PhysicsSchemaTools.intToSdfPath(getattr(header, k)))
                         for k in ('actor0','actor1','collider0','collider1')]
                event, classified = self.classifier.classify(*paths)
                self.complete &= classified
                if not classified:
                    self.unknown.append(dict(zip(('actor0','actor1','collider0','collider1'), paths)))
                if event is not None:
                    contacts = []
                    for i in range(header.contact_data_offset, header.contact_data_offset+header.num_contact_data):
                        item = data[i]
                        contacts.append(dict(position=list(item.position), normal=list(item.normal),
                                             impulse=list(item.impulse), separation=float(item.separation)))
                    event['points'] = contacts
                    event['event_type'] = str(header.type)
                    self.events.append(event)
        except Exception as exc:
            # Exceptions raised inside Kit callbacks must not silently disappear.
            self.complete = False
            self.unknown.append({'callback_error': repr(exc)})

    def drain(self):
        events, unknown, complete = self.events, self.unknown, self.complete
        self.events, self.unknown, self.complete = [], [], True
        return events, unknown, complete

    def close(self):
        self.subscription = None
