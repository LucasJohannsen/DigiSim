"""Tests für resolve_planting_year / get_random_planting_date (P1-2, Issue #58).

Befund B2: ``PlantingPlanService.initialize_planting_plan()`` plante den
Legetermin immer in ``start_date.year + 1``. Diese Tests sichern die neue
Terminlogik, die den Legetermin im frühestmöglichen erreichbaren Pflanzfenster
plant (Startjahr, sofern Vorlauf und Fenster es zulassen; sonst Folgejahr).

Pflanzfenster Kartoffel: April–Mai (Monate 4–5).
"""

from __future__ import annotations

import contextlib
import datetime
import io
import random

import numpy as np
import pytest

from events.domain_event_bus import DomainEventBus
from models.sim_context import SimContext
from scheduler.fast_forward_runner import FastForwardRunner
from utils import sim_helper

# Pflanzfenster Kartoffel (April–Mai), wie in config/planting_plan_potato.json
_PLANTING_MONTHS = (4, 5)
# Lead-Time aus dem Potato-Plan: max(|min_days_to_target|) der soil_preparation
# Ops = max(27, 22, 14, 5) = 27.
_LEAD_TIME_DAYS = 27


# ---------------------------------------------------------------------------
# resolve_planting_year – parametrisierte Unit-Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "start_date, lead_time_days, expected_year",
    [
        # a) Start 01.01. → Startjahr (Legen Apr/Mai desselben Jahres)
        (
            datetime.datetime(2026, 1, 1),
            _LEAD_TIME_DAYS,
            2026,
        ),
        # b) Start 01.04. (im Fenster) → Startjahr, sofern Fenster reicht
        #    earliest = 01.04. + 27 d = 28.04. ≤ 31.05. → Startjahr
        (
            datetime.datetime(2026, 4, 1),
            _LEAD_TIME_DAYS,
            2026,
        ),
        # c) Start 15.06. (nach Fensterende) → Folgejahr
        (
            datetime.datetime(2026, 6, 15),
            _LEAD_TIME_DAYS,
            2027,
        ),
        # d) Grenzfall: earliest liegt exakt am Fensterende (31.05.)
        #    04.05. + 27 d = 31.05. → noch Startjahr (≤)
        (
            datetime.datetime(2026, 5, 4),
            _LEAD_TIME_DAYS,
            2026,
        ),
        # d2) Grenzfall: earliest liegt 1 Tag nach Fensterende → Folgejahr
        (
            datetime.datetime(2026, 5, 5),
            _LEAD_TIME_DAYS,
            2027,
        ),
        # Start tief im Vorjahr (Nov) → Folgejahr, da Fenster im Startjahr
        # bereits vergangen ist (earliest 28.11. > 31.05.)
        (
            datetime.datetime(2025, 11, 1),
            _LEAD_TIME_DAYS,
            2026,
        ),
    ],
    ids=[
        "start_jan_1_start_year",
        "start_apr_1_in_window_start_year",
        "start_jun_15_after_window_next_year",
        "boundary_earliest_equals_window_end_start_year",
        "boundary_earliest_one_day_after_window_next_year",
        "start_late_prev_year_next_year",
    ],
)
def test_resolve_planting_year(
    start_date: datetime.datetime,
    lead_time_days: int,
    expected_year: int,
) -> None:
    """resolve_planting_year wählt das korrekte Pflanzjahr."""
    assert (
        sim_helper.resolve_planting_year(start_date, _PLANTING_MONTHS, lead_time_days)
        == expected_year
    )


# ---------------------------------------------------------------------------
# get_random_planting_date – Fenster- und Vorlauf-Constraints
# ---------------------------------------------------------------------------


def test_get_random_planting_date_in_start_year() -> None:
    """Start 01.01. → Legetermin im April/Mai des Startjahres."""
    random.seed(42)
    np.random.seed(42)
    start = datetime.datetime(2026, 1, 1)
    planting_date = sim_helper.get_random_planting_date(start, _PLANTING_MONTHS, _LEAD_TIME_DAYS)
    assert planting_date.year == 2026
    assert planting_date.month in (4, 5)


def test_get_random_planting_date_respects_lead_time() -> None:
    """Legetermin ≥ start_date + lead_time_days (Start im Fenster)."""
    random.seed(42)
    np.random.seed(42)
    start = datetime.datetime(2026, 4, 1)
    planting_date = sim_helper.get_random_planting_date(start, _PLANTING_MONTHS, _LEAD_TIME_DAYS)
    earliest = start + datetime.timedelta(days=_LEAD_TIME_DAYS)
    assert planting_date >= earliest, (
        f"Legetermin {planting_date.date()} vor earliest {earliest.date()}."
    )
    assert planting_date.year == 2026


