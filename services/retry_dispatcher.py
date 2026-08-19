import datetime
import json
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from models.planting_plan import FieldOperationEvent
from models.sim_context import SimContext
from services.digizert_client import DigiZertClient
from utils.logger import get_logger

logger = get_logger("retry_dispatcher")


class RetryDispatcher:
    def __init__(
        self, client: DigiZertClient, max_attempts: int, queue_dir: str, _wait_strategy=None
    ) -> None:
        self.client = client
        self.max_attempts = max_attempts
        self.queue_dir = Path(queue_dir)
        self._wait = _wait_strategy or wait_exponential(multiplier=1, min=1, max=10)

    def send_event(self, event: FieldOperationEvent, context: SimContext) -> None:
        try:
            self._send_with_retry(event, context)
        except Exception as e:
            logger.error("All retry attempts failed", max_attempts=self.max_attempts, error=str(e))
            self._save_to_queue(event, context)

    def _send_with_retry(self, event: FieldOperationEvent, context: SimContext) -> None:
        def _log_retry(retry_state):
            exception = retry_state.outcome.exception()
            wait_time = self._wait(retry_state)
            logger.warning(
                "Retry attempt",
                attempt=retry_state.attempt_number,
                max_attempts=self.max_attempts,
                error=str(exception),
                wait_time=wait_time,
            )

        @retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=self._wait,
            reraise=True,
            before_sleep=_log_retry,
        )
        def _attempt():
            self.client.send_event(event, context)

        _attempt()

    def process_queue(self) -> None:
        if not self.queue_dir.exists():
            return

        for queue_file in self.queue_dir.rglob("*.json"):
            try:
                with open(queue_file) as f:
                    data = json.load(f)

                event = self._deserialize_event(data["event"])
                context = self._deserialize_context(data["context"])

                try:
                    self._send_with_retry(event, context)
                    queue_file.unlink()
                    logger.info("Queued event resent", queue_file=str(queue_file))
                except Exception as e:
                    logger.error(
                        "Failed to resend queued event", queue_file=str(queue_file), error=str(e)
                    )
            except Exception as e:
                logger.error(
                    "Failed to process queue file", queue_file=str(queue_file), error=str(e)
                )

    def _save_to_queue(self, event: FieldOperationEvent, context: SimContext) -> None:
        field_dir = self.queue_dir / str(context.field_id)
        field_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H%M%S")
        queue_file = field_dir / f"{timestamp}.json"

        queue_data = {
            "field_id": context.field_id,
            "failed_at": datetime.datetime.now().isoformat(),
            "event": self._serialize_event(event),
            "context": self._serialize_context(context),
        }

        with open(queue_file, "w") as f:
            json.dump(queue_data, f, indent=2)

        logger.info("Event queued", queue_file=str(queue_file))

    def _serialize_event(self, event: FieldOperationEvent) -> dict:
        return {
            "field": event.field,
            "worktype": event.worktype,
            "exa_id": event.exa_id,
            "start_date": event.start_date,
            "end_date": event.end_date,
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
            "worktype_text": event.worktype_text,
            "machine": event.machine,
        }

    def _serialize_context(self, context: SimContext) -> dict:
        return {
            "field_size": context.field_size,
            "soil_type": context.soil_type,
            "start_date": context.start_date.isoformat()
            if isinstance(context.start_date, datetime.datetime)
            else context.start_date,
            "crop_type": context.crop_type,
            "variety": context.variety,
            "field_id": context.field_id,
            "field_name": context.field_name,
            "fuel_variation": context.fuel_variation,
        }

    def _deserialize_event(self, data: dict) -> FieldOperationEvent:
        return FieldOperationEvent(
            field=data.get("field"),
            worktype=data.get("worktype"),
            exa_id=data.get("exa_id"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            area=data.get("area"),
            distance=data.get("distance"),
            distanceWorked=data.get("distanceWorked"),
            duration=data.get("duration"),
            durationWorked=data.get("durationWorked"),
            fuel=data.get("fuel"),
            application_type=data.get("application_type"),
            application_category=data.get("application_category"),
            application_name=data.get("application_name"),
            application_amount=data.get("application_amount"),
            application_unit=data.get("application_unit"),
            worktype_text=data.get("worktype_text"),
            machine=data.get("machine"),
        )

    def _deserialize_context(self, data: dict) -> SimContext:
        start_date = data.get("start_date")
        if isinstance(start_date, str):
            start_date = datetime.datetime.fromisoformat(start_date)

        return SimContext(
            field_size=data.get("field_size"),
            soil_type=data.get("soil_type"),
            start_date=start_date,
            crop_type=data.get("crop_type"),
            variety=data.get("variety"),
            field_id=data.get("field_id"),
            field_name=data.get("field_name"),
            fuel_variation=data.get("fuel_variation"),
        )
