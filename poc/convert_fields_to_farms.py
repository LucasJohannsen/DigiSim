#!/usr/bin/env python3
"""
DigiZert API Fields to DigiSim Farms Converter
==============================================

Konvertiert response_fields.json (DigiZert API Format) 
zu config/farms.json (DigiSim Format)

Usage:
    python poc/convert_fields_to_farms.py
"""

import json
from pathlib import Path
from typing import Dict, Any
import math

def calculate_distance_to_barn(field_center: Dict[str, float], barn_location: Dict[str, float] = None) -> float:
    """
    Berechnet die Entfernung vom Feld zur Scheune in km.
    Falls keine Scheune definiert ist, wird eine Standard-Scheune angenommen.
    """
    if barn_location is None:
        # Standard-Scheune in der Nähe der Felder (Mittelwert der Koordinaten)
        barn_location = {"x": 7.900, "y": 49.540}
    
    # Haversine-Formel für Entfernungsberechnung
    lat1, lon1 = math.radians(field_center["y"]), math.radians(field_center["x"])
    lat2, lon2 = math.radians(barn_location["y"]), math.radians(barn_location["x"])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Erdradius in km
    r = 6371
    return round(r * c, 2)

def determine_soil_type(area: float) -> str:
    """
    Bestimmt den Bodentyp basierend auf der Feldgröße.
    Einfache Heuristik für Demo-Zwecke.
    """
    if area < 3.0:
        return "clay"
    elif area < 7.0:
        return "loam"
    else:
        return "sand"

def convert_field_to_digisim_format(field: Dict[str, Any]) -> Dict[str, Any]:
    """
    Konvertiert ein DigiZert API Field zu DigiSim Format.
    """
    return {
        "id": field["exa_id"],  # Verwende exa_id als eindeutige ID
        "name": field["name"],
        "distance_to_barn": calculate_distance_to_barn(field["center"]),
        "area": field["area"],
        "soil_type": determine_soil_type(field["area"])
    }

def convert_response_to_farms(response_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Konvertiert die komplette DigiZert API Response zu DigiSim farms.json Format.
    """
    fields = response_data.get("results", [])
    
    # Gruppiere Felder nach Enterprise (falls mehrere Betriebe vorhanden)
    enterprises = {}
    for field in fields:
        enterprise_id = field.get("enterprise", 1)
        if enterprise_id not in enterprises:
            enterprises[enterprise_id] = []
        enterprises[enterprise_id].append(field)
    
    # Erstelle Farms-Struktur
    farms = []
    for enterprise_id, enterprise_fields in enterprises.items():
        farm = {
            "id": enterprise_id,
            "name": f"DigiZert Betrieb {enterprise_id}",
            "fields": [convert_field_to_digisim_format(field) for field in enterprise_fields]
        }
        farms.append(farm)
    
    return {"farms": farms}

def main():
    """
    Hauptfunktion: Lädt response_fields.json und konvertiert zu farms.json
    """
    # Pfade definieren
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    input_file = script_dir / "response_fields.json"
    output_file = project_root / "config" / "farms_from_api.json"
    backup_file = project_root / "config" / "farms_backup.json"
    
    # Prüfe ob Input-Datei existiert
    if not input_file.exists():
        print(f"❌ Fehler: {input_file} nicht gefunden!")
        return
    
    # Backup der aktuellen farms.json erstellen
    current_farms = project_root / "config" / "farms.json"
    if current_farms.exists():
        print(f"📦 Backup erstellt: {backup_file}")
        with open(current_farms, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=4, ensure_ascii=False)
    
    # Lade und konvertiere Daten
    print(f"📖 Lade DigiZert API Daten: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        response_data = json.load(f)
    
    print(f"🔄 Konvertiere {len(response_data.get('results', []))} Felder...")
    farms_data = convert_response_to_farms(response_data)
    
    # Speichere konvertierte Daten
    print(f"💾 Speichere DigiSim Format: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(farms_data, f, indent=4, ensure_ascii=False)
    
    # Statistiken ausgeben
    total_fields = sum(len(farm["fields"]) for farm in farms_data["farms"])
    total_area = sum(field["area"] for farm in farms_data["farms"] for field in farm["fields"])
    
    print("\n✅ Konvertierung abgeschlossen!")
    print("📊 Statistiken:")
    print(f"   • Betriebe: {len(farms_data['farms'])}")
    print(f"   • Felder: {total_fields}")
    print(f"   • Gesamtfläche: {total_area:.2f} ha")
    
    # Zeige erste 3 Felder als Vorschau
    print("\n🔍 Vorschau der ersten Felder:")
    for farm in farms_data["farms"][:1]:  # Nur erster Betrieb
        for field in farm["fields"][:3]:  # Nur erste 3 Felder
            print(f"   • {field['name']}: {field['area']} ha, {field['soil_type']}, {field['distance_to_barn']} km zur Scheune")

if __name__ == "__main__":
    main()
