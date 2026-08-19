"""Regel-Checker für die Kartoffel-Plausibilitäts-Testsuite (P1-1, Issue #57).

Dieses Modul ist **reine Test-Infrastruktur** – es enthält keinen
Produktionscode und wird ausschließlich aus
``tests/test_plausibility_kartoffel.py`` angesprochen.

Die Checker lesen das maschinenlesbare Fachregelwerk
``documentation/fachregeln/kartoffel_regeln.json`` und stellen für jede
Regel eine Prüf-Funktion bereit, die eine Liste von normalisierten Events
gegen die Regel validiert. Härtegrad (``hard``/``soft``) wird aus dem
Regelwerk übernommen; **nur harte Verletzungen führen zu Testfehlern**
(soft-Verstöße werden als ``Violation(severity="soft")`` gemeldet, aber
nicht als Fehler gewertet – siehe Konzept P1-1).

Wetter-/Bodenregeln (KAR-030 … KAR-035) prüfen fertige Event-Sequenzen gegen
Wetterdaten aus einem ``WeatherLookup`` (``dict[date, WeatherData]``). Ohne
``weather_lookup`` (Baseline-Suite) werden sie als ``skip`` markiert und geben
eine leere Verletzungsliste + ``weather_skip=True`` zurück (Abwärtskompatibilität).
"""

from __future__ import annotations

import datetime
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from services.weather_service import WeatherData

#: Lookup-Tabelle: Datum → Wetterdaten. Wird aus einem deterministischen
#: Provider (z. B. ``SyntheticWeatherDataProvider``) generiert und an
#: ``check_rule`` übergeben, damit die Wetter-Checker dieselben Daten sehen
#: wie die Guards zur Laufzeit.
type WeatherLookup = dict[datetime.date, WeatherData]

# ---------------------------------------------------------------------------
# Konstanten / Pfade
# ---------------------------------------------------------------------------

_REGELWERK_PFAD = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "documentation",
    "fachregeln",
    "kartoffel_regeln.json",
)

# Worktype-IDs, die im Regelwerk referenziert werden (aus models/worktypes.py).
WT_GRUBBERN = 6
WT_EGGEN = 7
WT_SEPARIEREN = 28
WT_MIN_DUENGUNG = 23
WT_ORG_DUENGUNG = 13
WT_TRANSPORT = 18
WT_LEGEN = 26
WT_SPRITZEN = 14
WT_BEREGNEN = 15
WT_HAEUFELN = 29
WT_KRAUT_SCHLAGEN = 30
WT_RODEN = 27
WT_VERLADEN = 58

# Application categories (aus config/category.json; nicht mit worktypes verwechseln).
CAT_HERBIZID = 26
CAT_FUNGIZID = 27
CAT_INSEKTIZID = 28
CAT_SAATGUT = 29
CAT_N_DUENGUNG = 33
CAT_P_KALI_DUENGUNG = 34


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Violation:
    """Eine einzelne Regelverletzung.

    Attributes:
        rule_id: KAR-Regel-ID (z. B. ``"KAR-020"``).
        severity: ``"hard"`` oder ``"soft"`` – bestimmt, ob der Test fehlschlägt.
        message: Menschenlesbare Beschreibung der Verletzung.
        event_ref: Optionale Referenz auf das betroffene Event (z. B. Datum).
    """

    rule_id: str
    severity: str
    message: str
    event_ref: str | None = None


@dataclass(frozen=True)
class CheckResult:
    """Ergebnis eines Regel-Checks.

    Attributes:
        violations: Liste von Verletzungen (hard + soft).
        weather_skip: ``True``, wenn die Regel wegen fehlender Wetterdaten
            übersprungen wurde (nur KAR-030 … KAR-035).
        skip_reason: Begründungstext bei ``weather_skip``.
    """

    violations: list[Violation]
    weather_skip: bool = False
    skip_reason: str | None = None


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def load_rules(path: str | None = None) -> list[dict[str, Any]]:
    """Lade das Fachregelwerk aus ``kartoffel_regeln.json``.

    Args:
        path: Optionaler abweichender Pfad zur Regelwerk-JSON.

    Returns:
        Liste der Regel-Dicts (jedes mit ``id``, ``category``, ``severity``,
        ``check``).
    """
    pfad = path or os.path.abspath(_REGELWERK_PFAD)
    with open(pfad, encoding="utf-8") as f:
        data = json.load(f)
    return data["rules"]


def _parse_date(value: Any) -> datetime.datetime | None:
    """Parse einen Start/End-Zeitstempel aus einem Event.

    Akzeptiert ``datetime`` und Strings im Format ``"YYYY-MM-DD HH:MM:SS"``.
    """
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


