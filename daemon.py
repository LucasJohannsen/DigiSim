import argparse
import contextlib
import datetime
import io
import signal
import sys
from dotenv import load_dotenv

from config.settings import DaemonConfig, load_and_validate_config, load_sim_contexts
from scheduler.fast_forward_runner import FastForwardRunner
from services.digizert_client import DigiZertClient
from services.retry_dispatcher import RetryDispatcher
from scheduler.tick_scheduler import TickScheduler
from utils.logger import get_logger, setup_logging
from utils.state_manager import StateManager


def _run_bootstrap(
    config: DaemonConfig,
    state_manager: StateManager,
    dispatcher: RetryDispatcher | None,
) -> None:
    """Fast-Forward Bootstrap: simuliere von SEASON_START_DATE bis heute.

    Lädt die Contexte ohne State-Restore (frischer Start), führt für jedes
    Feld einen ``FastForwardRunner`` aus und sendet die generierten Events an
    die DigiZert API. Anschliessend wird der finale State pro Feld
    persistiert, damit der Daily-Mode nahtlos anknüpfen kann.
    """
    logger = get_logger("daemon")

    today = datetime.date.today()
    season_start = config.season_start_date
    if isinstance(season_start, datetime.datetime):
        season_start = season_start.date()

    n_days = (today - season_start).days

    if n_days <= 0:
        logger.info(
            "Bootstrap skipped – season start is today or in the future",
            season_start=str(season_start),
            today=str(today),
        )
        return

    logger.info(
        "Starting bootstrap",
        n_days=n_days,
        season_start=str(season_start),
        today=str(today),
    )

    # Contexte OHNE State-Restore laden (frischer Start).
    contexts = load_sim_contexts(config, state_manager=None)

    total_events = 0
    for ctx in contexts:
        runner = FastForwardRunner(
            context=ctx,
            n_days=n_days,
            output_target="stdout",
        )

        # Stdout vom FastForwardRunner unterdrücken (Beeinträchtigt Logs nicht).
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            events = runner.run()

        # Events an DigiZert API senden.
        if dispatcher:
            for event in events:
                dispatcher.send_event(event, ctx)

        # State speichern – der FastForwardRunner haelt den finalen Runner.
        state_manager.save(runner.calendar_runner, today)

        total_events += len(events)
        logger.info(
            "Bootstrap field completed",
            field_id=ctx.field_id,
            field_name=ctx.field_name,
            n_days=n_days,
            events=len(events),
        )

    # Retry-Queue verarbeiten (z. B. fehlgeschlagene Sendungen).
    if dispatcher:
        dispatcher.process_queue()

    logger.info(
        "Bootstrap completed",
        field_count=len(contexts),
        total_events=total_events,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="DigiSim daemon")
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Fast-Forward bis heute, dann daily mode",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Fast-Forward bis heute, dann exit",
    )
    args = parser.parse_args()

    bootstrap = args.bootstrap or args.bootstrap_only
    bootstrap_only = args.bootstrap_only

    load_dotenv()

    try:
        config = load_and_validate_config()
    except ValueError as e:
        print(f"[STARTUP ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    setup_logging(log_level=config.log_level, log_file=config.log_file)
    logger = get_logger("daemon")
    logger.info("DigiSim daemon starting", farm_id=config.farm_id)

    state_manager = StateManager(config.state_dir)

    client = DigiZertClient(
        api_url=config.api_url,
        api_token=config.api_token,
        timeout=config.api_timeout,
    )
    dispatcher = RetryDispatcher(
        client,
        max_attempts=config.retry_max_attempts,
        queue_dir=config.retry_queue_dir,
    )
    dispatcher.process_queue()

    if bootstrap:
        _run_bootstrap(config, state_manager, dispatcher)
        if bootstrap_only:
            logger.info("Bootstrap completed, exiting (--bootstrap-only)")
            return

    # Normaler daily mode – Contexte MIT State-Restore laden.
    try:
        contexts = load_sim_contexts(config, state_manager)
    except (ValueError, FileNotFoundError) as e:
        logger.error("Failed to load farm configuration", error=str(e))
        sys.exit(1)

    logger.info("Farm configuration loaded", farm_id=config.farm_id, field_count=len(contexts))

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
