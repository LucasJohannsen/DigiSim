import json
import datetime

from models.planting_plan import FieldOperationEvent
from models.sim_context import SimContext

class EventLogger:
    def __init__(self):
        self.events = []

    def log(self, event: FieldOperationEvent):

        # add hardcoded values

        if not event.machine:
            event.machine = "Fendt 719 Vario"
        
        event.exa_id = 0
        event.field = 0
        event.batch = None

        # anfügen
        self.events.append(event)

    def save(self, filepath, context:SimContext=None):

        data = {
            "field": {
                "exa_id": context.field_id,
                "name": context.field_name,
                "area": context.field_size,
            },
            "harvest_cycle": 
            {
                "id": 0,
                "start_date": "",
                "end_date": "",
            },
            "operations": []
        }

        for event in self.events:
            op = {
                "model": "pipeline.operation",
                "pk": 0,
                "fields": {
                    "batch": event.batch,
                    "field": context.field_id if context else 0,
                    "worktype": event.worktype,
                    "exa_id": event.exa_id,
                    "start_date": event.start_date,
                    "end_date": event.end_date,
                    "machine": event.machine,
                    "area": event.area,
                    "distance": event.distance,
                    "distanceWorked": event.distanceWorked,
                    "duration": event.duration,
                    "durationWorked": event.durationWorked,
                    "fuel": event.fuel,
                    "application_type": event.application_type,
                    "application_category": event.application_category,
                    "application_name": event.application_name,
                    "application_amount": event.application_amount,
                    "application_unit": event.application_unit,
                    "worktype_text": event.worktype_text
                }
            }
            data["operations"].append(op)


        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

class LogEvent:
    def __init__(self, details=None, event_type=None):
        self.details = details or {}
        self.event_type = event_type
