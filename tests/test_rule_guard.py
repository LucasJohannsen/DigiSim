"""Tests für die RuleGuard-Komponente (MS5 P2-4, Issue #68).

Parametrisierte Unit-Tests je ``check_type`` der Guard-Regeln
(``no_worktype_after_harvest``, ``min_gap_before_harvest_op``,
``no_siccation_after_harvest``). Der Guard ist ein datengetriebenes
Sicherheitsnetz – Regeln werden aus ``config/decision_guards_potato.json``
geladen, nicht hartcodiert.
"""
from __future__ import annotations

import datetime

import pytest

from scheduler.decision_manager import CycleContext, RuleGuard
from scheduler.guard_rule_loader import GuardRuleLoader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockOperation:
    """Minimal Mock für eine Operation mit worktype/application_category."""

    def __init__(
        self,
        worktype: int,
        application_category: int | None = None,
        name: str = "MockOp",
    ) -> None:
        self.worktype = worktype
        self.application_category = application_category
        self.worktype_text = name
        self.operation = name


def _ctx(
    harvest_completed: bool = False,
    last_siccation_date: datetime.datetime | None = None,
    siccation_count: int = 0,
    planting_date: datetime.datetime | None = None,
    harvest_date: datetime.datetime | None = None,
    last_harvest_op_date: datetime.datetime | None = None,
) -> CycleContext:
    return CycleContext(
        planting_date=planting_date,
        harvest_date=harvest_date,
        harvest_completed=harvest_completed,
        last_siccation_date=last_siccation_date,
        siccation_count_this_cycle=siccation_count,
        last_harvest_op_date=last_harvest_op_date,
    )


@pytest.fixture
def guard() -> RuleGuard:
    """Lädt den RuleGuard aus der Produktions-Konfiguration."""
    return GuardRuleLoader.load_default()


# ---------------------------------------------------------------------------
# Konfig-/Loader-Tests
# ---------------------------------------------------------------------------


class TestGuardRuleLoader:
    """Guard-Regeln werden aus config/decision_guards_potato.json geladen."""

    def test_loads_seven_guard_rules(self, guard: RuleGuard) -> None:
        """Genau 7 Guard-Regeln (3 bestehend + 4 Wetter-Guards ab P3-2).

        Bestehend: KAR-005, KAR-020, KAR-024.
        Neu (P3-2, Issue #80): KAR-030, KAR-031, KAR-032, KAR-035.
        """
        rule_ids = [r.rule_id for r in guard.rules]
        assert "KAR-005" in rule_ids
        assert "KAR-020" in rule_ids
        assert "KAR-024" in rule_ids
        assert "KAR-030" in rule_ids
        assert "KAR-031" in rule_ids
        assert "KAR-032" in rule_ids
        assert "KAR-035" in rule_ids
        assert len(guard.rules) == 7

    def test_fail_open_on_missing_file(self, tmp_path) -> None:
        """Nicht ladbare Konfig → Guard deaktiviert (leere Regel-Liste)."""
        loader = GuardRuleLoader(config_path=str(tmp_path / "nonexistent.json"))
        guard = loader.load()
        assert guard.rules == []

    def test_fail_open_on_invalid_json(self, tmp_path) -> None:
        """Kaputte JSON-Datei → Guard deaktiviert (leere Regel-Liste)."""
        bad = tmp_path / "bad.json"
        bad.write_text("{ invalid json", encoding="utf-8")
        loader = GuardRuleLoader(config_path=str(bad))
        guard = loader.load()
        assert guard.rules == []


# ---------------------------------------------------------------------------
# KAR-005: no_worktype_after_harvest
# ---------------------------------------------------------------------------


