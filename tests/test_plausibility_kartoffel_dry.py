"""Dry-Szenario-Plausibilitätssuite (MS5 P2-5 C, Issue #71).

Zweite, unabhängige Fixture ``dry_simulation`` mit synthetisch trockenem
Moisture-Verlauf, der Beregnungs-Events erzwingt. Damit werden die
Beregnungsregeln KAR-006/013/022/040/041 gegen **nicht-leere** Mengen
geprüft – die Baseline-Fixture (Seed 42, 760 d) enthält nach B2-Fix keine
Beregnungs-Events mehr.

Konzept: Issue #71 (Sub-Issue C von P2-5 Backlog-Sammelkonzept).

Die bestehende ``simulation``-Fixture (29/1613) bleibt unangetastet.
"""

from __future__ import annotations

import contextlib
import datetime
import io
import random
from typing import Any

import numpy as np
import pytest

from events.domain_event_bus import DomainEventBus
from models.sim_context import SimContext
from scheduler.fast_forward_runner import FastForwardRunner

from tests.plausibility.dry_moisture_stub import DryMoistureDataService
from tests.plausibility.rule_checks import (
    CheckResult,
    hard_violations,
    load_rules,
    normalize_events,
    segment_cycles,
    check_rule,
    soft_violations,
)

# ---------------------------------------------------------------------------
# Fixture-Konfiguration (analog Baseline, aber mit Dry-Moisture-Stub)
# ---------------------------------------------------------------------------

_SEED = 42
_FIELD_ID = 990001
_FIELD_NAME = "Audit Field"
_FIELD_SIZE = 20.0
_N_DAYS = 760
_START_DATE = datetime.datetime(2026, 1, 1)


@pytest.fixture(scope="module")
def dry_simulation() -> dict[str, Any]:
    """Module-scoped Dry-FF-Simulation (deterministisch, kein Netzwerk).

    Analog der Baseline-``simulation``-Fixture, aber mit einem
    ``DryMoistureDataService``-Stub, der synthetisch niedrige Bodenfeuchte
    (35 % nFK) über die Vegetationsperiode (Mai–Sep) liefert, sodass der
    ``IrrigationSimulator`` Beregnungs-Kandidaten erzeugt.

    Returns:
        Dict mit ``events`` (Integration Events), ``domain_events``,
        ``event_bus``, ``context`` und ``cycles`` (normalisierte Events je
        Anbauzyklus).
    """
    random.seed(_SEED)
    np.random.seed(_SEED)

    context = SimContext(
        field_size=_FIELD_SIZE,
        soil_type="sandy_loam",
        start_date=_START_DATE,
        crop_type="Potato",
        variety="Belana",
        field_id=_FIELD_ID,
        field_name=_FIELD_NAME,
        fuel_variation=0.1,
    )
    event_bus = DomainEventBus()
    runner = FastForwardRunner(
        context=context,
        n_days=_N_DAYS,
        output_target="stdout",
        event_bus=event_bus,
        moisture_service_factory=lambda: DryMoistureDataService(
            context=context
        ),
    )

    # Stdout des Runners unterdrücken (Progress-Reports).
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        events = runner.run()

    domain_events = event_bus.get_history()
    normalized = normalize_events(events)
    cycles = segment_cycles(normalized)

    return {
        "events": events,
        "domain_events": domain_events,
        "event_bus": event_bus,
        "context": context,
        "cycles": cycles,
        "normalized": normalized,
    }


@pytest.fixture(scope="module")
def rules() -> list[dict[str, Any]]:
    """Lade das Fachregelwerk einmal pro Modul."""
    return load_rules()


# ---------------------------------------------------------------------------
# xfail-Mapping für die Dry-Suite
# ---------------------------------------------------------------------------

# KAR-040: B3 (Gaben zu klein) – IrrigationSimulator berechnet Gabe =
# Defizit × Zufall, nicht Mindestgabe 20 mm. Im Dry-Szenario sind die
# Einzelgaben < 10 mm (hartes Fenster 10–40 mm). P3-Thema.
# KAR-024: B5/B6 – Quickdown-Abstand außerhalb [4,7] (derselbe Befund wie
# in der Baseline-Suite; im Dry-Szenario 66 d statt 69 d, gleiche Ursache).
XFAIL_REASONS: dict[str, str] = {
    "KAR-024": (
        "Befund B5/B6, Issue #57 – Quickdown-Abstand 66 d außerhalb [4,7] "
        "(im Dry-Szenario; gleiche Ursache wie Baseline-Suite, wo der "
        "Abstand 69 d beträgt)."
    ),
    "KAR-040": (
        "Befund B3 (P3) – Beregnungs-Einzelgaben < 10 mm: "
        "IrrigationSimulator berechnet Gabe = Defizit × Zufall, nicht "
        "Mindestgabe 20 mm. Dry-Szenario deckt die Struktur, nicht die "
        "Mengenfachlichkeit."
    ),
}


