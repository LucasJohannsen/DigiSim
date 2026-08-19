import httpx
from models.planting_plan import FieldOperationEvent
from models.sim_context import SimContext
from utils.logger import get_logger

logger = get_logger("digizert_client")


class DigiZertClient:
    def __init__(
        self,
        api_url: str,
        api_token: str,
        timeout: int = 10
    ) -> None:
        self.api_url = api_url
        self.api_token = api_token
        self.timeout = timeout

    def send_event(self, event: FieldOperationEvent, context: SimContext) -> None:
        payload = self._build_payload(event, context)
        headers = {
            "Authorization": f"Token {self.api_token}",
            "Content-Type": "application/json"
        }
        
        response = httpx.post(
            self.api_url,
            json=payload,
            headers=headers,
            timeout=self.timeout
        )
        response.raise_for_status()
        logger.info("Event dispatched", field=event.field, worktype=event.worktype)

    def _build_payload(self, event: FieldOperationEvent, context: SimContext) -> dict:
        return {
            "model": "pipeline.operation",
            "pk": 0,
            "fields": {
                "field": event.field,
                "worktype": event.worktype,
                "start_date": event.start_date,
                "end_date": event.end_date,
                "area": event.area,
                "fuel": event.fuel,
                "worktype_text": event.worktype_text,
                "application_type": event.application_type,
                "application_category": event.application_category,
                "application_name": event.application_name,
                "application_amount": event.application_amount,
                "application_unit": event.application_unit,
            }
        }
