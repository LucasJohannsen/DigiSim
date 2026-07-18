# P1-1 — Plausibilitäts-Testsuite gegen Fachregeln (Fundament)

## Problem

Es gibt keine automatisierte Prüfung, ob die Simulation fachlich plausible Event-Sequenzen erzeugt. Alle Befunde des Baseline-Audits (`documentation/fachregeln/maengelbericht_baseline.md`, B1–B14) wurden manuell gefunden. Ohne dauerhafte Testsuite können Regressionen unbemerkt zurückkehren und der Fortschritt der fachlichen Härtung ist nicht messbar.

## Zielverhalten

Eine pytest-Testsuite simuliert deterministisch ganze Saisons und prüft die erzeugten Events gegen das maschinenlesbare Fachregelwerk (`documentation/fachregeln/kartoffel_regeln.json`). Jede harte Regelverletzung ist ein Testfehler. Bekannte, noch nicht behobene Befunde sind als `xfail` mit Befund-ID markiert und werden beim Fix auf „grün erwartet" umgestellt.

## Lösungsdesign

- Neues Testmodul `tests/test_plausibility_kartoffel.py` + Hilfsmodul `tests/plausibility/` (Regel-Checker)
- **Fixture (module-scoped):** `FastForwardRunner` mit fixiertem Seed (`random.seed(42)`, `np.random.seed(42)`), SimContext wie Referenzlauf (Feld 990001, Belana, 20 ha, Start 01.01., n_days so, dass eine volle Saison inkl. Roden/Lagerung enthalten ist), eigenem `DomainEventBus`; liefert Integration Events + Domain-Event-Historie
- **Regel-Checker:** liest `kartoffel_regeln.json`; pro Regelkategorie eine Prüf-Funktion:
  - Reihenfolge (KAR-001…008): Sortierung nach `start_date`, Phasen-/Sequenzvergleich
  - Zeitfenster (KAR-010…016): Monat der Events je Worktype
  - Abstände (KAR-020…025): Δt zwischen Event-Paaren (z. B. letzte Sikkation → Roden ≥ 14 d)
  - Mengen (KAR-040…047): `application_amount`-Grenzen, Zählungen je Zyklus
  - Wetterregeln (KAR-030…035) sind erst nach P3 prüfbar → zunächst `skip` mit Verweis
- **Domain-Event-Checks:** genau 1× `CropCycleStarted` und 1× `HarvestCompleted` je Zyklus (deckt B13 ab)
- Kein Netzwerkzugriff im Test: MoistureDataService-Fallback akzeptieren bzw. lokale `dwd_data/` nutzen

## Betroffene Dateien

- Neu: `tests/test_plausibility_kartoffel.py`, `tests/plausibility/__init__.py`, `tests/plausibility/rule_checks.py`
- Keine Änderungen an Produktionscode

## Akzeptanzkriterien

1. `pytest tests/test_plausibility_kartoffel.py` läuft ohne Netzwerk deterministisch durch (< 2 min)
2. Alle harten Regeln aus `kartoffel_regeln.json` haben eine Prüf-Funktion oder einen begründeten `skip`
3. Bekannte Befunde B1, B2, B3, B5, B6, B7, B13, B14 schlagen als `xfail(strict=True)` mit Befund-ID an — d. h. der Test wird FEHLSCHLAGEN, sobald der Bug behoben ist, und erinnert daran, das xfail zu entfernen
4. Die Suite läuft in der bestehenden CI (GitHub Actions) mit

## Testhinweise

Referenz-Baseline zum Gegenprüfen der Checker-Logik: `export/fast_forward/audit_baseline_990001_760days.json` (+ `_domain_events.json`), Seed 42.

## Aufwandsschätzung

M

## Abhängigkeiten

Keine — bewusst VOR den Fixes umsetzen (P1-2 bis P1-4 stellen dann je ein xfail auf grün).