def _rule_params(rules: list[dict[str, Any]]) -> list[Any]:
    """Baue parametrize-Liste mit xfail-Marks für bekannte Befunde."""
    params: list[Any] = []
    for rule in rules:
        rid = rule["id"]
        marks = []
        if rid in XFAIL_REASONS:
            marks.append(pytest.mark.xfail(strict=True, reason=XFAIL_REASONS[rid]))
        params.append(pytest.param(rid, marks=marks, id=rid))
    return params


_RULE_PARAMS: list[Any] = _rule_params(load_rules())


# ---------------------------------------------------------------------------
# Stub-Unit-Tests (DryMoistureDataService)
# ---------------------------------------------------------------------------


class TestDryMoistureService:
    """Unit-Tests für den synthetischen Moisture-Stub."""

    def test_returns_full_year_dates(self) -> None:
        """Stub liefert für jedes Tag des Jahres ein Datum (365/366)."""
        ctx = SimContext(
            field_size=_FIELD_SIZE,
            soil_type="sandy_loam",
            start_date=_START_DATE,
            crop_type="Potato",
            variety="Belana",
            field_id=_FIELD_ID,
            field_name=_FIELD_NAME,
            fuel_variation=0.1,
        )
        stub = DryMoistureDataService(context=ctx)
        data = stub.get_moisture_data(year=2026, depth_range="0-10")
        dates = data["dates"]
        # 2026 ist kein Schaltjahr → 365 Tage.
        assert len(dates) == 365, f"Erwartet 365 Tage, got {len(dates)}."
        assert dates[0] == datetime.date(2026, 1, 1)
        assert dates[-1] == datetime.date(2026, 12, 31)

    def test_moisture_below_threshold_in_vegetation_period(self) -> None:
        """Mai–Sep: nFK < 50 % (unter Schwellwert → Beregnungs-Trigger).

        Der Stub liefert einen Sägezahn-Verlauf (45→30 % nFK), der
        durchgehend unter dem 50 %-Schwellwert bleibt.
        """
        ctx = SimContext(
            field_size=_FIELD_SIZE,
            soil_type="sandy_loam",
            start_date=_START_DATE,
            crop_type="Potato",
            variety="Belana",
            field_id=_FIELD_ID,
            field_name=_FIELD_NAME,
            fuel_variation=0.1,
        )
        stub = DryMoistureDataService(context=ctx)
        data = stub.get_moisture_data(year=2026, depth_range="0-10")
        moisture = data["moisture_data"]
        dates = data["dates"]
        for d, m in zip(dates, moisture):
            if 5 <= d.month <= 9:
                assert m < 50, (
                    f"{d}: nFK={m} >= 50 in Vegetationsperiode (Mai–Sep)."
                )

    def test_moisture_above_threshold_outside_vegetation_period(self) -> None:
        """Außerhalb Mai–Sep: nFK >= 50 % (kein Beregnungs-Trigger)."""
        ctx = SimContext(
            field_size=_FIELD_SIZE,
            soil_type="sandy_loam",
            start_date=_START_DATE,
            crop_type="Potato",
            variety="Belana",
            field_id=_FIELD_ID,
            field_name=_FIELD_NAME,
            fuel_variation=0.1,
        )
        stub = DryMoistureDataService(context=ctx)
        data = stub.get_moisture_data(year=2026, depth_range="0-10")
        moisture = data["moisture_data"]
        dates = data["dates"]
        for d, m in zip(dates, moisture):
            if d.month < 5 or d.month > 9:
                assert m >= 50, (
                    f"{d}: nFK={m} < 50 außerhalb Vegetationsperiode."
                )

    def test_deterministic_no_network(self) -> None:
        """Zwei Aufrufe lieerten identische Daten (kein Zufall, kein Netz)."""
        ctx = SimContext(
            field_size=_FIELD_SIZE,
            soil_type="sandy_loam",
            start_date=_START_DATE,
            crop_type="Potato",
            variety="Belana",
            field_id=_FIELD_ID,
            field_name=_FIELD_NAME,
            fuel_variation=0.1,
        )
        stub = DryMoistureDataService(context=ctx)
        d1 = stub.get_moisture_data(year=2026, depth_range="0-10")
        d2 = stub.get_moisture_data(year=2026, depth_range="0-10")
        assert list(d1["moisture_data"]) == list(d2["moisture_data"])
        assert d1["dates"] == d2["dates"]


