"""Plausibilitäts-Checker-Module für DigiSim.

Liefert datengetriebene Prüf-Funktionen, die Event-Sequenzen aus der
FastForward-Simulation gegen das maschinenlesbare Fachregelwerk
(``documentation/fachregeln/kartoffel_regeln.json``) validieren.

Öffentliche API siehe ``rule_checks``.
"""

from tests.plausibility.rule_checks import (
    Violation,
    check_rule,
    load_rules,
    normalize_events,
    segment_cycles,
)

__all__ = [
    "Violation",
    "check_rule",
    "load_rules",
    "normalize_events",
    "segment_cycles",
]
