"""Tests für Issue #65 (P2-1): Harvest-Phase & P-Grunddüngung Konfiguration.

Verifies the config-only fix for Befunde B5 (Sikkation→Roden < 14 d) and
B14 (P-Grunddüngung nach dem Legen) in ``config/planting_plan_potato.json``.

Konzept: ``documentation/konzepte/P2-1_harvest_phase_und_p_duengung_konfig.md``

Akzeptanzkriterien (Issue #65):
1. FF-Lauf: ``Datum(wt=27) − Datum(letzte Sikkation wt=14 Kat.26) ≥ 14 d`` (KAR-020)
2. Sikkation aus Harvest-Phase im Fenster 14–35 Tage vor dem Roden (KAR-020 weich)
3. P-Düngung (wt=23, Kat. 34, Superphosphat) liegt **vor** dem Lege-Event (wt=26)
4. Kali-Düngung bleibt vor dem Legen (Regression)
5. N-Düngung (Kat. 33) bleibt 0–35 Tage nach dem Legen (Regression, KAR-016)
6. xfail-Marker KAR-016 entfernt → grün (in ``test_plausibility_kartoffel.py``)
7. xfail-Marker KAR-020 entfernt → grün (in ``test_plausibility_kartoffel.py``)
8. Fixture-Baseline aktualisiert (in ``test_plausibility_kartoffel.py``)

Zusätzlich (Testhinweise Issue #65):
- PlantingPlanLoader lädt die korrigierte Konfig: P-Düngung in ``soil_preparation``,
  nicht in ``crop_management``; Harvest-Phase Herbizid-Offsets ``-21/-14``.
"""

from __future__ import annotations

import contextlib
import datetime
import io
import random
from typing import Any

import numpy as np
import pytest

from models.planting_plan import FieldOperationPhases
from models.sim_context import SimContext
from scheduler.fast_forward_runner import FastForwardRunner
from services.planting_plan_loader import PlantingPlanLoader

# ---------------------------------------------------------------------------
# Konfigurations-Checks (rein statisch, kein Simulationslauf)
# ---------------------------------------------------------------------------

_P_NAME = "Superphosphat"
_P_OP_NAME = "P Düngung"


def _load_plan() -> Any:
    loader = PlantingPlanLoader(crop_type="Potato", variety="Belana")
    return loader.get_planting_plan()


def _phase_ops(plan: Any, phase: FieldOperationPhases) -> list[Any]:
    phase_obj = next(
        (p for p in plan.phases if p.phase_name == phase.value), None
    )
    assert phase_obj is not None, f"Phase '{phase.value}' fehlt im Plan."
    return phase_obj.operations


