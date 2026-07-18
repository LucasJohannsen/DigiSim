# Fachregelwerk Kartoffel (Norddeutschland)

**Version:** 1.0 (Baseline) · **Rolle:** Agrar-Domänenexperte & Simulation-Auditor
**Geltungsbereich:** Kartoffelanbau (Speise-/Frühkartoffel, z. B. Sorte Belana), Norddeutschland.
**Maschinenlesbare Variante:** `documentation/fachregeln/kartoffel_regeln.json`

Jede Regel hat: **ID**, **Beschreibung**, **Typ** (hart = Verstoß ist fachlich falsch; weich = Verstoß ist unplausibel/unüblich), **Prüfkriterium** (gegen Event-Exporte prüfbar; Worktype-IDs aus `models/worktypes.py`).

**Quellenlage:** Agronomische Eckwerte aus öffentlicher Beratungsliteratur (ISIP, top agrar, agrarheute, LWK Niedersachsen/NRW, LfL Bayern, Fachverband Feldberegnung); wo keine belastbare Quelle vorliegt, ist die Regel als **[Annahme]** gekennzeichnet. Worktype-Zuordnung und Phasen aus `models/worktypes.py`, `documentation/WORKTYPES.md`, `config/planting_plan_potato.json`.

**Relevante Worktypes:** Grubbern=6, Eggen/Kreiseln=7, Separieren=28, Min. Düngung=23, Org. Düngung=13, Transport=18, Kartoffeln legen=26, Spritzen=14, Beregnen=15, Dammfräsen/Häufeln=29, Kraut schlagen=30, Roden=27, Verladen/Lagerung=58.

---

## 1. Zulässige Operationsreihenfolge

Referenzablauf (Pflichtschritte **fett**, optionale kursiv):

**Grubbern (6)** → *Eggen/Kreiseln (7)* → *Separieren (28)* → *Grunddüngung Kali/P (23)* → **Legen (26)** (inkl. *Pflanzguttransport (18)* davor) → **N-Düngung (23)** → **Häufeln/Dammaufbau (29)** → *Pflege: Spritzen (14), Beregnen (15)* → **Sikkation/Krautabtötung (14 mit Kat. 26 bzw. 30)** → **Roden (27)** → *Abtransport/Einlagerung (58)*.

| ID | Beschreibung | Typ | Prüfkriterium |
|---|---|---|---|
| KAR-001 | Die Phasenreihenfolge Bodenbearbeitung → Legen → Bestandespflege → Sikkation → Roden → Einlagerung darf nicht invertiert werden. | hart | Für jedes Feld und jeden Anbauzyklus: max(Datum wt∈{5,6,7,28}) < Datum(wt=26) < min(Datum Pflege wt∈{23-Kopfdüngung,29}) ≤ Datum(Sikkation) < Datum(wt=27) ≤ Datum(wt=58). |
| KAR-002 | Kein Legen (26) vor Abschluss der Saatbettbereitung (Grubbern/Eggen/Separieren). | hart | Kein Event wt∈{5,6,7,28} mit Datum > Datum(wt=26) und < Datum(wt=27) desselben Zyklus. |
| KAR-003 | Innerhalb eines Tages muss die geplante Sequenz eingehalten werden; Zeitstempel dürfen die Reihenfolge nicht invertieren (z. B. Pflanzguttransport **vor** Legen). | hart | Bei Events gleichen Datums: start_date(seq n) ≤ start_date(seq n+1); konkret: start(wt=18, Pflanzguttransport) < start(wt=26). |
| KAR-004 | Roden (27) erst nach Krautabtötung (Sikkation: Spritzen wt=14 mit Herbizid-Kategorie 26 auf abreifenden Bestand, oder Kraut schlagen wt=30). | hart | Vor jedem wt=27-Event existiert ≥1 Sikkations-Event; Datum(Sikkation) < Datum(wt=27). |
| KAR-005 | Nach dem Roden keine Bestandesmaßnahmen mehr (Spritzen, Beregnen, Düngen, Häufeln) im selben Zyklus. | hart | Kein Event wt∈{13,14,15,23,29} mit Datum > Datum(wt=27) und vor Zyklusende. |
| KAR-006 | Keine Beregnung (15) vor dem Legen (26). | hart | Kein wt=15-Event mit Datum < Datum(wt=26) desselben Zyklus. |
| KAR-007 | Häufeln/Dammaufbau (29) vor Reihenschluss, d. h. ca. 10–25 Tage nach dem Legen. [Annahme: Spanne] | weich | 10 ≤ Datum(wt=29) − Datum(wt=26) ≤ 25 Tage. |
| KAR-008 | Erste Herbizidmaßnahme (Vorauflauf, Kat. 26) zwischen Legen und Auflaufen, d. h. 0–14 Tage nach dem Legen. [Annahme] | weich | 0 ≤ Datum(1. wt=14 mit Kat. 26) − Datum(wt=26) ≤ 14 Tage. |

