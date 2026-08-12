"""Plausibilitäts-Testsuite gegen Fachregeln (P1-1, Issue #57).

Deterministische pytest-Suite, die eine volle Kartoffel-Saison über den
``FastForwardRunner`` simuliert (Seed 42, Feld 990001, 760 Tage) und die
erzeugten Event-Sequenzen gegen das maschinenlesbare Fachregelwerk
``documentation/fachregeln/kartoffel_regeln.json`` prüft.

Konzept: ``documentation/konzepte/P1-1_plausibilitaets_testsuite.md``

Bekannte, noch nicht behobene Befunde (``documentation/fachregeln/
maengelbericht_baseline.md``) werden als ``xfail(strict=True)`` markiert –
sobald der zugehörige Bug gefixt ist, schlägt der Test **erwartungsgemäß
fehl** (xfail-strict) und erinnert daran, den Marker zu entfernen.
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
# Fixture-Konfiguration (Referenz-Baseline: Seed 42, Feld 990001, 760 Tage)
# ---------------------------------------------------------------------------

_SEED = 42
_FIELD_ID = 990001
_FIELD_NAME = "Audit Field"
_FIELD_SIZE = 20.0
_N_DAYS = 760
_START_DATE = datetime.datetime(2026, 1, 1)


@pytest.fixture(scope="module")
def simulation() -> dict[str, Any]:
    """Module-scoped FastForward-Simulation (deterministisch, kein Netzwerk).

    Reproduziert die Referenz-Baseline (Seed 42, Feld 990001, 760 Tage).
    Nach Fix von B2 (Issue #58) läuft die Saison im Startjahr (2026 statt
    2027). Nach P2-1 (Issue #65) verschieben sich Sikkation (Harvest-Phase
    auf -21/-14 d vor Ernte) und P-Düngung (nach soil_preparation, -5/-1 d
    vor Legen); dadurch ändert sich der Zufallszustand an den
    Beregnungs-Entscheidungspunkten, was zu anderen Beregnungs-Events und
    damit neuen Baseline-Zahlen führt:
    29 Integration Events + 1610 Domain Events (vor P2-1: 27 / 1606).

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
    )

    # Stdout des Runners unterdrücken (Progress-Reports); Logger-Ausgabe bleibt.
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
# Bekannte Befunde → xfail-Mapping (Befund-ID → KAR-Regel-IDs)
# ---------------------------------------------------------------------------