def _coerce_category(value: Any) -> int | str | None:
    """Normalisiere ``application_category`` auf ``int`` wenn möglich, sonst ``str``."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return str(value)


def normalize_events(events: list[Any]) -> list[dict[str, Any]]:
    """Wandle rohe ``FieldOperationEvent``-Objekte (oder Dicts) in normalisierte Dicts.

    Jedes normalisiertes Event enthält:
    - ``worktype``: int
    - ``start``: datetime
    - ``end``: datetime | None
    - ``category``: int | str | None  (normalisierte application_category)
    - ``amount``: float
    - ``unit``: str | None
    - ``area``: float
    - ``name``: str | None
    - ``worktype_text``: str | None
    - ``raw``: das ursprüngliche Objekt (für Referenzen)
    """
    normalized: list[dict[str, Any]] = []
    for ev in events:
        if isinstance(ev, dict):
            worktype = int(ev.get("worktype", 0))
            start = _parse_date(ev.get("start_date"))
            end = _parse_date(ev.get("end_date"))
            category = _coerce_category(ev.get("application_category"))
            amount = float(ev.get("application_amount", 0.0) or 0.0)
            unit = ev.get("application_unit")
            area = float(ev.get("area", 0.0) or 0.0)
            name = ev.get("application_name")
            text = ev.get("worktype_text")
        else:
            worktype = int(getattr(ev, "worktype", 0))
            start = _parse_date(getattr(ev, "start_date", None))
            end = _parse_date(getattr(ev, "end_date", None))
            category = _coerce_category(getattr(ev, "application_category", None))
            amount = float(getattr(ev, "application_amount", 0.0) or 0.0)
            unit = getattr(ev, "application_unit", None)
            area = float(getattr(ev, "area", 0.0) or 0.0)
            name = getattr(ev, "application_name", None)
            text = getattr(ev, "worktype_text", None)
        normalized.append(
            {
                "worktype": worktype,
                "start": start,
                "end": end,
                "category": category,
                "amount": amount,
                "unit": unit,
                "area": area,
                "name": name,
                "worktype_text": text,
                "raw": ev,
            }
        )
    return normalized


def segment_cycles(events: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Segmentiere Events in Anbauzyklen anhand der Lege-Events (wt=26).

    Ein neuer Zyklus beginnt an jedem Lege-Event. Events vor dem ersten
    Legen gehören zum ersten Zyklus (Bodenbearbeitung läuft vor dem Legen).

    Limitierung: Bei mehreren Zyklen pro Lauf wird die Bodenbearbeitung des
    Folgezyklus dem vorangegangenen Zyklus zugeordnet (Cycle-Ende-Event fehlt,
    siehe Befund B13). Für die aktuelle Single-Cycle-Baseline (760 Tage, 1
    Lege-Event) ist die Segmentierung korrekt.
    """
    if not events:
        return []
    sorted_events = sorted(events, key=lambda e: e["start"] or datetime.datetime.min)
    boundaries = [i for i, e in enumerate(sorted_events) if e["worktype"] == WT_LEGEN]
    if not boundaries:
        return [sorted_events]
    cycles: list[list[dict[str, Any]]] = []
    # Zyklus 0: alles bis zum 2. Legen (das 1. Legen gehört noch zu Zyklus 0)
    prev = 0
    for b in boundaries[1:]:
        cycles.append(sorted_events[prev:b])
        prev = b
    cycles.append(sorted_events[prev:])
    return cycles


def _events_with_wt(
    cycle: list[dict[str, Any]], worktypes: int | list[int]
) -> list[dict[str, Any]]:
    if isinstance(worktypes, int):
        worktypes = [worktypes]
    wt_set = set(worktypes)
    return [e for e in cycle if e["worktype"] in wt_set]


def _events_with_wt_cat(
    cycle: list[dict[str, Any]],
    worktype: int,
    category: int | None = None,
) -> list[dict[str, Any]]:
    result = [e for e in cycle if e["worktype"] == worktype]
    if category is not None:
        result = [e for e in result if e["category"] == category]
    return result


def _days_between(a: datetime.datetime, b: datetime.datetime) -> int:
    """Kalendertage-Differenz (Datumsebene, ohne Uhrzeit)."""
    return (a.date() - b.date()).days


def _ref(ev: dict[str, Any]) -> str:
    start = ev.get("start")
    if start is None:
        return f"wt={ev['worktype']}"
    return f"wt={ev['worktype']} @ {start.date().isoformat()}"


# ---------------------------------------------------------------------------
# Check-Implementierungen (dispatch nach check.type)
# ---------------------------------------------------------------------------