## 2. Zeitfenster je Operation (Norddeutschland)

| ID | Beschreibung | Typ | Prüfkriterium |
|---|---|---|---|
| KAR-010 | Legen (26) im Zeitfenster April–Mai (Ende März nur in frühen Lagen). | hart (Monate 3–5), weich (4–5) | Monat(wt=26) ∈ {4,5}; Monat=3 → weiche Verletzung; sonst harte. |
| KAR-011 | Roden (27) im Zeitfenster September–Oktober (Frühkartoffeln ab August möglich). | hart (8–11), weich (9–10) | Monat(wt=27) ∈ {9,10}; 8 oder 11 → weich; sonst hart. |
| KAR-012 | Frühjahrsbodenbearbeitung (6,7,28) Februar–April; keine Saatbettbereitung im Winter (Dez–Jan) oder Sommer. [Annahme] | weich | Monat(wt∈{6,7,28}) ∈ {2,3,4} (bis Anfang 5 tolerierbar). |
| KAR-013 | Beregnung (15) nur in der Vegetationszeit Mai–September. | hart | Monat(wt=15) ∈ {5..9}. |
| KAR-014 | Pflanzenschutzspritzungen (14) nur April–September (Vorauflauf bis Sikkation). | hart | Monat(wt=14) ∈ {4..9}. |
| KAR-015 | Alle Events eines Anbauzyklus liegen in einer konsistenten Zeitachse: Datum/Jahr der Events muss dem Simulationsdatum entsprechen; Export chronologisch konsistent (kein Jahr-Sprung innerhalb eines Zyklus). | hart | Sortierung nach start_date entspricht Erzeugungsreihenfolge; Jahresdifferenz zwischen aufeinanderfolgenden Events eines Zyklus = 0 (außer Jahreswechsel Dez→Jan). |
| KAR-016 | Grunddüngung (Kali/P, wt=23 Kat. 34) vor dem Legen im Frühjahr; N-Kopfdüngung (Kat. 33) nach dem Legen bis Reihenschluss (≤ 35 Tage nach Legen). [Annahme: Spanne] | weich | Kali/P: Datum < Datum(wt=26); N: 0 < Datum − Datum(wt=26) ≤ 35 Tage. |

## 3. Mindest-/Höchstabstände zwischen Operationen