class TestKAR005NoWorktypeAfterHarvest:
    """KAR-005: Keine Bestandesmaßnahme nach Roden (harvest_completed=True)."""

    @pytest.mark.parametrize("wt", [13, 14, 15, 23, 29])
    def test_rejects_worktype_after_harvest(
        self, guard: RuleGuard, wt: int
    ) -> None:
        """harvest_completed=True → wt ∈ {13,14,15,23,29} wird abgelehnt."""
        op = MockOperation(worktype=wt)
        ctx = _ctx(harvest_completed=True)
        reason = guard.check(op, ctx, datetime.datetime(2027, 8, 1))
        assert reason is not None
        assert reason.startswith("KAR-005:")

    @pytest.mark.parametrize("wt", [13, 14, 15, 23, 29])
    def test_passes_worktype_before_harvest(
        self, guard: RuleGuard, wt: int
    ) -> None:
        """harvest_completed=False → wt ∈ {13,14,15,23,29} wird durchgelassen."""
        op = MockOperation(worktype=wt)
        ctx = _ctx(harvest_completed=False)
        reason = guard.check(op, ctx, datetime.datetime(2027, 6, 1))
        assert reason is None

    def test_passes_other_worktype_after_harvest(
        self, guard: RuleGuard
    ) -> None:
        """harvest_completed=True, wt=27 (Roden) → nicht durch KAR-005 abgelehnt."""
        op = MockOperation(worktype=27)
        ctx = _ctx(harvest_completed=True)
        reason = guard.check(op, ctx, datetime.datetime(2027, 8, 1))
        # KAR-005 prüft nur worktypes [13,14,15,23,29], nicht wt=27
        assert reason is None or not reason.startswith("KAR-005:")


# ---------------------------------------------------------------------------
# KAR-020: min_gap_before_harvest_op (Sikkation → Roden ≥ 14 d)
# ---------------------------------------------------------------------------


class TestKAR020MinGapBeforeHarvestOp:
    """KAR-020: Roden ≥ 14 d nach letzter Sikkation."""

    def test_rejects_roden_within_14_days(self, guard: RuleGuard) -> None:
        """last_siccation=2027-08-05, date=2027-08-10, wt=27 → 5 d < 14 d → reject."""
        op = MockOperation(worktype=27)
        ctx = _ctx(
            harvest_completed=False,
            last_siccation_date=datetime.datetime(2027, 8, 5),
        )
        reason = guard.check(op, ctx, datetime.datetime(2027, 8, 10))
        assert reason is not None
        assert reason.startswith("KAR-020:")

    def test_passes_roden_after_14_days(self, guard: RuleGuard) -> None:
        """last_siccation=2027-08-05, date=2027-08-20, wt=27 → 15 d ≥ 14 d → pass."""
        op = MockOperation(worktype=27)
        ctx = _ctx(
            harvest_completed=False,
            last_siccation_date=datetime.datetime(2027, 8, 5),
        )
        reason = guard.check(op, ctx, datetime.datetime(2027, 8, 20))
        assert reason is None

    def test_passes_roden_without_siccation(self, guard: RuleGuard) -> None:
        """Keine Sikkation im Zyklus → wt=27 wird durchgelassen."""
        op = MockOperation(worktype=27)
        ctx = _ctx(harvest_completed=False, last_siccation_date=None)
        reason = guard.check(op, ctx, datetime.datetime(2027, 8, 20))
        assert reason is None

    def test_passes_non_roden_within_14_days(self, guard: RuleGuard) -> None:
        """wt=14 (nicht Roden) innerhalb 14 d → nicht durch KAR-020 abgelehnt."""
        op = MockOperation(worktype=14, application_category=26)
        ctx = _ctx(
            harvest_completed=False,
            last_siccation_date=datetime.datetime(2027, 8, 5),
        )
        reason = guard.check(op, ctx, datetime.datetime(2027, 8, 10))
        assert reason is None or not reason.startswith("KAR-020:")

    def test_rejects_exactly_13_days(self, guard: RuleGuard) -> None:
        """Grenzwert: 13 d < 14 d → reject."""
        op = MockOperation(worktype=27)
        ctx = _ctx(
            harvest_completed=False,
            last_siccation_date=datetime.datetime(2027, 8, 5),
        )
        reason = guard.check(op, ctx, datetime.datetime(2027, 8, 18))
        assert reason is not None
        assert reason.startswith("KAR-020:")

    def test_passes_exactly_14_days(self, guard: RuleGuard) -> None:
        """Grenzwert: 14 d ≥ 14 d → pass."""
        op = MockOperation(worktype=27)
        ctx = _ctx(
            harvest_completed=False,
            last_siccation_date=datetime.datetime(2027, 8, 5),
        )
        reason = guard.check(op, ctx, datetime.datetime(2027, 8, 19))
        assert reason is None