def _check_phase_order(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-001: Phasenreihenfolge Bodenbearbeitung → Legen → Sikkation → Roden → Lagerung.

    Geprüft wird die Makro-Reihenfolge der Phasen-Anker:
    max(Bodenbearbeitung) < Legen < min(Sikkation) < Roden < Lagerung.
    Die Pflege-Gruppe (23/29/14) überlappt per Definition mit Legen/Sikkation
    (Grunddüngung vor dem Legen ist via KAR-016 erlaubt) und wird hier nicht
    auf strikte Reihenfolge geprüft.
    """
    order = rule["check"]["order"]
    rid = rule["id"]
    sev = rule["severity"]
    out: list[Violation] = []

    def group_dates(wts: list[int]) -> list[datetime.datetime]:
        return [e["start"] for e in cycle if e["worktype"] in wts and e["start"]]

    soil_wts = order[0]  # [5,6,7,28]

    soil_dates = group_dates(soil_wts)
    planting_dates = [e["start"] for e in _events_with_wt(cycle, WT_LEGEN) if e["start"]]
    sikkation_dates = [
        e["start"] for e in _events_with_wt_cat(cycle, WT_SPRITZEN, CAT_HERBIZID) if e["start"]
    ]
    harvest_dates = [e["start"] for e in _events_with_wt(cycle, WT_RODEN) if e["start"]]
    storage_dates = [e["start"] for e in _events_with_wt(cycle, WT_VERLADEN) if e["start"]]

    anchors: list[tuple[str, datetime.datetime | None]] = [
        ("Bodenbearbeitung_max", max(soil_dates) if soil_dates else None),
        ("Legen", planting_dates[0] if planting_dates else None),
        ("Sikkation_min", min(sikkation_dates) if sikkation_dates else None),
        ("Roden", harvest_dates[0] if harvest_dates else None),
        ("Lagerung", storage_dates[0] if storage_dates else None),
    ]
    # Aufsteigende Reihenfolge der vorhandenen Anker prüfen
    present = [(name, d) for name, d in anchors if d is not None]
    for (n1, d1), (n2, d2) in zip(present, present[1:], strict=False):
        if d1 >= d2:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"Phasenreihenfolge invertiert: {n1} ({d1.date()}) "
                    f">= {n2} ({d2.date()}).",
                )
            )
    return out


def _check_no_worktype_after(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-002 / KAR-005: Keine Worktypes aus einer Menge nach einem Anker-Worktype."""
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    forbidden = check["worktypes"]
    after_wt = check["after_worktype"]
    anchor_events = [e for e in cycle if e["worktype"] == after_wt and e["start"]]
    if not anchor_events:
        return []
    anchor = min(e["start"] for e in anchor_events)
    # 'until_worktype' begrenzt das Fenster (z. B. bis Roden); 'until=cycle_end' = bis Zyklusende
    until_wt = check.get("until_worktype")
    until_cycle_end = check.get("until") == "cycle_end"
    if until_wt is not None:
        until_events = [e for e in cycle if e["worktype"] == until_wt and e["start"]]
        window_end = min(e["start"] for e in until_events) if until_events else None
    elif until_cycle_end:
        window_end = None
    else:
        window_end = None
    out: list[Violation] = []
    for e in cycle:
        if e["worktype"] not in forbidden or e["start"] is None:
            continue
        if e["start"] <= anchor:
            continue
        if window_end is not None and e["start"] >= window_end:
            continue
        out.append(
            Violation(
                rule_id=rid,
                severity=sev,
                message=f"Worktype {e['worktype']} nach Anker wt={after_wt} "
                f"({anchor.date()}): {_ref(e)}.",
                event_ref=_ref(e),
            )
        )
    return out


def _check_intraday_timestamp_order(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-003: Intra-Tages-Sequenz – bei gleichem Datum muss Reihenfolge erhalten bleiben."""
    rid = rule["id"]
    sev = rule["severity"]
    pairs = rule["check"]["pairs"]  # z. B. [[18, 26]] -> wt=18 muss VOR wt=26 liegen
    out: list[Violation] = []
    for first_wt, second_wt in pairs:
        first_events = [e for e in cycle if e["worktype"] == first_wt and e["start"]]
        second_events = [e for e in cycle if e["worktype"] == second_wt and e["start"]]
        for f in first_events:
            for s in second_events:
                if f["start"].date() == s["start"].date() and f["start"] >= s["start"]:
                    out.append(
                        Violation(
                            rule_id=rid,
                            severity=sev,
                            message=(
                                f"Intra-Tages-Sequenz invertiert: wt={first_wt} "
                                f"({f['start'].time()}) >= wt={second_wt} "
                                f"({s['start'].time()}) am {f['start'].date()}."
                            ),
                            event_ref=f"{f['start'].isoformat()} / {s['start'].isoformat()}",
                        )
                    )
    return out


def _check_requires_prior_event(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-004: Roden erst nach Sikkation (wt=14 cat=26) oder Kraut schlagen (wt=30)."""
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    target_wt = check["worktype"]
    prior = check["prior"]
    alt_prior = check.get("alternative_prior")
    out: list[Violation] = []
    for e in cycle:
        if e["worktype"] != target_wt or e["start"] is None:
            continue
        prior_events = _events_with_wt_cat(
            cycle, prior["worktype"], prior.get("application_category")
        )
        prior_dates = [p["start"] for p in prior_events if p["start"] and p["start"] < e["start"]]
        alt_dates: list[datetime.datetime] = []
        if alt_prior is not None:
            alt_events = _events_with_wt(cycle, alt_prior["worktype"])
            alt_dates = [p["start"] for p in alt_events if p["start"] and p["start"] < e["start"]]
        if not prior_dates and not alt_dates:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"wt={target_wt} ohne vorangegangenes Sikkations-Event: {_ref(e)}.",
                    event_ref=_ref(e),
                )
            )
    return out