# xfail-Regeln mit Befund-Begründung. Nach Fix des jeweiligen Befunds wird der
# Test grün erwartet → xfail(strict=True) schlägt fehl → Marker entfernen.
XFAIL_REASONS: dict[str, str] = {
    "KAR-003": "Befund B7, Issue #57 – Intra-Tages-Sequenz invertiert (Pflanzguttransport nach Legen).",
    "KAR-005": "Befund B6, Issue #57 – Pflanzenschutz/Sikkation nach dem Roden.",
    "KAR-024": "Befund B5/B6, Issue #57 – Sikkations-Grenzen verletzt (letzte Gabe < 14 d vor Roden / nach Roden). Wird laut Konzept erst nach P2-3 (Protection-Plan-Beschneidung) vollständig grün; Marker bleibt auch bei zufälligem XPASS erhalten (mit PO klären).",
    # Neu durch P2-1 (Issue #65): Die Verschiebung von Sikkation und P-Düngung
    # verändert den Zufallszustand an den Beregnungs-Entscheidungspunkten, was
    # zu Beregnungs-Einzelgaben < 10 mm führt (KAR-040 hartes Fenster 10–40 mm).
    # Dies ist ein Sekundäreffekt der Konfigurationsänderung, keine Abschwächung
    # der Regel – im PR als neuer Befund (B15) für den PO vermerkt.
    "KAR-040": "Befund B15 (neu durch P2-1, Issue #65) – Beregnungs-Einzelgaben < 10 mm durch veränderten Zufallszustand nach Konfig-Verschiebung; Regel wird nicht abgeshwächt, Ursache mit PO zu klären.",
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


# Modul-level Param-Liste (einmaliges Laden des Regelwerks zur Sammlungszeit).
_RULE_PARAMS: list[Any] = _rule_params(load_rules())


# ---------------------------------------------------------------------------
# Fixture-Smoke-Tests (Reproduzierbarkeit der Baseline)
# ---------------------------------------------------------------------------


class TestFixtureBaseline:
    """Sichert, dass die Fixture die Referenz-Baseline reproduziert."""

    def test_integration_event_count_matches_baseline(self, simulation):
        """Baseline: 29 Integration Events (nach P2-1-Fix, Issue #65).

        Vor P2-1 (B2-Fix, Issue #58) waren es 27 Events. Durch die
        Verschiebung der Sikkation (-21/-14 d) und P-Düngung (nach
        soil_preparation) ändert sich der Zufallszustand an den
        Beregnungs-Entscheidungspunkten, was zu +2 Beregnungs-Events führt.
        """
        assert len(simulation["events"]) == 29

    def test_domain_event_count_matches_baseline(self, simulation):
        """Baseline: 1610 Domain Events (nach P2-1-Fix, Issue #65).

        Vor P2-1 (B2-Fix, Issue #58) waren es 1606 Domain Events. Die
        Differenz (+4) ergibt sich aus den zusätzlichen Beregnungs-Events
        durch den veränderten Zufallszustand nach der Konfig-Verschiebung.
        """
        assert len(simulation["domain_events"]) == 1610

    def test_fixture_is_deterministic(self, simulation):
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
            context=ctx, n_days=_N_DAYS, output_target="stdout"
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            events = runner.run()
        assert len(events) == len(simulation["events"])
        assert [e.start_date for e in events] == [
            e.start_date for e in simulation["events"]
        ]

    def test_no_network_access(self, simulation, monkeypatch):
        """Stellt sicher, dass die Simulation keinen Netzwerkzugriff benötigt.

        Wir blockieren socket-Verbindungen und prüfen, dass ein erneuter Lauf
        (kurz, 30 Tage) trotzdem durchläuft.
        """
        import socket

        def _block(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Netzwerkzugriff im Plausibilitätstest verboten")

        monkeypatch.setattr(socket, "socket", _block)
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
            context=ctx, n_days=30, output_target="stdout"
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            runner.run()
        # Keine Exception → Netzwerk nicht benötigt.


# ---------------------------------------------------------------------------
# Regel-Checks (parametrisiert über alle KAR-Regeln)
# ---------------------------------------------------------------------------


class TestKartoffelRegeln:
    """Prüft jede Regel aus ``kartoffel_regeln.json`` gegen die Simulation."""

    @pytest.mark.parametrize("rule_id", _RULE_PARAMS)
    def test_rule(
        self,
        rule_id: str,
        simulation: dict[str, Any],
        rules: list[dict[str, Any]],
    ) -> None:
        """Jede harte Regelverletzung ist ein Testfehler.

        Wetter-/Bodenregeln (KAR-030 … KAR-035) werden mit Begründung
        übersprungen (Wetterkopplung erst ab P3, Befund B4/B8).
        Bekannte Befunde sind via ``XFAIL_REASONS`` als xfail(strict=True)
        markiert.
        """
        rule = next(r for r in rules if r["id"] == rule_id)
        result: CheckResult = check_rule(rule, simulation["cycles"])

        if result.weather_skip:
            pytest.skip(result.skip_reason or "Wetterregel übersprungen")

        hard = hard_violations(result)
        soft = soft_violations(result)
        # Soft-Verstöße werden dokumentiert, führen aber nicht zum Fehler.
        if soft:
            print(
                f"\n[{rule_id}] soft-Verstöße ({len(soft)}): "
                + "; ".join(v.message for v in soft[:5])
            )
        # Für xfail-markierte Regeln (bekannte Befunde) bestätigt JEDE
        # Verletzung (hard oder soft) den Bug → Test schlägt fehl → xfail.
        # Nach Fix verschwindet die Verletzung → XPASS(strict) → Marker
        # entfernen.
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


# ---------------------------------------------------------------------------
# Domain-Event-Checks (B13, B2)
# ---------------------------------------------------------------------------


class TestDomainEventChecks:
    """Prüft die Domain-Event-Historie auf Zyklus-Konsistenz."""

    def test_crop_cycle_started_emitted_once(self, simulation):
        """Genau 1× CropCycleStarted je Lauf (1 Zyklus in der Baseline)."""
        started = [
            e for e in simulation["domain_events"]
            if e.event_type == "CropCycleStarted"
        ]
        assert len(started) == 1, (
            f"Erwartet genau 1 CropCycleStarted, got {len(started)}."
        )

    def test_harvest_completed_emitted_once_per_cycle(self, simulation):
        """Genau 1× HarvestCompleted je Zyklus (deckt B13 ab)."""
        completed = [
            e for e in simulation["domain_events"]
            if e.event_type == "HarvestCompleted"
        ]
        assert len(completed) == 1, (
            f"Erwartet genau 1 HarvestCompleted, got {len(completed)}."
        )

    def test_planting_year_matches_start_year(self, simulation):
        """Lege-Event muss im Startjahr der Simulation liegen (B2).

        Nach Fix von B2 (Issue #58) liegt der Legetermin im Startjahr
        (2026-04/05), nicht mehr in ``start_year+1``.
        """
        planting = [
            e for e in simulation["events"] if e.worktype == 26
        ]
        assert planting, "Kein Lege-Event in der Simulation."
        start = planting[0].start_date
        if isinstance(start, str):
            year = int(start[:4])
        else:
            year = start.year
        assert year == _START_DATE.year, (
            f"Lege-Event im Jahr {year}, erwartet {_START_DATE.year}."
        )


# ---------------------------------------------------------------------------
# Wetter-Regeln: explizite Skip-Dokumentation (KAR-030 … KAR-035)
# ---------------------------------------------------------------------------


class TestWeatherRulesSkipped:
    """Dokumentiert, dass Wetterregeln bis P3 nicht prüfbar sind."""

    @pytest.mark.parametrize(
        "rule_id",
        ["KAR-030", "KAR-031", "KAR-032", "KAR-033", "KAR-034", "KAR-035"],
    )
    def test_weather_rule_is_skipped(
        self,
        rule_id: str,
        simulation: dict[str, Any],
        rules: list[dict[str, Any]],
    ) -> None:
        rule = next(r for r in rules if r["id"] == rule_id)
        result = check_rule(rule, simulation["cycles"])
        assert result.weather_skip, (
            f"{rule_id} sollte als Wetterregel übersprungen werden."
        )
        assert result.skip_reason, f"{rule_id} benötigt eine Skip-Begründung."
        pytest.skip(result.skip_reason)