class TestPlantingPlanConfig:
    """Statische Prüfungen der korrigierten ``planting_plan_potato.json``."""

    def test_p_duengung_in_soil_preparation(self) -> None:
        """B14-Fix: P-Düngung (Superphosphat) ist in Phase ``soil_preparation``."""
        plan = _load_plan()
        soil_ops = _phase_ops(plan, FieldOperationPhases.SOIL_PREPARATION)
        p_ops = [op for op in soil_ops if op.application_name == _P_NAME]
        assert p_ops, (
            "P-Düngung (Superphosphat) fehlt in soil_preparation (B14 nicht gefixt)."
        )
        assert len(p_ops) == 1, (
            f"Erwartet genau 1 P-Düngung in soil_preparation, got {len(p_ops)}."
        )
        p = p_ops[0]
        assert p.worktype == 23
        assert int(p.application_category) == 34
        assert p.min_days_to_target == -5
        assert p.max_days_to_target == -1
        assert p.application_amount == 0.5
        assert int(p.application_unit) == 2  # kg (DataUnit pk=2)

    def test_p_duengung_not_in_crop_management(self) -> None:
        """B14-Fix: P-Düngung darf nicht mehr in ``crop_management`` liegen."""
        plan = _load_plan()
        crop_ops = _phase_ops(plan, FieldOperationPhases.CROP_MANAGEMENT)
        p_ops = [op for op in crop_ops if op.application_name == _P_NAME]
        assert not p_ops, (
            f"P-Düngung darf nicht in crop_management liegen: {p_ops}."
        )
        # Auch kein Eintrag mit operation-Name "P Düngung"
        p_by_op = [op for op in crop_ops if op.operation == _P_OP_NAME]
        assert not p_by_op, (
            f"Operation 'P Düngung' darf nicht in crop_management liegen: {p_by_op}."
        )

    def test_crop_management_sequence_renumbered(self) -> None:
        """Sequenz in ``crop_management`` neu nummeriert: N-Düngung=1, Häufeln=2."""
        plan = _load_plan()
        crop_ops = _phase_ops(plan, FieldOperationPhases.CROP_MANAGEMENT)
        by_seq = sorted(crop_ops, key=lambda op: op.sequence)
        assert len(by_seq) == 2, (
            f"crop_management sollte 2 Operationen haben (N-Düngung, Häufeln), "
            f"got {len(by_seq)}."
        )
        assert by_seq[0].sequence == 1
        assert by_seq[0].operation == "N Düngung"
        assert by_seq[1].sequence == 2
        assert by_seq[1].operation == "Häufeln"

    def test_harvest_herbizid_offsets_corrected(self) -> None:
        """B5-Fix: Harvest-Phase Herbizid (Quickdown) auf -21/-14 korrigiert."""
        plan = _load_plan()
        harvest_ops = _phase_ops(plan, FieldOperationPhases.HARVESTING)
        herbizid = [op for op in harvest_ops if op.application_name == "Quickdown"]
        assert len(herbizid) == 1, (
            f"Erwartet genau 1 Quickdown in harvesting, got {len(herbizid)}."
        )
        h = herbizid[0]
        assert h.min_days_to_target == -21, (
            f"min_days_to_target={h.min_days_to_target}, erwartet -21 (B5)."
        )
        assert h.max_days_to_target == -14, (
            f"max_days_to_target={h.max_days_to_target}, erwartet -14 (B5)."
        )
        assert int(h.application_category) == 26
        assert h.worktype == 14

    def test_harvest_roden_lagerung_unchanged(self) -> None:
        """Roden (0/+5) und Lagerung (5/+5) bleiben unverändert."""
        plan = _load_plan()
        harvest_ops = _phase_ops(plan, FieldOperationPhases.HARVESTING)
        roden = [op for op in harvest_ops if op.operation == "Roden"]
        lagerung = [op for op in harvest_ops if op.operation == "Lagerung"]
        assert len(roden) == 1 and len(lagerung) == 1
        assert roden[0].min_days_to_target == 0
        assert roden[0].max_days_to_target == 5
        assert roden[0].worktype == 27
        assert lagerung[0].min_days_to_target == 5
        assert lagerung[0].max_days_to_target == 5
        assert lagerung[0].worktype == 58

    def test_soil_preparation_kali_unchanged(self) -> None:
        """Regression: Kali-Düngung bleibt in soil_preparation (seq 4, -5/-1)."""
        plan = _load_plan()
        soil_ops = _phase_ops(plan, FieldOperationPhases.SOIL_PREPARATION)
        kali = [op for op in soil_ops if op.application_name == "Kali"]
        assert len(kali) == 1
        assert kali[0].sequence == 4
        assert kali[0].min_days_to_target == -5
        assert kali[0].max_days_to_target == -1
        assert int(kali[0].application_category) == 34


# ---------------------------------------------------------------------------
# FF-Lauf (Seed 42, 760 d) – Event-Reihenfolge prüfen
# ---------------------------------------------------------------------------

_SEED = 42
_FIELD_ID = 990001
_FIELD_SIZE = 20.0
_N_DAYS = 760
_START_DATE = datetime.datetime(2026, 1, 1)


@pytest.fixture(scope="module")
def ff_events() -> list[Any]:
    """Module-scoped FastForward-Simulation (deterministisch, kein Netzwerk)."""
    random.seed(_SEED)
    np.random.seed(_SEED)
    context = SimContext(
        field_size=_FIELD_SIZE,
        soil_type="sandy_loam",
        start_date=_START_DATE,
        crop_type="Potato",
        variety="Belana",
        field_id=_FIELD_ID,
        field_name="Audit Field",
        fuel_variation=0.1,
    )
    runner = FastForwardRunner(
        context=context,
        n_days=_N_DAYS,
        output_target="stdout",
    )
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        events = runner.run()
    return events


def _parse_date(value: Any) -> datetime.datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                return None
    return None


def _events_wt(events: list[Any], wt: int) -> list[Any]:
    return [e for e in events if int(getattr(e, "worktype", 0)) == wt]


def _events_wt_cat(events: list[Any], wt: int, cat: int) -> list[Any]:
    out: list[Any] = []
    for e in _events_wt(events, wt):
        c = getattr(e, "application_category", None)
        if c is not None:
            try:
                if int(c) == cat:
                    out.append(e)
            except (TypeError, ValueError):
                pass
    return out