def _check_no_worktype_before(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-006: Kein Worktype vor einem Anker-Worktype (z. B. keine Beregnung vor dem Legen)."""
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    wt = check["worktype"]
    before_wt = check["before_worktype"]
    anchor_events = [e for e in cycle if e["worktype"] == before_wt and e["start"]]
    if not anchor_events:
        return []
    anchor = min(e["start"] for e in anchor_events)
    out: list[Violation] = []
    for e in cycle:
        if e["worktype"] != wt or e["start"] is None:
            continue
        if e["start"] < anchor:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"wt={wt} ({e['start'].date()}) vor wt={before_wt} ({anchor.date()}).",
                    event_ref=_ref(e),
                )
            )
    return out


def _check_interval_days(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-007/008/020/023/025/047: Tagesabstand zwischen zwei Worktype-Events.

    Occurrence-Semantik:
    - ``from.occurrence`` (im ``from``-Dict) wählt das Quell-Event aus.
    - Top-Level ``occurrence`` mit ``to_application_category`` wählt das
      Ziel-Event (z. B. KAR-008 "first Herbizid nach Legen").
    - Top-Level ``occurrence`` ohne ``to_application_category`` wählt das
      Quell-Event (z. B. KAR-023 "letzte Saatbettbereitung vor Legen").
    """
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    out: list[Violation] = []

    # Quell-Worktypes und ggf. Quell-Kategorie bestimmen
    from_cat: int | None = None
    src_occ: str | None = None
    if "from_worktype" in check:
        from_wts: list[int] = [check["from_worktype"]]
    elif "from_worktypes" in check:
        from_wts = check["from_worktypes"]
    elif "from" in check:
        spec = check["from"]
        from_wts = [spec["worktype"]]
        from_cat = spec.get("application_category")
        src_occ = spec.get("occurrence")
    else:
        return []

    to_wt = check["to_worktype"]
    to_cat = check.get("to_application_category")

    # Ziel-Occurrence nur, wenn Top-Level occurrence + to_application_category
    dst_occ: str | None = None
    if "occurrence" in check and "to_application_category" in check:
        dst_occ = check["occurrence"]
    elif "occurrence" in check and src_occ is None:
        # Top-Level occurrence ohne from-Dict → wählt Quelle (z. B. KAR-023)
        src_occ = check["occurrence"]

    src_events = [e for e in cycle if e["worktype"] in from_wts and e["start"]]
    if from_cat is not None:
        src_events = [e for e in src_events if e["category"] == from_cat]
    dst_events = [e for e in cycle if e["worktype"] == to_wt and e["start"]]
    if to_cat is not None:
        dst_events = [e for e in dst_events if e["category"] == to_cat]

    if not src_events or not dst_events:
        return []

    src_events = sorted(src_events, key=lambda e: e["start"])
    dst_events = sorted(dst_events, key=lambda e: e["start"])

    # Quell-Event(s) basierend auf src_occ selektieren
    if src_occ == "last":
        src_selected: list[dict[str, Any]] = [src_events[-1]]
    elif src_occ == "last_before_harvest":
        harvest_events = [e for e in cycle if e["worktype"] == WT_RODEN and e["start"]]
        if harvest_events:
            harvest = min(e["start"] for e in harvest_events)
            before = [e for e in src_events if e["start"] < harvest]
            if not before:
                return []
            src_selected = [before[-1]]
        else:
            src_selected = [src_events[-1]]
    else:
        # 'first' oder None → erstes Quell-Event
        src_selected = [src_events[0]]

    # Ziel-Event(s) basierend auf dst_occ selektieren
    if dst_occ == "first":
        dst_selected: list[dict[str, Any]] = [dst_events[0]]
    elif dst_occ == "last":
        dst_selected = [dst_events[-1]]
    else:
        dst_selected = dst_events

    min_days = check.get("min_days")
    max_days = check.get("max_days")
    soft_max_days = check.get("soft_max_days")

    for src in src_selected:
        # Nur Ziel-Events nach dem Quell-Event betrachten
        following = [d for d in dst_selected if d["start"] >= src["start"]]
        if not following:
            continue
        # Bei mehreren Kandidaten das erste nach der Quelle nehmen
        # (Ausnahme: dst_occ='last' → letztes insgesamt)
        if dst_occ == "last":
            dst = dst_selected[0]
        else:
            dst = following[0]
        delta = _days_between(dst["start"], src["start"])
        if min_days is not None and delta < min_days:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"Abstand wt={src['worktype']}→{dst['worktype']} "
                    f"= {delta} d < min={min_days} d.",
                    event_ref=f"{src['start'].date()} → {dst['start'].date()}",
                )
            )
        elif max_days is not None and delta > max_days:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"Abstand wt={src['worktype']}→{dst['worktype']} "
                    f"= {delta} d > max={max_days} d.",
                    event_ref=f"{src['start'].date()} → {dst['start'].date()}",
                )
            )
        elif soft_max_days is not None and delta > soft_max_days:
            out.append(
                Violation(
                    rule_id=rid,
                    severity="soft",
                    message=f"Abstand wt={src['worktype']}→{dst['worktype']} "
                    f"= {delta} d > soft_max={soft_max_days} d.",
                    event_ref=f"{src['start'].date()} → {dst['start'].date()}",
                )
            )
    return out


def _check_month_window(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-010…014: Monat der Events je Worktype in zulässigem Fenster."""
    rid = rule["id"]
    check = rule["check"]
    out: list[Violation] = []
    wts: list[int]
    if "worktype" in check:
        wts = [check["worktype"]]
    else:
        wts = check["worktypes"]
    hard_months = set(check.get("hard_months", []))
    soft_months = set(check.get("soft_months", []))
    for e in cycle:
        if e["worktype"] not in wts or e["start"] is None:
            continue
        month = e["start"].month
        if hard_months and month not in hard_months:
            out.append(
                Violation(
                    rule_id=rid,
                    severity="hard",
                    message=f"wt={e['worktype']} im Monat {month} nicht in "
                    f"harten Monaten {sorted(hard_months)}.",
                    event_ref=_ref(e),
                )
            )
        elif soft_months and month not in soft_months:
            out.append(
                Violation(
                    rule_id=rid,
                    severity="soft",
                    message=f"wt={e['worktype']} im Monat {month} nicht in "
                    f"weichen Monaten {sorted(soft_months)}.",
                    event_ref=_ref(e),
                )
            )
    return out


def _check_chronology_consistency(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-015: Konsistente Zeitachse – keine Jahres-Sprünge innerhalb eines Zyklus.

    Aufeinanderfolgende Events (sortiert nach start_date) dürfen höchstens um
    ``max_year_gap_within_cycle`` Jahre springen, außer am legitimen
    Jahreswechsel Dez→Jan (innerhalb derselben Saison).
    """
    rid = rule["id"]
    sev = rule["severity"]
    max_gap = rule["check"].get("max_year_gap_within_cycle", 0)
    out: list[Violation] = []
    sorted_cycle = sorted([e for e in cycle if e["start"] is not None], key=lambda e: e["start"])
    for prev, cur in zip(sorted_cycle, sorted_cycle[1:], strict=False):
        if cur["start"] <= prev["start"]:
            continue
        year_diff = cur["start"].year - prev["start"].year
        # Legitimer Jahreswechsel Dez→Jan (diff=1, Monat springt 12→1)
        legit_jump = year_diff == 1 and prev["start"].month == 12 and cur["start"].month == 1
        if abs(year_diff) > max_gap and not legit_jump:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"Jahressprung innerhalb Zyklus: {prev['start'].date()} "
                    f"→ {cur['start'].date()} (Δyear={year_diff}).",
                    event_ref=f"{_ref(prev)} → {_ref(cur)}",
                )
            )
    return out


