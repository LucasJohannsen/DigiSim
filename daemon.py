import signal
import sys
from dotenv import load_dotenv

from config.settings import load_and_validate_config, load_sim_contexts
from utils.logger import setup_logging, get_logger
from utils.state_manager import StateManager
from services.digizert_client import DigiZertClient
from services.retry_dispatcher import RetryDispatcher
from services.farm_sync_service import FarmSyncService
from scheduler.tick_scheduler import TickScheduler


def main() -> None:
    load_dotenv()

    try:
        config = load_and_validate_config()
    except ValueError as e:
        print(f"[STARTUP ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    setup_logging(log_level=config.log_level, log_file=config.log_file)
    logger = get_logger("daemon")
    logger.info("DigiSim daemon starting", farm_id=config.farm_id)

    try:
        contexts = load_sim_contexts(config)
    except (ValueError, FileNotFoundError) as e:
        logger.error("Failed to load farm configuration", error=str(e))
        sys.exit(1)

    logger.info("Farm configuration loaded", farm_id=config.farm_id, field_count=len(contexts))

    state_manager = StateManager(config.state_dir)
    local_field_ids = state_manager.get_all_field_ids()
    
    sync_service = FarmSyncService(config.api_url, config.api_token, config.api_timeout)
    try:
        api_fields = sync_service.load_farm_fields(config.farm_id)
        sync_result = sync_service.sync_fields(api_fields, local_field_ids)
        
        logger.info(
            "Field sync completed",
            new_fields=sync_result.new_fields,
            existing_fields=len(sync_result.existing_fields),
            inactive_fields=sync_result.inactive_fields
        )
        
        active_field_ids = {f.field_id for f in api_fields}
        contexts = [ctx for ctx in contexts if ctx.field_id in active_field_ids]
        
        logger.info("Active fields filtered", active_count=len(contexts))
    except ValueError as e:
        logger.warning("Field sync failed, using all loaded contexts", error=str(e))

    client = DigiZertClient(
        api_url=config.api_url,
        api_token=config.api_token,
        timeout=config.api_timeout,
    )
    dispatcher = RetryDispatcher(
        client,
        max_attempts=config.retry_max_attempts,
        queue_dir=config.retry_queue_dir
    )
    dispatcher.process_queue()

    scheduler = TickScheduler(
        contexts=contexts,
        tick_time=config.tick_time,
        state_dir=config.state_dir,
        event_dispatcher=dispatcher,
        max_concurrent_fields=config.max_concurrent_fields,
    )

    def _shutdown(signum, frame):
        logger.info("Shutdown signal received", signal=signum)
        scheduler.stop()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    logger.info("DigiSim daemon started", tick_time=config.tick_time)
    scheduler.start()
    logger.info("DigiSim daemon stopped")


if __name__ == "__main__":
    main()