def test_get_random_planting_date_after_window_next_year() -> None:
    """Start 15.06. → Legetermin im Folgejahr."""
    random.seed(42)
    np.random.seed(42)
    start = datetime.datetime(2026, 6, 15)
    planting_date = sim_helper.get_random_planting_date(start, _PLANTING_MONTHS, _LEAD_TIME_DAYS)
    assert planting_date.year == 2027
    assert planting_date.month in (4, 5)


def test_get_random_planting_date_boundary_window_end() -> None:
    """Grenzfall: earliest = Fensterende → Legetermin = Fensterende möglich."""
    random.seed(0)
    np.random.seed(0)
    # 04.05. + 27 d = 31.05. → Fenster schrumpft auf 31.05.
    start = datetime.datetime(2026, 5, 4)
    for _ in range(50):
        planting_date = sim_helper.get_random_planting_date(
            start, _PLANTING_MONTHS, _LEAD_TIME_DAYS
        )
        earliest = start + datetime.timedelta(days=_LEAD_TIME_DAYS)
        assert planting_date >= earliest
        assert planting_date.year == 2026
        assert planting_date.month in (4, 5)


# ---------------------------------------------------------------------------
# Integrationstest: 365-Tage-FF-Lauf ab 01.01.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ff_365_run() -> dict:
    """365-Tage FastForward-Lauf ab 01.01.2026 (Seed 42, Feld 990001)."""
    random.seed(42)
    np.random.seed(42)
    context = SimContext(
        field_size=20.0,
        soil_type="sandy_loam",
        start_date=datetime.datetime(2026, 1, 1),
        crop_type="Potato",
        variety="Belana",
        field_id=990001,
        field_name="Audit Field",
        fuel_variation=0.1,
    )
    event_bus = DomainEventBus()
    runner = FastForwardRunner(
        context=context,
        n_days=365,
        output_target="stdout",
        event_bus=event_bus,
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        events = runner.run()
    return {
        "events": events,
        "domain_events": event_bus.get_history(),
        "context": context,
        "planned_planting_date": runner.calendar_runner.planting_plan_service.planned_planting_date,
    }


def test_ff_365_produces_events(ff_365_run: dict) -> None:
    """Akzeptanzkriterium 1: > 0 Events im 365-Tage-Lauf ab 01.01."""
    assert len(ff_365_run["events"]) > 0, (
        "365-Tage-Lauf ab 01.01. erzeugte keine Events (Befund B2 nicht behoben)."
    )


def test_ff_365_planting_in_start_year(ff_365_run: dict) -> None:
    """Akzeptanzkriterium 1: Legen im Apr/Mai des Startjahres (2026)."""
    planting = [e for e in ff_365_run["events"] if e.worktype == 26]
    assert planting, "Kein Lege-Event (wt=26) im 365-Tage-Lauf."
    start_str = planting[0].start_date
    year = int(start_str[:4]) if isinstance(start_str, str) else start_str.year
    month = int(start_str[5:7]) if isinstance(start_str, str) else start_str.month
    assert year == 2026, f"Lege-Event im Jahr {year}, erwartet 2026."
    assert month in (4, 5), f"Lege-Event im Monat {month}, erwartet Apr/Mai."


def test_ff_365_harvest_in_start_year(ff_365_run: dict) -> None:
    """Akzeptanzkriterium 1: Roden im selben Jahr (2026)."""
    harvest = [e for e in ff_365_run["events"] if e.worktype == 27]
    assert harvest, "Kein Rode-Event (wt=27) im 365-Tage-Lauf."
    start_str = harvest[0].start_date
    year = int(start_str[:4]) if isinstance(start_str, str) else start_str.year
    assert year == 2026, f"Rode-Event im Jahr {year}, erwartet 2026."


def test_ff_365_crop_cycle_scheduled_emitted_once(ff_365_run: dict) -> None:
    """Akzeptanzkriterium 4: CropCycleScheduled genau 1× mit korrektem Payload."""
    scheduled = [e for e in ff_365_run["domain_events"] if e.event_type == "CropCycleScheduled"]
    assert len(scheduled) == 1, f"Erwartet genau 1 CropCycleScheduled, got {len(scheduled)}."
    payload = scheduled[0].payload
    assert "planned_planting_date" in payload
    planned_str = payload["planned_planting_date"]
    planned_year = int(planned_str[:4])
    assert planned_year == 2026, f"planned_planting_date Jahr {planned_year}, erwartet 2026."
    planned_month = int(planned_str[5:7])
    assert planned_month in (4, 5), (
        f"planned_planting_date Monat {planned_month}, erwartet Apr/Mai."
    )


def test_ff_365_scheduled_matches_planned_planting_date(ff_365_run: dict) -> None:
    """CropCycleScheduled.payload['planned_planting_date'] == planned_planting_date."""
    scheduled = next(e for e in ff_365_run["domain_events"] if e.event_type == "CropCycleScheduled")
    planned = ff_365_run["planned_planting_date"]
    assert scheduled.payload["planned_planting_date"].startswith(planned.date().isoformat())