def _check_fertilization_windows(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-016: Grunddüngung (cat 34) vor dem Legen; N-Kopfdüngung (cat 33) 1-35 d nach Legen."""
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    base_cats = set(check["base_fertilizer_categories"])
    top_cats = set(check["top_dressing_categories"])
    ref_wt = check["reference_worktype"]
    max_after = check["top_dressing_max_days_after"]
    out: list[Violation] = []
    planting_events = [e for e in cycle if e["worktype"] == ref_wt and e["start"]]
    if not planting_events:
        return []
    planting = min(e["start"] for e in planting_events)
    for e in cycle:
        if e["start"] is None or e["category"] is None:
            continue
        cat = e["category"]
        if cat in base_cats and e["start"] > planting:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"Grunddüngung (cat={cat}) nach dem Legen: {_ref(e)}.",
                    event_ref=_ref(e),
                )
            )
        elif cat in top_cats:
            delta = _days_between(e["start"], planting)
            if delta < 1 or delta > max_after:
                out.append(
                    Violation(
                        rule_id=rid,
                        severity=sev,
                        message=f"N-Kopfdüngung {delta} d nach Legen (zulässig 1..{max_after}): {_ref(e)}.",
                        event_ref=_ref(e),
                    )
                )
    return out


def _check_gap_between_events(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-021/022: Abstand aufeinanderfolgender Events desselben Worktypes/Kategorie."""
    rid = rule["id"]
    check = rule["check"]
    wt = check["worktype"]
    cat = check.get("application_category")
    hard_min = check.get("hard_min_days")
    soft_min = check.get("soft_min_days")
    soft_max = check.get("soft_max_days")
    out: list[Violation] = []
    events = _events_with_wt(cycle, wt)
    if cat is not None:
        events = [e for e in events if e["category"] == cat]
    events = sorted([e for e in events if e["start"]], key=lambda e: e["start"])
    for prev, cur in zip(events, events[1:], strict=False):
        delta = _days_between(cur["start"], prev["start"])
        if hard_min is not None and delta < hard_min:
            out.append(
                Violation(
                    rule_id=rid,
                    severity="hard",
                    message=f"Abstand wt={wt} = {delta} d < hard_min={hard_min} d.",
                    event_ref=f"{prev['start'].date()} → {cur['start'].date()}",
                )
            )
        elif soft_min is not None and delta < soft_min:
            out.append(
                Violation(
                    rule_id=rid,
                    severity="soft",
                    message=f"Abstand wt={wt} = {delta} d < soft_min={soft_min} d.",
                    event_ref=f"{prev['start'].date()} → {cur['start'].date()}",
                )
            )
        elif soft_max is not None and delta > soft_max:
            out.append(
                Violation(
                    rule_id=rid,
                    severity="soft",
                    message=f"Abstand wt={wt} = {delta} d > soft_max={soft_max} d.",
                    event_ref=f"{prev['start'].date()} → {cur['start'].date()}",
                )
            )
    return out


def _check_siccation_limits(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-024: Sikkations-Grenzen (Shark ≤1×, Quickdown ≤2×, Abstand 4-7 d, letzte Gabe ≥14 d vor Roden).

    Hinweis: Die Unterscheidung Shark vs. Quickdown erfolgt heuristisch am
    ``application_name`` (Substring 'shark'/'quickdown'). Nur Events mit
    'quickdown' oder 'shark' im Namen werden als Sikkationsmittel gewertet –
    andere Herbizide (Bandur Artist, Boxer etc.) sind keine Sikkation.
    """
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    out: list[Violation] = []
    all_herbizid = _events_with_wt_cat(cycle, WT_SPRITZEN, CAT_HERBIZID)
    all_herbizid = sorted([e for e in all_herbizid if e["start"]], key=lambda e: e["start"])

    def medium(ev: dict[str, Any]) -> str | None:
        name = (ev.get("name") or "").lower()
        if "shark" in name:
            return "shark"
        if "quickdown" in name:
            return "quickdown"
        return None  # kein Sikkationsmittel (z. B. Vorauflauf-Herbizid)

    sikkation = [e for e in all_herbizid if medium(e) is not None]
    shark = [e for e in sikkation if medium(e) == "shark"]
    quickdown = [e for e in sikkation if medium(e) == "quickdown"]

    if len(shark) > check["max_shark_per_cycle"]:
        out.append(
            Violation(
                rule_id=rid,
                severity=sev,
                message=f"Shark {len(shark)}× > {check['max_shark_per_cycle']}× pro Zyklus.",
            )
        )
    if len(quickdown) > check["max_quickdown_per_cycle"]:
        out.append(
            Violation(
                rule_id=rid,
                severity=sev,
                message=f"Quickdown {len(quickdown)}× > {check['max_quickdown_per_cycle']}× pro Zyklus.",
            )
        )
    gap_min, gap_max = check["quickdown_gap_days"]
    for prev, cur in zip(quickdown, quickdown[1:], strict=False):
        delta = _days_between(cur["start"], prev["start"])
        if delta < gap_min or delta > gap_max:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"Quickdown-Abstand {delta} d außerhalb [{gap_min},{gap_max}].",
                    event_ref=f"{prev['start'].date()} → {cur['start'].date()}",
                )
            )
    harvest_events = [e for e in cycle if e["worktype"] == WT_RODEN and e["start"]]
    if sikkation and harvest_events:
        harvest = min(e["start"] for e in harvest_events)
        last = sikkation[-1]["start"]
        delta = _days_between(harvest, last)
        if delta < check["min_days_before_harvest"]:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"Letzte Sikkation {delta} d vor Roden < {check['min_days_before_harvest']} d.",
                    event_ref=f"{last.date()} → Roden {harvest.date()}",
                )
            )
    return out


def _check_amount_range(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-040: application_amount in hartem/weichem Bereich."""
    rid = rule["id"]
    check = rule["check"]
    wt = check["worktype"]
    hard_min = check["hard_min"]
    hard_max = check["hard_max"]
    soft_min = check.get("soft_min")
    soft_max = check.get("soft_max")
    out: list[Violation] = []
    for e in _events_with_wt(cycle, wt):
        amt = e["amount"]
        if amt < hard_min or amt > hard_max:
            out.append(
                Violation(
                    rule_id=rid,
                    severity="hard",
                    message=f"application_amount={amt} außerhalb hart [{hard_min},{hard_max}].",
                    event_ref=_ref(e),
                )
            )
        elif soft_min is not None and soft_max is not None and (amt < soft_min or amt > soft_max):
            out.append(
                Violation(
                    rule_id=rid,
                    severity="soft",
                    message=f"application_amount={amt} außerhalb weich [{soft_min},{soft_max}].",
                    event_ref=_ref(e),
                )
            )
    return out


def _check_seasonal_sum(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-041: Saisonaler Summenbereich."""
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    wt = check["worktype"]
    lo = check["min"]
    hi = check["max"]
    total = sum(e["amount"] for e in _events_with_wt(cycle, wt))
    out: list[Violation] = []
    if total < lo or total > hi:
        out.append(
            Violation(
                rule_id=rid,
                severity=sev,
                message=f"Saisonsumme wt={wt} = {total} außerhalb [{lo},{hi}].",
            )
        )
    return out


def _check_event_count(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-042 / KAR-046: Anzahlen je Zyklus (gesamt und/oder je Kategorie)."""
    rid = rule["id"]
    check = rule["check"]
    out: list[Violation] = []
    if "per_cycle" in check:
        for wt_str, expected in check["per_cycle"].items():
            wt = int(wt_str)
            count = len(_events_with_wt(cycle, wt))
            if count != expected:
                out.append(
                    Violation(
                        rule_id=rid,
                        severity="hard",
                        message=f"wt={wt}: {count}× (erwartet genau {expected}).",
                    )
                )
    if "total_range" in check:
        wt = check["worktype"]
        total = len(_events_with_wt(cycle, wt))
        lo, hi = check["total_range"]
        if total < lo or total > hi:
            out.append(
                Violation(
                    rule_id=rid,
                    severity="soft",
                    message=f"wt={wt}: {total}× außerhalb [{lo},{hi}].",
                )
            )
    if "by_category" in check:
        wt = check["worktype"]
        wt_events = _events_with_wt(cycle, wt)
        for cat_str, rng in check["by_category"].items():
            cat = int(cat_str)
            count = sum(1 for e in wt_events if e["category"] == cat)
            lo, hi = rng
            if count < lo or count > hi:
                out.append(
                    Violation(
                        rule_id=rid,
                        severity="soft",
                        message=f"wt={wt} cat={cat}: {count}× außerhalb [{lo},{hi}].",
                    )
                )
    return out


def _check_nutrient_sum(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-043: N-Düngung gesamt ≤ Grenze (kg N/ha)."""
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    wt = check["worktype"]
    cat = check.get("application_category")
    max_kg = check["max_kg_n_per_ha"]
    events = _events_with_wt(cycle, wt)
    if cat is not None:
        events = [e for e in events if e["category"] == cat]
    # application_amount wird als kg/ha interpretiert; falls area>0 als Gesamtmenge.
    total_per_ha = 0.0
    for e in events:
        if e["area"] and e["area"] > 0:
            total_per_ha += e["amount"] / e["area"]
        else:
            total_per_ha += e["amount"]
    out: list[Violation] = []
    if total_per_ha > max_kg:
        out.append(
            Violation(
                rule_id=rid,
                severity=sev,
                message=f"N-Düngung gesamt {total_per_ha} kg/ha > {max_kg}.",
            )
        )
    return out


def _check_amount_per_ha_range(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-044: application_amount pro Hektar in Bereich."""
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    wt = check["worktype"]
    lo = check["min"]
    hi = check["max"]
    out: list[Violation] = []
    for e in _events_with_wt(cycle, wt):
        if e["area"] and e["area"] > 0:
            per_ha = e["amount"] / e["area"]
        else:
            per_ha = e["amount"]
        if per_ha < lo or per_ha > hi:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"application_amount/ha={per_ha} außerhalb [{lo},{hi}].",
                    event_ref=_ref(e),
                )
            )
    return out


def _check_operation_timing(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-045: Arbeitsbeginn 05:00-20:00; max. 18 h Dauer."""
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    start_lo, start_hi = check["start_hour_range"]
    max_dur_h = check["max_duration_hours"]
    out: list[Violation] = []
    for e in cycle:
        if e["start"] is None:
            continue
        hour = e["start"].hour
        if hour < start_lo or hour > start_hi:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=f"Arbeitsbeginn {hour}:00 außerhalb [{start_lo},{start_hi}].",
                    event_ref=_ref(e),
                )
            )
        if e["end"] is not None:
            dur_h = (e["end"] - e["start"]).total_seconds() / 3600.0
            if dur_h > max_dur_h:
                out.append(
                    Violation(
                        rule_id=rid,
                        severity=sev,
                        message=f"Dauer {dur_h:.1f} h > {max_dur_h} h.",
                        event_ref=_ref(e),
                    )
                )
    return out


# ---------------------------------------------------------------------------
# Wetter-Checks (KAR-030 … KAR-035)
# ---------------------------------------------------------------------------


def _check_weather_condition(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-030 / KAR-035: Kein Spritzen bei Regen/Wind oder Hitze.

    Prüft für alle Events des konfigurierten Worktypes (optional gefiltert
    nach ``application_category``), ob die Wetterdaten am Event-Datum die
    Schwellwerte für Niederschlag, Wind oder Temperatur überschreiten.
    """
    if weather_lookup is None:
        return []
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    wt = check["worktype"]
    max_precip = check.get("max_precipitation_mm_day")
    max_wind = check.get("max_wind_ms")
    max_temp = check.get("max_temperature_c")
    app_cat = check.get("application_category")
    out: list[Violation] = []
    for e in cycle:
        if e["worktype"] != wt or e["start"] is None:
            continue
        if app_cat is not None and e["category"] != app_cat:
            continue
        w = weather_lookup.get(e["start"].date())
        if w is None:
            continue
        if max_precip is not None and w.precipitation_mm > max_precip:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=(
                        f"Niederschlag {w.precipitation_mm} mm > {max_precip} mm am {_ref(e)}."
                    ),
                    event_ref=_ref(e),
                )
            )
        if max_wind is not None and w.wind_speed_ms > max_wind:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=(f"Wind {w.wind_speed_ms} m/s > {max_wind} m/s am {_ref(e)}."),
                    event_ref=_ref(e),
                )
            )
        if max_temp is not None and w.temperature_max_c > max_temp:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=(f"Temperatur {w.temperature_max_c} °C > {max_temp} °C am {_ref(e)}."),
                    event_ref=_ref(e),
                )
            )
    return out


