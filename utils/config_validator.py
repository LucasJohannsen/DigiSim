"""Konfigurations-Validierung für Planting-Plan (P3-6, Issue #84).

Prüft die planting_plan-Konfiguration auf Konsistenz und gibt Warnungen
zurück. Fail-open: ungültige Konfiguration wird nicht blockiert, nur
gewarnt.
"""
from __future__ import annotations

from typing import Any

__all__ = ["validate_planting_plan"]


def validate_planting_plan(config: dict[str, Any]) -> list[str]:
    """Validiert planting_plan-Konfiguration auf Konsistenz.

    Fail-open-Prinzip: Probleme werden als Warnungs-Strings zurückgegeben,
    nicht als Exceptions geworfen. Eine leere Liste bedeutet „keine Probleme".

    Aktuell geprüft:
        - Worktype-Label-Konsistenz: Worktype 7 (Eggen) mit „Kreiseln" im
          Label sollte „(Eggen)" enthalten für Klarheit (Befund B11).

    Args:
        config: Geladene planting_plan-Konfiguration als dict.

    Returns:
        Liste von Warnungs-Strings (leer = keine Probleme).
    """
    warnings: list[str] = []

    for phase in config.get("phases", []):
        for phase_body in phase.values():
            if not isinstance(phase_body, dict):
                continue
            for op in phase_body.get("operations", []):
                if not isinstance(op, dict):
                    continue
                wt = op.get("worktype")
                label = op.get("operation", "")
                # Worktype 7 (Eggen) mit „Kreiseln" im Label ist fachlich
                # akzeptabel, aber das Label sollte „(Eggen)" enthalten
                # für Klarheit (Befund B11, KAR-034).
                if wt == 7 and "Kreiseln" in label and "(Eggen)" not in label:
                    warnings.append(
                        f"Worktype 7 (Eggen) mit Label '{label}' – "
                        f"Label sollte '(Eggen)' enthalten für Klarheit"
                    )

    return warnings