| ID | Beschreibung | Typ | Prüfkriterium |
|---|---|---|---|
| KAR-020 | Sikkation → Roden: mindestens **14 Tage** Wartezeit (Quickdown/Shark: frühestens 14 Tage vor Ernte; Schalenfestigkeit 2–5 Wochen nach Krautregulierung). Quelle: agrarheute/LWK. | hart | Datum(wt=27) − Datum(letzte Sikkation) ≥ 14 Tage; weich: 14–35 Tage. |
| KAR-021 | Abstand zwischen Fungizidspritzungen (Krautfäule): min. 3 Tage, üblich 7–10, max. 14 Tage in der Hauptsaison. Quelle: ISIP/LTZ. | hart (≥3), weich (5–14) | 3 ≤ Δt aufeinanderfolgender wt=14-Events (Kat. 27) ; weiche Verletzung wenn Δt < 5 oder > 14 Tage. |
| KAR-022 | Beregnungsintervall: min. 4 Tage zwischen Gaben (bei 20–25 mm-Gabe rechnerisch 5–8 Tage). Quelle: top agrar. | weich | Δt aufeinanderfolgender wt=15-Events ≥ 4 Tage. |
| KAR-023 | Letzte Saatbettbereitung (Separieren/Eggen) max. 21 Tage vor dem Legen (Boden setzt sich sonst / Unkrautauflauf). [Annahme] | weich | Datum(wt=26) − Datum(letztes wt∈{7,28}) ≤ 21 Tage. |
| KAR-024 | Sikkationsdurchgänge: Shark max. 1×/Jahr, Quickdown max. 2× (Abstand 4–7 Tage); zweite Gabe ≥ 14 Tage vor Ernte. Quelle: agrarheute. | hart | Anzahl Sikkations-Events je Mittel je Zyklus prüfen; Δt(Quickdown-Gaben) ∈ [4,7]; letzte Gabe ≥ 14 Tage vor wt=27. |
| KAR-025 | Zwischen Grubbern (6) und Eggen/Kreiseln (7) min. 1 Tag Abstand (Abtrocknung). [Annahme] | weich | Δt ≥ 1 Tag. |

## 4. Wetter-/Bodenabhängigkeiten

Diese Regeln setzen voraus, dass Entscheidungen an Wetter-/Bodendaten desselben Simulationsjahres gekoppelt sind.

| ID | Beschreibung | Typ | Prüfkriterium |
|---|---|---|---|
| KAR-030 | Kein Spritzen (14) bei Regen (Niederschlag > 1 mm während der Applikation bzw. am Applikationstag > 5 mm) und bei Wind > 5 m/s (Abdriftminderung). | hart | Join wt=14-Events mit Wetterdaten des Event-Datums: Niederschlag/Wind unter Schwellwert. |
| KAR-031 | Keine Beregnung (15), wenn innerhalb der nächsten 3–4 Tage signifikanter Niederschlag (kumuliert > 10 mm) prognostiziert ist. | hart | Für jedes wt=15-Event: Prognose-Niederschlag (t..t+3) < 10 mm. |
| KAR-032 | Keine Bodenbearbeitung (5,6,7,28) und kein Legen (26) auf nassem/wassergesättigtem Boden (Bodenfeuchte > ~90 % nFK bzw. Vortagesniederschlag > 10 mm). [Annahme: Schwellwerte] | hart | Join mit Bodenfeuchte-/Niederschlagsdaten am Event-Datum. |
| KAR-033 | Legen (26) erst ab Bodentemperatur ≥ 8 °C in Legetiefe. [Annahme: Standardempfehlung] | weich | Bodentemperatur am Legetermin ≥ 8 °C. |
| KAR-034 | Beregnungsauslösung nur bei Unterschreiten des nFK-Schwellwerts (Speise-/Frühkartoffel: 50 % nFK; mittelfrüh/spät: 40 % nFK), berechnet aus Feuchtedaten **desselben Jahres/Standorts** wie die Simulation. Quelle: top agrar/LWK Nds. | hart | Bodenfeuchte am Vortag des wt=15-Events < Schwellwert; Datenjahr = Simulationsjahr. |
| KAR-035 | Keine Sikkation bei starker Trockenheit/Hitzestress und nicht auf taunassen Bestand; nach Starkregen Abtrocknung abwarten (Lentizellen). Quelle: BLW/kartoffelanbauberatung. | weich | Sikkations-Event nicht an Tagen mit Tmax > 30 °C oder Niederschlag am selben Tag. |

