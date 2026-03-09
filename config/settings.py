import os
import json
from dataclasses import dataclass
from pathlib import Path
import datetime

from models.sim_context import SimContext


@dataclass
class DaemonConfig:
    """Validierte Konfiguration für den Daemon-Start."""
    api_url: str
    api_token: str
    farm_id: int
    api_timeout: int
    retry_max_attempts: int
    retry_queue_dir: str
    tick_time: str
    state_dir: str
    log_level: str
    log_file: str | None
    crop_type: str
    variety: str
    season_start_date: datetime.datetime
    fuel_variation: float
    farms_config_path: str
    max_concurrent_fields: int


def load_and_validate_config() -> DaemonConfig:
    """
    Lädt und validiert alle Env-Vars.
    Wirft ValueError mit klarer Nachricht bei fehlenden Pflichtfeldern.
    """
    missing = []
    required = ["DIGIZERT_API_URL", "DIGIZERT_API_TOKEN", "FARM_ID"]
    for key in required:
        if not os.environ.get(key):
            missing.append(key)
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return DaemonConfig(
        api_url=os.environ["DIGIZERT_API_URL"],
        api_token=os.environ["DIGIZERT_API_TOKEN"],
        farm_id=int(os.environ["FARM_ID"]),
        api_timeout=int(os.getenv("API_TIMEOUT_SECONDS", "10")),
        retry_max_attempts=int(os.getenv("RETRY_MAX_ATTEMPTS", "3")),
        retry_queue_dir=os.getenv("RETRY_QUEUE_DIR", "./retry_queue"),
        tick_time=os.getenv("TICK_TIME", "06:00"),
        state_dir=os.getenv("STATE_DIR", "./state"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_file=os.getenv("LOG_FILE"),
        crop_type=os.getenv("CROP_TYPE", "Potato"),
        variety=os.getenv("VARIETY", "Belana"),
        season_start_date=datetime.datetime.fromisoformat(
            os.getenv("SEASON_START_DATE", str(datetime.datetime.now().replace(month=10, day=1).date()))
        ),
        fuel_variation=float(os.getenv("FUEL_VARIATION", "0.1")),
        farms_config_path=os.getenv("FARMS_CONFIG_PATH", "./config/farms.json"),
        max_concurrent_fields=int(os.getenv("MAX_CONCURRENT_FIELDS", "10")),
    )


def load_sim_contexts(config: DaemonConfig) -> list[SimContext]:
    """
    Liest farms.json, findet den Betrieb mit config.farm_id,
    und gibt eine Liste von SimContext-Objekten zurück (ein pro Feld).
    Wirft ValueError wenn farm_id nicht gefunden.
    """

    with open(config.farms_config_path, "r") as f:
        data = json.load(f)

    farm = next((f for f in data["farms"] if f["id"] == config.farm_id), None)
    if farm is None:
        raise ValueError(f"Farm ID {config.farm_id} not found in {config.farms_config_path}")

    contexts = []
    for field in farm["fields"]:
        contexts.append(SimContext(
            field_id=field["id"],
            field_name=field["name"],
            field_size=field["area"],
            soil_type=field["soil_type"],
            crop_type=config.crop_type,
            variety=config.variety,
            start_date=config.season_start_date,
            fuel_variation=config.fuel_variation,
        ))
    return contexts
