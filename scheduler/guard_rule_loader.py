"""Loader für Guard-Regeln aus Konfiguration (MS5 P2-4, Issue #68).

Lädt ``config/decision_guards_potato.json`` und instanziiert einen
``RuleGuard`` mit datengetriebenen Guard-Regeln. Fail-open: bei
Konfigurationsfehlern (Datei fehlt, ungültiges JSON, unbekannter
``check_type``) wird ein leerer ``RuleGuard`` zurückgegeben und ein
Warning-Log emittiert – die Simulation läuft ohne Guard weiter.
"""
from __future__ import annotations

import json
import os
from typing import Any, Protocol, runtime_checkable

from scheduler.decision_manager import (
    GuardRule,
    MinGapBeforeHarvestOpRule,
    NoSiccationAfterHarvestRule,
    NoWorktypeAfterHarvestRule,
    RuleGuard,
)
from utils.logger import get_logger

logger = get_logger("guard_rule_loader")

__all__ = ["GuardRuleLoader"]


_DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "decision_guards_potato.json"
)


@runtime_checkable
class _GuardRuleFactory(Protocol):
    """Factory-Protocol für Guard-Regel-Klassen mit from_config()."""

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> GuardRule: ...


# Mapping check_type → GuardRule-Factory (datengetrieben, erweiterbar).
_CHECK_TYPE_MAP: dict[str, _GuardRuleFactory] = {
    "no_worktype_after_harvest": NoWorktypeAfterHarvestRule,
    "min_gap_before_harvest_op": MinGapBeforeHarvestOpRule,
    "no_siccation_after_harvest": NoSiccationAfterHarvestRule,
}


class GuardRuleLoader:
    """Lädt Guard-Regeln aus einer JSON-Konfigurationsdatei."""

    def __init__(self, config_path: str | None = None) -> None:
        self.config_path = config_path or _DEFAULT_CONFIG_PATH

    def load(self) -> RuleGuard:
        """Lädt die Konfiguration und instanziiert einen RuleGuard.

        Fail-open: bei Fehlern wird ein leerer RuleGuard zurückgegeben.
        """
        try:
            with open(self.config_path, encoding="utf-8") as fh:
                data: dict[str, Any] = json.load(fh)
        except FileNotFoundError:
            logger.warning(
                "Guard config not found, guard disabled: %s", self.config_path
            )
            return RuleGuard(rules=[])
        except json.JSONDecodeError as exc:
            logger.warning(
                "Guard config invalid JSON, guard disabled: %s (%s)",
                self.config_path,
                exc,
            )
            return RuleGuard(rules=[])

        rules: list[GuardRule] = []
        for entry in data.get("guards", []):
            check_type = entry.get("check_type")
            rule_cls = _CHECK_TYPE_MAP.get(check_type)
            if rule_cls is None:
                logger.warning(
                    "Unknown guard check_type '%s', skipping rule %s",
                    check_type,
                    entry.get("rule_id", "?"),
                )
                continue
            try:
                rules.append(rule_cls.from_config(entry))
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "Guard rule '%s' could not be loaded, skipping: %s",
                    entry.get("rule_id", "?"),
                    exc,
                )

        return RuleGuard(rules=rules)

    @staticmethod
    def load_default() -> RuleGuard:
        """Convenience: lädt den RuleGuard aus der Standard-Konfiguration."""
        return GuardRuleLoader().load()