def _start(ev: Any) -> datetime.datetime:
    s = _parse_date(getattr(ev, "start_date", None))
    assert s is not None, f"Event ohne start_date: {ev}"
    return s


class TestFastForwardEventOrder:
    """Prüft die Event-Reihenfolge im FF-Lauf nach dem Konfig-Fix."""

    def test_sikkation_to_roden_min_14_days(self, ff_events: list[Any]) -> None:
        """AK #1: letzte Sikkation (wt=14, Kat.26) ≥ 14 d vor Roden (wt=27)."""
        sikkation = _events_wt_cat(ff_events, 14, 26)
        roden = _events_wt(ff_events, 27)
        assert sikkation, "Keine Sikkation (wt=14, Kat.26) im Lauf."
        assert roden, "Kein Roden (wt=27) im Lauf."
        roden_date = min(_start(e) for e in roden)
        # Letzte Sikkation vor dem Roden
        before = [s for s in sikkation if _start(s) < roden_date]
        assert before, "Keine Sikkation vor dem Roden."
        last_sikk = max(_start(s) for s in before)
        delta = (roden_date.date() - last_sikk.date()).days
        assert delta >= 14, (
            f"Abstand letzte Sikkation→Roden = {delta} d < 14 d (B5 nicht gefixt)."
        )

    def test_sikkation_in_window_14_to_35_days_before_roden(
        self, ff_events: list[Any]
    ) -> None:
        """AK #2: Sikkation aus Harvest-Phase im Fenster 14–35 d vor Roden (weich)."""
        sikkation = _events_wt_cat(ff_events, 14, 26)
        roden = _events_wt(ff_events, 27)
        assert sikkation and roden
        roden_date = min(_start(e) for e in roden)
        before = [s for s in sikkation if _start(s) < roden_date]
        assert before
        # Mindestens eine Sikkation muss im Fenster [14, 35] liegen
        in_window = [
            s for s in before
            if 14 <= (roden_date.date() - _start(s).date()).days <= 35
        ]
        assert in_window, (
            "Keine Sikkation im Fenster 14–35 d vor Roden: "
            + ", ".join(
                f"{(roden_date.date() - _start(s).date()).days}d"
                for s in before
            )
        )

    def test_p_duengung_before_legen(self, ff_events: list[Any]) -> None:
        """AK #3: P-Düngung (wt=23, Kat.34, Superphosphat) vor dem Legen (wt=26)."""
        p_duengung = [
            e for e in _events_wt_cat(ff_events, 23, 34)
            if getattr(e, "application_name", None) == "Superphosphat"
        ]
        legen = _events_wt(ff_events, 26)
        assert p_duengung, "Keine P-Düngung (Superphosphat) im Lauf."
        assert legen, "Kein Lege-Event (wt=26) im Lauf."
        legen_date = min(_start(e) for e in legen)
        for p in p_duengung:
            assert _start(p) < legen_date, (
                f"P-Düngung am {_start(p).date()} NACH Legen am {legen_date.date()} "
                f"(B14 nicht gefixt)."
            )

    def test_kali_before_legen_regression(self, ff_events: list[Any]) -> None:
        """AK #4: Kali-Düngung (wt=23, Kat.34, Kali) bleibt vor dem Legen."""
        kali = [
            e for e in _events_wt_cat(ff_events, 23, 34)
            if getattr(e, "application_name", None) == "Kali"
        ]
        legen = _events_wt(ff_events, 26)
        assert kali, "Keine Kali-Düngung im Lauf."
        assert legen
        legen_date = min(_start(e) for e in legen)
        for k in kali:
            assert _start(k) < legen_date, (
                f"Kali-Düngung am {_start(k).date()} NACH Legen am {legen_date.date()} "
                f"(Regression)."
            )

    def test_n_duengung_after_legen_regression(self, ff_events: list[Any]) -> None:
        """AK #5: N-Düngung (Kat.33) 0–35 Tage nach dem Legen (KAR-016)."""
        n_duengung = _events_wt_cat(ff_events, 23, 33)
        legen = _events_wt(ff_events, 26)
        assert n_duengung, "Keine N-Düngung (Kat.33) im Lauf."
        assert legen
        legen_date = min(_start(e) for e in legen)
        for n in n_duengung:
            delta = (_start(n).date() - legen_date.date()).days
            assert 0 <= delta <= 35, (
                f"N-Düngung {delta} d nach Legen (zulässig 0..35): "
                f"{_start(n).date()} vs Legen {legen_date.date()} (Regression)."
            )