# ---------------------------------------------------------------------------
# Dry-Fixture-Smoke-Tests
# ---------------------------------------------------------------------------


class TestDryFixture:
    """Sichert, dass die Dry-Fixture Beregnungs-Events erzeugt."""

    def test_dry_season_has_irrigation_events(self, dry_simulation) -> None:
        """AK 2: Dry-Saison enthält >= 1 Beregnungs-Event (wt=15)."""
        irrigation = [
            e for e in dry_simulation["events"] if e.worktype == 15
        ]
        assert len(irrigation) >= 1, (
            f"Erwartet >= 1 Beregnungs-Event, got {len(irrigation)}."
        )

    def test_irrigation_in_vegetation_period(self, dry_simulation) -> None:
        """AK 2: Beregnungs-Events liegen in der Vegetationsperiode (Mai–Sep)."""
        irrigation = [
            e for e in dry_simulation["events"] if e.worktype == 15
        ]
        assert irrigation, "Keine Beregnungs-Events zum Monats-Check."
        for ev in irrigation:
            start = ev.start_date
            if isinstance(start, str):
                month = int(start[5:7])
            else:
                month = start.month
            assert 5 <= month <= 9, (
                f"Beregnung außerhalb Mai–Sep: {start} (Monat {month})."
            )

    def test_dry_fixture_is_deterministic(self, dry_simulation) -> None:
        """Zweite Ausführung mit gleichem Seed liefert gleiche Event-Anzahl."""
        random.seed(_SEED)
        np.random.seed(_SEED)
        ctx = SimContext(
            field_size=_FIELD_SIZE,
            soil_type="sandy_loam",
            start_date=_START_DATE,
            crop_type="Potato",
            variety="Belana",
            field_id=_FIELD_ID,
            field_name=_FIELD_NAME,
            fuel_variation=0.1,
        )
        runner = FastForwardRunner(
            context=ctx,
            n_days=_N_DAYS,
            output_target="stdout",
            moisture_service_factory=lambda: DryMoistureDataService(
                context=ctx
            ),
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            events = runner.run()
        assert len(events) == len(dry_simulation["events"]), (
            f"Nicht deterministisch: {len(events)} vs "
            f"{len(dry_simulation['events'])} Events."
        )
        assert [e.start_date for e in events] == [
            e.start_date for e in dry_simulation["events"]
        ]


# ---------------------------------------------------------------------------
# Regel-Checks (parametrisiert über alle KAR-Regeln gegen die Dry-Saison)
# ---------------------------------------------------------------------------


class TestKartoffelRegelnDry:
    """Prüft jede Regel aus ``kartoffel_regeln.json`` gegen die Dry-Saison."""

    @pytest.mark.parametrize("rule_id", _RULE_PARAMS)
    def test_rule(
        self,
        rule_id: str,
        dry_simulation: dict[str, Any],
        rules: list[dict[str, Any]],
    ) -> None:
        """Jede harte Regelverletzung ist ein Testfehler (gegen Dry-Saison).

        Wetter-/Bodenregeln (KAR-030 … KAR-035) werden übersprungen.
        KAR-040 ist xfail (B3 – Gaben zu klein, P3).
        """
        rule = next(r for r in rules if r["id"] == rule_id)
        result: CheckResult = check_rule(rule, dry_simulation["cycles"])

        if result.weather_skip:
            pytest.skip(result.skip_reason or "Wetterregel übersprungen")

        hard = hard_violations(result)
        soft = soft_violations(result)
        if soft:
            print(
                f"\n[{rule_id}] soft-Verstöße ({len(soft)}): "
                + "; ".join(v.message for v in soft[:5])
            )
        if rule_id in XFAIL_REASONS:
            assert not result.violations, (
                f"{rule_id}: {len(result.violations)} Verletzung(en) – "
                + "; ".join(v.message for v in result.violations)
            )
        else:
            assert hard == [], (
                f"{rule_id}: {len(hard)} harte Verletzung(en) – "
                + "; ".join(v.message for v in hard)
            )
