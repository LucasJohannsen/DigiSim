# P1-3 — Beregnungs-Events auf korrekte Zeitachse (Befund B1)

## Problem

`IrrigationSimulator._create_irrigation_event()` konstruiert das Event-Datum aus `context.start_date.year` + Tag-des-Jahres (`services/irrigation_service.py`, Z. 100). Läuft die Saison — wie durch B2 üblich — im Folgejahr, tragen Beregnungs-Events das **falsche Jahr**. Beleg (Referenzlauf 990001): Beregnung datiert 2026-06-05…2026-07-22, obwohl Legen am 2027-05-10 erfolgte; im Export erscheinen die Beregnungen dadurch VOR dem Legen.

Verletzte Regeln: KAR-015 (konsistente Zeitachse, hart), KAR-006 (keine Beregnung vor dem Legen, hart).

## Zielverhalten

Beregnungs-Events tragen exakt das Simulationsdatum des Ticks, an dem sie entschieden wurden. Die Zeitachse eines Zyklus ist chronologisch konsistent, unabhängig davon, in welchem Jahr die Saison liegt.

## Lösungsdesign

- **API-Änderung** `IrrigationSimulator`: `get_candidate_operations(date: datetime.date)` statt `day: int` (ebenso `apply_irrigation`, `get_status_for_day` intern). Der Tag-des-Jahres für die Indizierung der Moisture-Arrays wird **intern** aus dem Datum abgeleitet (`date.timetuple().tm_yday`), das Event-Datum aus dem übergebenen Datum (12:00 Uhr wie bisher).
- Aufrufer `CalendarDrivenRunner.tick()` übergibt `date` direkt (Z. 114–116, 142–147); die dortige `day_of_year`-Berechnung entfällt.
- Legacy-Methode `trigger_irrigation()` analog anpassen oder — falls ohne Verwender — entfernen (vorher mit `grep` prüfen; Verwender in Tests migrieren).
- **Achtung Mehrjahres-Läufe:** Die Moisture-Arrays sind 1 Jahr lang (365/366). Beim Ableiten von `day_of_year` Index-Überlauf abfangen (bestehendes `IndexError`-Handling beibehalten). Die grundsätzliche Jahres-/Standortkopplung der Daten ist B4 (Paket P3) und NICHT Teil dieses Issues.
- Kein neues Domain Event nötig — die Entscheidung läuft bereits über `OperationConsidered/Approved/Applied`; es wird nur die Datumsermittlung korrigiert.

## Betroffene Dateien

- `services/irrigation_service.py` (Signaturen, Datumslogik)
- `scheduler/calendar_driven_runner.py` (Aufrufstellen)
- Tests: `tests/test_irrigation_candidates.py`, `tests/test_calendar_driven_runner_irrigation.py`, `tests/test_irrigation_state_persistence.py`

## Akzeptanzkriterien

1. In einem FF-Lauf über eine volle Saison gilt für jedes wt=15-Event: `start_date.date()` == Datum des Ticks, in dem es approved wurde (Abgleich über Domain Events `OperationApplied`)
2. Kein wt=15-Event datiert vor dem Lege-Event desselben Zyklus (KAR-006)
3. Export ist chronologisch konsistent: kein Jahres-Rücksprung innerhalb eines Zyklus (KAR-015)
4. Plausibilitätstest xfail-B1 (P1-1) wird grün → Marker entfernen
5. State-Persistenz (Snapshot save/load) funktioniert unverändert

## Testhinweise

Unit-Test: `get_candidate_operations(datetime.date(2027, 6, 5))` liefert Event mit `start_date` „2027-06-05 12:00:00". Regressionstest mit Saison im Folgejahr (Start 2026-01-01, Legen 2027) — genau das Szenario des Referenzlaufs.

## Aufwandsschätzung

S

## Abhängigkeiten

Unabhängig implementierbar; Akzeptanzkriterium 2 ist erst nach P1-2 sinnvoll end-to-end prüfbar (vorher liegt die Saison ohnehin im Folgejahr).