def _check_soil_condition(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-032 / KAR-033: Bodenbearbeitung bei nassen Bedingungen / Bodentemperatur.

    KAR-032: Keine Bodenbearbeitung bei nFK > Schwellwert oder
    Vortagesniederschlag > Schwellwert.
    KAR-033: Legen erst ab Bodentemperatur >= Schwellwert (Näherung:
    Bodentemperatur ≈ (temp_max + temp_min) / 2).
    """
    if weather_lookup is None:
        return []
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    worktypes = check.get("worktypes", [check.get("worktype")])
    max_moisture = check.get("max_soil_moisture_pct_nfk")
    max_prev_precip = check.get("max_previous_day_precipitation_mm")
    min_soil_temp = check.get("min_soil_temperature_c")
    out: list[Violation] = []
    for e in cycle:
        if e["worktype"] not in worktypes or e["start"] is None:
            continue
        d = e["start"].date()
        w = weather_lookup.get(d)
        if w is None:
            continue
        if max_moisture is not None and w.soil_moisture_pct_nfk > max_moisture:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=(f"nFK {w.soil_moisture_pct_nfk} % > {max_moisture} % am {_ref(e)}."),
                    event_ref=_ref(e),
                )
            )
        if max_prev_precip is not None:
            prev = weather_lookup.get(d - datetime.timedelta(days=1))
            if prev is not None and prev.precipitation_mm > max_prev_precip:
                out.append(
                    Violation(
                        rule_id=rid,
                        severity=sev,
                        message=(
                            f"Vortagesniederschlag {prev.precipitation_mm} mm > "
                            f"{max_prev_precip} mm vor {_ref(e)}."
                        ),
                        event_ref=_ref(e),
                    )
                )
        if min_soil_temp is not None:
            soil_temp = (w.temperature_max_c + w.temperature_min_c) / 2.0
            if soil_temp < min_soil_temp:
                out.append(
                    Violation(
                        rule_id=rid,
                        severity=sev,
                        message=(
                            f"Bodentemperatur ≈ {soil_temp:.1f} °C < "
                            f"{min_soil_temp} °C am {_ref(e)}."
                        ),
                        event_ref=_ref(e),
                    )
                )
    return out


def _check_forecast_condition(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-031: Keine Beregnung bei prognostiziertem Niederschlag.

    Kumuliert den Niederschlag der Folgetage (1 … forecast_days) und meldet
    eine Verletzung, wenn die Summe den Schwellwert überschreitet.
    """
    if weather_lookup is None:
        return []
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    wt = check["worktype"]
    forecast_days = check["forecast_days"]
    max_cumul = check["max_cumulative_precipitation_mm"]
    out: list[Violation] = []
    for e in cycle:
        if e["worktype"] != wt or e["start"] is None:
            continue
        d = e["start"].date()
        cumul = 0.0
        for i in range(1, forecast_days + 1):
            fw = weather_lookup.get(d + datetime.timedelta(days=i))
            if fw is not None:
                cumul += fw.precipitation_mm
        if cumul > max_cumul:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=(
                        f"Prognose-Niederschlag {cumul:.1f} mm > {max_cumul} mm "
                        f"in {forecast_days} Tagen ab {_ref(e)}."
                    ),
                    event_ref=_ref(e),
                )
            )
    return out