# ---------------------------------------------------------------------------
# KAR-024: no_siccation_after_harvest
# ---------------------------------------------------------------------------


class TestKAR024NoSiccationAfterHarvest:
    """KAR-024: Keine Sikkation (wt=14, Kat. 26) nach Roden."""

    def test_rejects_sikkation_after_harvest(self, guard: RuleGuard) -> None:
        """harvest_completed=True, wt=14, Kat.26 → reject."""
        op = MockOperation(worktype=14, application_category=26)
        ctx = _ctx(harvest_completed=True)
        reason = guard.check(op, ctx, datetime.datetime(2027, 9, 1))
        assert reason is not None
        assert reason.startswith("KAR-024:")

    def test_passes_sikkation_before_harvest(self, guard: RuleGuard) -> None:
        """harvest_completed=False, wt=14, Kat.26 → pass."""
        op = MockOperation(worktype=14, application_category=26)
        ctx = _ctx(harvest_completed=False)
        reason = guard.check(op, ctx, datetime.datetime(2027, 7, 1))
        assert reason is None

    def test_passes_fungicide_after_harvest_via_kar024(
        self, guard: RuleGuard
    ) -> None:
        """harvest_completed=True, wt=14, Kat.27 (Fungizid) → nicht durch
        KAR-024 abgelehnt (nur Kat. 26). Aber KAR-005 lehnt wt=14 ab."""
        op = MockOperation(worktype=14, application_category=27)
        ctx = _ctx(harvest_completed=True)
        reason = guard.check(op, ctx, datetime.datetime(2027, 9, 1))
        # KAR-024 prüft nur Kat. 26; KAR-005 lehnt wt=14 generell ab
        assert reason is not None
        assert reason.startswith("KAR-005:")

    def test_passes_non_sikkation_after_harvest(
        self, guard: RuleGuard
    ) -> None:
        """harvest_completed=True, wt=27 (Roden), Kat.26 → nicht durch KAR-024."""
        op = MockOperation(worktype=27, application_category=26)
        ctx = _ctx(harvest_completed=True)
        reason = guard.check(op, ctx, datetime.datetime(2027, 9, 1))
        assert reason is None or not reason.startswith("KAR-024:")


# ---------------------------------------------------------------------------
# Guard deaktiviert bei cycle_context=None
# ---------------------------------------------------------------------------


class TestGuardDisabledWithoutCycleContext:
    """Guard deaktiviert, wenn cycle_context=None (Abwärtskompatibilität)."""

    def test_check_returns_none_when_context_none(self, guard: RuleGuard) -> None:
        """cycle_context=None → check() immer None (Guard deaktiviert)."""
        op = MockOperation(worktype=14, application_category=26)
        reason = guard.check(op, None, datetime.datetime(2027, 9, 1))
        assert reason is None


# ---------------------------------------------------------------------------
# RuleGuard ohne Regeln (fail-open)
# ---------------------------------------------------------------------------


class TestRuleGuardEmpty:
    """Leerer Guard (fail-open) lehnt nichts ab."""

    def test_empty_guard_passes_everything(self) -> None:
        guard = RuleGuard(rules=[])
        op = MockOperation(worktype=14, application_category=26)
        ctx = _ctx(harvest_completed=True)
        reason = guard.check(op, ctx, datetime.datetime(2027, 9, 1))
        assert reason is None
