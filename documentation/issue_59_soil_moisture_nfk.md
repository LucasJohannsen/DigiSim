# Issue #59: SoilMoisture-Daten als nfk_pct an DigiZert senden

## Problem

DigiSim sendete `vwc` (Volumetric Water Content in %) an den Endpunkt
`POST /api/v1/simulator/soil-moisture/`. Die Werte sind aber DWD-nFK%
(nutzbare Feldkapazität in %), keine VWC%. DigiZert rechnet diese falsch um.

## Lösung

Statt `vwc` sende `nfk_pct` pro Measurement:

```json
{
  "field": 42,
  "depth": 15,
  "measurements": [
    {"timestamp": "2026-05-01T00:00:00", "nfk_pct": 50.0},
    {"timestamp": "2026-05-02T00:00:00", "nfk_pct": 45.3}
  ]
}
```

## Regeln

- Pro Measurement **entweder** `vwc` (echte Sensoren, %) **oder** `nfk_pct`
  (DWD/simuliert, %) – nicht beide
- `nfk_pct` = DWD "nutzbare Feldkapazität" direkt, keine Umrechnung nötig
- Werte-Bereich: 0-100%
- Tiefe 15cm und 30cm wie bisher
- Endpunkt, Auth, Bulk-Limit (10000) unchanged

## DigiSim-Implementierung

- `SoilMoistureMeasurement.nfk_pct` (statt `vwc`)
- `DigiZertDataClient.send_soil_moisture_data()` sendet `nfk_pct` im Payload
- `DataTransferService` mappt DWD/Synthetic-Werte auf `nfk_pct`
- DWD-Sentinel (-9999) wird gefiltert, Fallback auf SyntheticMoistureProvider

## Referenz

Siehe `SIMULATOR_API.md` im DigiZert-Repo, Abschnitt "SoilMoistureData".