def _check_irrigation_trigger(
    cycle: list[dict[str, Any]],
    rule: dict[str, Any],
    weather_lookup: WeatherLookup | None = None,
) -> list[Violation]:
    """KAR-034: Beregnungsauslösung nur bei nFK < Schwellwert.

    Prüft, ob die synthetische Bodenfeuchte (``soil_moisture_pct_nfk`` aus
    dem WeatherLookup) am Beregnungs-Tag unter dem Trigger-Schwellwert lag.
    Da ``FieldOperationEvent`` keine nFK-Werte enthält, dient der
    ``WeatherLookup`` als Näherung.
    """
    if weather_lookup is None:
        return []
    rid = rule["id"]
    sev = rule["severity"]
    check = rule["check"]
    wt = check["worktype"]
    trigger_early = check["trigger_pct_nfk_early"]
    out: list[Violation] = []
    for e in cycle:
        if e["worktype"] != wt or e["start"] is None:
            continue
        w = weather_lookup.get(e["start"].date())
        if w is None:
            continue
        if w.soil_moisture_pct_nfk >= trigger_early:
            out.append(
                Violation(
                    rule_id=rid,
                    severity=sev,
                    message=(
                        f"Beregnung bei nFK {w.soil_moisture_pct_nfk} % >= "
                        f"{trigger_early} % (Trigger-Schwellwert) am {_ref(e)}."
                    ),
                    event_ref=_ref(e),
                )
            )
    return out


