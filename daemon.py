import argparse
import contextlib
import datetime
import io
import signal
import sys

from dotenv import load_dotenv

from config.settings import DaemonConfig, load_and_validate_config, load_sim_contexts
from scheduler.fast_forward_runner import FastForwardRunner
from scheduler.tick_scheduler import TickScheduler
from services.data_transfer_service import DataTransferService
from services.digizert_client import DigiZertClient
from services.digizert_data_client import DigiZertDataClient
from services.isip_pressure_service import ISIPPressureService
from services.moisture_service import MoistureDataService
from services.providers.dwd_weather_provider import DWDWeatherDataProvider
from services.retry_dispatcher import RetryDispatcher
from services.weather_service import WeatherDataService
from utils.logger import get_logger, setup_logging
from utils.state_manager import StateManager


def _transfer_field_data(
    data_client: DigiZertDataClient,
    transfer_service: DataTransferService,
    field_id: int,
    start_date: datetime.date,
    end_date: datetime.date,
    year: int,
) -> None:
    """Überträgt WeatherData + SoilMoistureData für ein Feld an DigiZert.

    Wird im Bootstrap (ganze Saison) und im Daily-Mode (aktueller Tag) aufgerufen.
    Sensoren werden idempotent angelegt, Daten als Bulk gesendet.
    """
    logger = get_logger("data_transfer")

    # 1. Sensoren anlegen (idempotent)
    data_client.ensure_weather_sensor(field_id)
    data_client.ensure_soil_moisture_sensor(field_id, depth=15)
    data_client.ensure_soil_moisture_sensor(field_id, depth=30)

    # 2. WeatherData senden
    weather_measurements = transfer_service.collect_weather_measurements(
        start_date=start_date,
        end_date=end_date,
    )
    if weather_measurements:
        data_client.send_weather_data(field_id, weather_measurements)
        logger.info(
            "WeatherData transferred",
            field_id=field_id,
            n=len(weather_measurements),
        )

    # 3. SoilMoistureData senden (15cm + 30cm)
    soil_data = transfer_service.collect_soil_moisture_measurements(
        start_date=start_date,
        end_date=end_date,
        year=year,
    )
    for depth, measurements in soil_data.items():
        if measurements:
            data_client.send_soil_moisture_data(field_id, depth, measurements)
            logger.info(
                "SoilMoistureData transferred",
                field_id=field_id,
                depth=depth,
                n=len(measurements),
            )


def _run_bootstrap(
    config: DaemonConfig,
    state_manager: StateManager,
    dispatcher: RetryDispatcher | None,
    data_client: DigiZertDataClient | None = None,
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
        # P4: ISIP-Service pro Feld (für Bootstrap-Modus)
        isip_svc = (
            ISIPPressureService(
                api_base_url=config.data_api_base_url,
                api_token=config.api_token,
                field_id=ctx.field_id,
                timeout=config.api_timeout,
                enabled=config.isip_pressure_gating_enabled,
            )
            if config.isip_pressure_gating_enabled
            else None
        )
        # ISIP-Saison-Daten prefetchen (Batch-Modus)
        if isip_svc and isip_svc.enabled:
            isip_svc.fetch_season(season_start, today)

        runner = FastForwardRunner(
            context=ctx,
            n_days=n_days,
            output_target="stdout",
            isip_service=isip_svc,
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

        # S2/S3: WeatherData + SoilMoistureData transfer (Feature-Flag)
        if data_client and data_client.enabled:
            weather_svc = WeatherDataService(
                context=ctx,
                provider=DWDWeatherDataProvider(),
            )
            moisture_svc = MoistureDataService(context=ctx)
            transfer_svc = DataTransferService(
                weather_service=weather_svc,
                moisture_service=moisture_svc,
            )
            _transfer_field_data(
                data_client=data_client,
                transfer_service=transfer_svc,
                field_id=ctx.field_id,
                start_date=season_start,
                end_date=today,
                year=season_start.year,
            )

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

    # S2/S3: Data-Transfer-Client (D3/D4 – Feature-Flag, default off)
    data_client = DigiZertDataClient(
        api_base_url=config.data_api_base_url,
        api_token=config.api_token,
        timeout=config.api_timeout,
        enabled=config.data_transfer_enabled,
    )
    if data_client.enabled:
        logger.info("Data transfer enabled (D3/D4)")

    # P4: ISIP-Druck-Gating – Factory erstellt pro Feld einen ISIPService
    isip_enabled = config.isip_pressure_gating_enabled
    if isip_enabled:
        logger.info("ISIP pressure gating enabled")

    def _isip_service_factory(ctx) -> ISIPPressureService | None:
        if not isip_enabled:
            return None
        return ISIPPressureService(
            api_base_url=config.data_api_base_url,
            api_token=config.api_token,
            field_id=ctx.field_id,
            timeout=config.api_timeout,
            enabled=True,
        )

    if bootstrap:
        _run_bootstrap(config, state_manager, dispatcher, data_client)
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
        isip_service_factory=_isip_service_factory,
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
