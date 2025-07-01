# DigiSim

## Minimal Viable Product (MVP)

Das MVP von DigiSim verfolgt das Ziel, eine erste lauffähige Version der Simulationssoftware bereitzustellen, die den Kernnutzen demonstriert und als Grundlage für Feedback und Weiterentwicklung dient.

**Ziele des MVP:**
- Simuliert ein Beispiel-Feld und einen vordefinierten Zeitraum (z.B. eine Saison, feste Parameter).
- Bildet mindestens eine Maßnahme (z.B. Düngung oder Pflanzenschutz) mit einfachen Regeln ab.
- Gibt die simulierten Ereignisse als strukturierte Zeitreihe im JSON-Format aus.
- Speichert die Daten lokal als JSON-Datei (die spätere Anbindung an die Event Sourcing Datenbank erfolgt auf Basis dieses Formats).
- Erkennt und meldet Fehler bei ungültigen Eingaben verständlich.

**Nicht enthalten im MVP:**
- Keine komplexe Konfiguration oder Batch-Funktionalität.
- Kein Import echter Betriebsdaten.
- Keine Anbindung an die ESDB (diese folgt später).

**Technische Hinweise:**
- Die Architektur ist modular, um spätere Erweiterungen (weitere Felder, Maßnahmen, Validierung, UI) zu erleichtern.
- Das JSON-Ausgabeformat wird so gestaltet, dass es für die spätere Integration in die ESDB geeignet ist.

---