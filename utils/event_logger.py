import json
import datetime

from models.planting_plan import FieldOperationEvent

class EventLogger:
    def __init__(self):
        self.events = []

    def log(self, event: FieldOperationEvent):

        # add hardcoded values
        event.machine = "Fendt 719 Vario"
        event.application_amount = 0
        event.application_unit = ""
        event.application_type = ""
        event.application_category = ""
        event.application_name = ""

        event.exa_id = 0
        event.field = 0
        event.batch = None

        # anfügen
        self.events.append(event)

    def save(self, filepath):

        data = {
            "field": 0,
            "harvest_cycle": 0,
            "operations": []
        }

        for event in self.events:
            op = {
                "model": "pipeline.operation",
                "pk": 0,
                "fields": {
                    "batch": getattr(event, "batch", None),
                    "field": getattr(event, "field", None),
                    "worktype": getattr(event, "worktype", None),
                    "exa_id": getattr(event, "exa_id", None),
                    "start_date": getattr(event, "start_date", None),
                    "end_date": getattr(event, "end_date", None),
                    "machine": getattr(event, "machine", None),
                    "area": getattr(event, "area", None),
                    "distance": getattr(event, "distance", None),
                    "distanceWorked": getattr(event, "distanceWorked", None),
                    "duration": getattr(event, "duration", None),
                    "durationWorked": getattr(event, "durationWorked", None),
                    "fuel": getattr(event, "fuel", None),
                    "application_type": getattr(event, "application_type", None),
                    "application_category": getattr(event, "application_category", None),
                    "application_name": getattr(event, "application_name", None),
                    "application_amount": getattr(event, "application_amount", None),
                    "application_unit": getattr(event, "application_unit", None),
                    "worktype_text": getattr(event, "worktype_text", None)
                }
            }
            data["operations"].append(op)


        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

class LogEvent:
    def __init__(self, details=None, event_type=None):
        self.details = details or {}
        self.event_type = event_type