## 5. Plausible Mengen und Häufigkeiten

| ID | Beschreibung | Typ | Prüfkriterium |
|---|---|---|---|
| KAR-040 | Beregnungseinzelgabe: 20–30 mm (Früh-/Speisekartoffel 20–25 mm); hart: ≥ 10 mm und ≤ 40 mm (kleinere Gaben verdunsten wirkungslos, größere waschen N aus). Quelle: top agrar. | hart (10–40), weich (20–30) | 10 ≤ application_amount(wt=15, Einheit mm) ≤ 40; weich: 20–30. |
| KAR-041 | Saisonale Beregnungssumme: ca. 60–150 mm Zusatzwasser (leichte Böden Norddeutschland: 70–140 mm). Quelle: Fachverband Feldberegnung. | weich | Σ application_amount(wt=15) je Zyklus ∈ [30, 180] mm. |
| KAR-042 | Anzahl Pflanzenschutzdurchgänge: gesamt 8–18 je Saison; davon Fungizide (Krautfäule, Kat. 27) ca. 6–14, Insektizide (Kat. 28) 0–3, Herbizide (Kat. 26) 1–3 (inkl. Sikkation ≤ 2 zusätzliche). [Annahme: Spannen, konsistent mit Protection-Plänen] | weich | Zählung wt=14-Events je Kategorie je Zyklus. |
| KAR-043 | N-Düngung gesamt ≤ 220 kg N/ha (Belana/Speise: typ. 120–180 kg N/ha inkl. Nmin); KAS 0,46 t/ha ≈ 124 kg N/ha plausibel. [Annahme: DüV-Richtwerte] | hart | Σ N aus wt=23-Events (Kat. 33) ≤ 220 kg N/ha. |
| KAR-044 | Pflanzgutmenge 2,0–3,0 t/ha. [Annahme: Standard Speisekartoffel] | weich | application_amount(wt=26)/Fläche ∈ [2,3] t/ha. |
| KAR-045 | Arbeitszeiten plausibel: Feldarbeiten beginnen zwischen 05:00 und 20:00; keine durchgehende Einzeloperation > 18 h; Ende spätestens Folgetag früh. [Annahme] | weich | start_date-Uhrzeit ∈ [05:00, 20:00]; end_date − start_date ≤ 18 h. |
| KAR-046 | Genau **ein** Lege-Event (26) und **ein** Rode-Event (27) je Feld und Anbauzyklus (Teilflächen aktuell nicht modelliert). | hart | Anzahl wt=26 = Anzahl wt=27 = 1 je Zyklus. |
| KAR-047 | Wachstumsdauer: Roden ca. 90–150 Tage nach dem Legen (Belana, mittelfrüh: ~100–120 Tage; `growth_duration=90` ist untere Grenze). | weich | 90 ≤ Datum(wt=27) − Datum(wt=26) ≤ 150 Tage. |

---

## Hinweise zu Annahmen

- Alle mit **[Annahme]** markierten Spannen sind praxisübliche Richtwerte ohne Einzelquelle; sie sollten mit dem Product Owner / einer Fachberatung validiert werden.
- Wetter-/Bodenregeln (KAR-030 ff.) sind derzeit in der Simulation **nicht prüfbar aus den Event-Exporten allein**, da die Entscheidungslogik keine Wetterkopplung besitzt; sie definieren das Soll für die Weiterentwicklung.
- Belege der Recherche: ISIP (Spritzabstände 7–10 Tage), top agrar (Beregnung 20–30 mm, Intervall 5–8 Tage, Auslösung 50 %/40 % nFK), agrarheute (Quickdown/Shark ≥ 14 Tage vor Ernte, Shark 1×/Jahr), LWK NRW (Schalenfestigkeit 2–5 Wochen nach Krautregulierung), Fachverband Feldberegnung (Zusatzwasserbedarf 70–140 mm auf leichten Böden).