# Wetter-Regel-IDs (KAR-030 … KAR-035)
_WEATHER_RULE_IDS = {f"KAR-0{i}" for i in range(30, 36)}


def _weather_skip(rule: dict[str, Any]) -> CheckResult:
    return CheckResult(
        violations=[],
        weather_skip=True,
        skip_reason=(
            f"{rule['id']}: Wetter-/Bodenkopplung erst nach P3 verfügbar (Befund B4/B8, Issue #57)."
        ),
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_CHECK_DISPATCH: dict[str, Callable[..., list[Violation]]] = {
    "phase_order": _check_phase_order,
    "no_worktype_after": _check_no_worktype_after,
    "intraday_timestamp_order": _check_intraday_timestamp_order,
    "requires_prior_event": _check_requires_prior_event,
    "no_worktype_before": _check_no_worktype_before,
    "interval_days": _check_interval_days,
    "month_window": _check_month_window,
    "chronology_consistency": _check_chronology_consistency,
    "fertilization_windows": _check_fertilization_windows,
    "gap_between_events": _check_gap_between_events,
    "siccation_limits": _check_siccation_limits,
    "amount_range": _check_amount_range,
    "seasonal_sum": _check_seasonal_sum,
    "event_count": _check_event_count,
    "nutrient_sum": _check_nutrient_sum,
    "amount_per_ha_range": _check_amount_per_ha_range,
    "operation_timing": _check_operation_timing,
    "weather_condition": _check_weather_condition,
    "soil_condition": _check_soil_condition,
    "forecast_condition": _check_forecast_condition,
    "irrigation_trigger": _check_irrigation_trigger,
}


def check_rule(
    rule: dict[str, Any],
    cycles: list[list[dict[str, Any]]],
    weather_lookup: WeatherLookup | None = None,
) -> CheckResult:
    """Führe einen einzelnen Regel-Check über alle Zyklen aus.

    Args:
        rule: Regel-Dict aus ``kartoffel_regeln.json``.
        cycles: Liste der Anbauzyklen (jeweils normalisierte Events).
        weather_lookup: Optionale Wetterdaten-Tabelle (Datum → WeatherData).
            Wird für Wetter-Regeln (KAR-030 … KAR-035) benötigt. Ohne Lookup
            werden Wetter-Regeln als ``weather_skip`` markiert
            (Abwärtskompatibilität für die Baseline-Suite).

    Returns:
        ``CheckResult`` mit allen Verletzungen über alle Zyklen.
    """
    if rule["id"] in _WEATHER_RULE_IDS and weather_lookup is None:
        return _weather_skip(rule)
    check_type = rule["check"]["type"]
    handler = _CHECK_DISPATCH.get(check_type)
    if handler is None:
        return CheckResult(
            violations=[
                Violation(
                    rule_id=rule["id"],
                    severity="hard",
                    message=f"Kein Checker für check.type='{check_type}' registriert.",
                )
            ]
        )
    all_violations: list[Violation] = []
    for cycle in cycles:
        all_violations.extend(handler(cycle, rule, weather_lookup))
    return CheckResult(violations=all_violations)


def hard_violations(result: CheckResult) -> list[Violation]:
    """Filtere harte Verletzungen aus einem CheckResult."""
    return [v for v in result.violations if v.severity == "hard"]


def soft_violations(result: CheckResult) -> list[Violation]:
    """Filtere weiche Verletzungen aus einem CheckResult."""
    return [v for v in result.violations if v.severity == "soft"]


__all__ = [
    "Violation",
    "CheckResult",
    "WeatherLookup",
    "load_rules",
    "normalize_events",
    "segment_cycles",
    "check_rule",
    "hard_violations",
    "soft_violations",
]
