"""Tests für den Konfigurations-Validator (P3-6, Issue #84).

Prüft ``utils.config_validator.validate_planting_plan`` auf
Worktype-Label-Konsistenz (Befund B11).
"""
from __future__ import annotations

from utils.config_validator import validate_planting_plan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(label: str, worktype: int = 7) -> dict[str, object]:
    """Baut eine minimale planting_plan-Config mit einer Operation."""
    return {
        "phases": [
            {
                "soil_preparation": {
                    "operations": [
                        {
                            "sequence": 2,
                            "operation": label,
                            "worktype": worktype,
                        }
                    ]
                }
            }
        ]
    }


# ---------------------------------------------------------------------------
# Testfälle
# ---------------------------------------------------------------------------


class TestValidatePlantingPlan:
    """Tests für ``validate_planting_plan`` (P3-6, Issue #84)."""

    def test_valid_label_kreiseln_eggen_no_warnings(self) -> None:
        """(a) Gültige Config mit „Kreiseln (Eggen)" -> keine Warnungen."""
        config = _make_config("Kreiseln (Eggen)", worktype=7)
        warnings = validate_planting_plan(config)
        assert warnings == []

    def test_label_kreiseln_without_eggen_warns(self) -> None:
        """(b) Config mit „Kreiseln" (ohne „(Eggen)") -> Warnung."""
        config = _make_config("Kreiseln", worktype=7)
        warnings = validate_planting_plan(config)
        assert len(warnings) == 1
        assert "Kreiseln" in warnings[0]
        assert "(Eggen)" in warnings[0]

    def test_empty_config_no_warnings(self) -> None:
        """(c) Leere Config -> keine Warnungen."""
        warnings = validate_planting_plan({})
        assert warnings == []

    def test_config_without_phases_no_warnings(self) -> None:
        """(d) Config ohne phases -> keine Warnungen."""
        warnings = validate_planting_plan({"crop": "Potato"})
        assert warnings == []

    def test_non_kreiseln_worktype_7_no_warning(self) -> None:
        """Worktype 7 mit anderem Label (nicht „Kreiseln") -> keine Warnung."""
        config = _make_config("Eggen", worktype=7)
        warnings = validate_planting_plan(config)
        assert warnings == []

    def test_kreiseln_wrong_worktype_no_warning(self) -> None:
        """„Kreiseln" mit anderem Worktype (nicht 7) -> keine Warnung."""
        config = _make_config("Kreiseln", worktype=9)
        warnings = validate_planting_plan(config)
        assert warnings == []
