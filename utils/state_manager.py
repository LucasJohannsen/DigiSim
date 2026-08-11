import datetime
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from models.sim_context import SimContext

if TYPE_CHECKING:
    from scheduler.calendar_driven_runner import CalendarDrivenRunner


@dataclass
class FieldStateSnapshot:
    field_id: int
    last_tick_date: datetime.date | None
    context: SimContext
    planting_ops: list[dict]
    protection_ops: list[dict]
    irrigation_state: dict | None = None  # Contains: irrigation, updated_moisture arrays
    crop_cycle_state: str | None = None  # scheduled / running / completed


class StateManager:
    def __init__(self, state_dir: str = "./state") -> None:
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, runner: "CalendarDrivenRunner", tick_date: datetime.date | None = None) -> None:
        snapshot = runner.get_state_snapshot(last_tick_date=tick_date)
        
        state_file = self.state_dir / f"field_{snapshot.field_id}.json"
        
        data = {
            "field_id": snapshot.field_id,
            "last_tick_date": snapshot.last_tick_date.isoformat() if snapshot.last_tick_date else None,
            "context": {
                "field_id": snapshot.context.field_id,
                "field_name": snapshot.context.field_name,
                "field_size": snapshot.context.field_size,
                "soil_type": snapshot.context.soil_type,
                "start_date": snapshot.context.start_date.isoformat(),
                "crop_type": snapshot.context.crop_type,
                "variety": snapshot.context.variety,
                "fuel_variation": snapshot.context.fuel_variation
            },
            "planting_operations": snapshot.planting_ops,
            "protection_operations": snapshot.protection_ops,
            "irrigation_state": snapshot.irrigation_state,
            "crop_cycle_state": snapshot.crop_cycle_state
        }
        
        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self, field_id: int) -> FieldStateSnapshot | None:
        state_file = self.state_dir / f"field_{field_id}.json"
        
        if not state_file.exists():
            return None
        
        with open(state_file, 'r') as f:
            data = json.load(f)
        
        context_data = data["context"]
        context = SimContext(
            field_id=context_data["field_id"],
            field_name=context_data["field_name"],
            field_size=context_data["field_size"],
            soil_type=context_data.get("soil_type", "sand"),
            start_date=datetime.datetime.fromisoformat(context_data["start_date"]),
            crop_type=context_data["crop_type"],
            variety=context_data["variety"],
            fuel_variation=context_data.get("fuel_variation", 0.1)
        )
        
        last_tick_date = None
        if data.get("last_tick_date"):
            last_tick_date = datetime.date.fromisoformat(data["last_tick_date"])
        
        return FieldStateSnapshot(
            field_id=data["field_id"],
            last_tick_date=last_tick_date,
            context=context,
            planting_ops=data.get("planting_operations", []),
            protection_ops=data.get("protection_operations", []),
            irrigation_state=data.get("irrigation_state"),
            crop_cycle_state=data.get("crop_cycle_state")
        )
    
    def get_all_field_ids(self) -> list[int]:
        state_files = Path(self.state_dir).glob("field_*.json")
        field_ids = []
        for file in state_files:
            try:
                field_id = int(file.stem.replace("field_", ""))
                field_ids.append(field_id)
            except ValueError:
                continue
        return field_ids
