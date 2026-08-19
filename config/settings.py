import os
import json
from dataclasses import dataclass
import datetime
from urllib.parse import urlparse

from models.sim_context import SimContext
from services.farm_sync_service import FarmSyncService
from utils.logger import get_logger

logger = get_logger("config")


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
    api_base_url: str = ""

    def __post_init__(self) -> None:
        if not self.api_base_url:
            parsed = urlparse(self.api_url)
            self.api_base_url = f"{parsed.scheme}://{parsed.netloc}"


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


def load_sim_contexts_from_api(config: DaemonConfig, state_manager=None) -> list[SimContext]:
    sync_service = FarmSyncService(
        api_url=config.api_base_url,
        api_token=config.api_token,
        timeout=config.api_timeout
    )
    
    api_fields = sync_service.load_farm_fields(config.farm_id)
    
    if state_manager:
        local_field_ids = state_manager.get_all_field_ids()
        sync_result = sync_service.sync_fields(api_fields, local_field_ids)
        
        logger.info(
            "Field sync completed",
            new_fields=sync_result.new_fields,
            existing_fields=len(sync_result.existing_fields),
            inactive_fields=sync_result.inactive_fields
        )
    
    contexts = []
    for field in api_fields:
        contexts.append(SimContext(
            field_id=field.field_id,
            field_name=field.field_name,
            field_size=field.field_size,
            soil_type=field.soil_type,
            crop_type=config.crop_type,
            variety=config.variety,
            start_date=config.season_start_date,
            fuel_variation=config.fuel_variation,
        ))
    
    return contexts


def load_sim_contexts_from_json(config: DaemonConfig) -> list[SimContext]:
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


def load_sim_contexts(config: DaemonConfig, state_manager=None) -> list[SimContext]:
    if config.api_url and config.api_token:
        try:
            return load_sim_contexts_from_api(config, state_manager)
        except ValueError as e:
            logger.warning("API load failed, falling back to JSON", error=str(e))
    
    return load_sim_contexts_from_json(config)
