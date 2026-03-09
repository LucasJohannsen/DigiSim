import signal
import sys
from dotenv import load_dotenv

from utils.config_loader import load_and_validate_config, load_sim_contexts
from utils.logger import setup_logging, get_logger
from services.digizert_client import DigiZertClient
from services.retry_dispatcher import RetryDispatcher
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

    client = DigiZertClient(
        api_url=config.api_url,
        api_token=config.api_token,
        timeout=config.api_timeout,
    )
    dispatcher = RetryDispatcher(client, max_attempts=config.retry_max_attempts)
    dispatcher.process_queue()

    scheduler = TickScheduler(
        contexts=contexts,
        tick_time=config.tick_time,
        state_dir=config.state_dir,
        event_dispatcher=dispatcher,
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
