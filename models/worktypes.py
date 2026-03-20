"""
DigiZert Worktype Constants

Diese Konstanten definieren die offiziellen Worktype-IDs aus DigiZert.
WICHTIG: Diese IDs dürfen NICHT mit application_category IDs aus category.json verwechselt werden!

Verwendung:
    from models.worktypes import WorkType
    operation.worktype = WorkType.PLANTING
"""

from enum import IntEnum


class WorkType(IntEnum):
    """
    Offizielle Worktype-IDs aus DigiZert.
    
    Diese IDs werden für das 'worktype'-Feld in FieldOperation und FieldOperationEvent verwendet.
    Sie beschreiben die Art der durchgeführten Arbeit (z.B. Pflügen, Säen, Spritzen).
    
    NICHT zu verwechseln mit application_category IDs (26-34), die in category.json definiert sind
    und die Art des ausgebrachten Materials beschreiben (z.B. Herbizid, Fungizid, Dünger).
    """
    
    LEERFAHRT = 0
    DEADHEAD = 0  # Alias für LEERFAHRT
    
    RUNDBALLEN_PRESSEN = 1
    QUADERBALLEN_PRESSEN = 2
    PRESSWICKELN = 3
    BALLEN_WICKELN = 4
    
    PFLUEGEN = 5
    GRUBBERN = 6
    EGGEN = 7
    TIEFGRUBBERN = 8
    FRAESEN = 9
    WALZEN = 10
    
    SAEEN = 11
    PFLANZEN = 12
    
    ORGANISCHE_DUENGUNG = 13
    SPRITZEN = 14
    BEREGNEN = 15
    
    MAEHEN = 16
    WENDEN = 17
    TRANSPORTIEREN = 18
    KEHREN = 19
    SCHNEE_RAEUMEN = 20
    SALZ_STREUEN = 21
    HACKEN = 22
    
    MINERALISCHE_DUENGUNG = 23
    
    GUELLE_PUMPEN = 24
    GUELLE_RUEHREN = 25
    
    KARTOFFELN_LEGEN = 26
    RODEN = 27
    SEPARIEREN = 28
    DAMMFRAESEN = 29
    KRAUT_SCHLAGEN = 30
    SCHWADEN = 31
    STRIEGELN = 32
    SCHLEPPEN = 33
    MULCHEN = 34
    
    KEHREN_ALT = 35  # Duplikat von 19
    SCHNEE_FRAESEN = 36
    GUELLECONTAINER_UMSETZEN = 37
    BEETFORMEN = 38
    FUETTERN = 39
    
    HOLZ_RUECKEN = 40
    HOLZ_SAEGEN = 41
    HOLZ_SPALTEN = 42
    BAUMSTUMPFFRAESEN = 43
    
    SCHUETTGUT_LADEN = 44
    PALETTEN_LADEN = 45
    BALLEN_LADEN = 46
    CCM_MUEHLE_UMSETZEN = 47
    SCHIEBEN = 48
    FRONT_HECKGEWICHT = 49
    
    DRESCHEN = 50
    HAECKSELN = 51
    HOCHDRUCKBALLEN_PRESSEN = 52
    ENTBLAETTERN = 53
    PLANIEREN = 54
    BODENBEARBEITUNG = 55
    GEHOELZPFLEGE = 56
    PFLEGE_MONTAGEARBEITEN = 57
    VERLADEN = 58
    BE_UND_ENTLADEN = 59
    WASCHEN = 60
    VERDICHTEN = 61


# Häufig verwendete Worktype-Gruppen
SOIL_PREPARATION_WORKTYPES = [
    WorkType.PFLUEGEN,
    WorkType.GRUBBERN,
    WorkType.EGGEN,
    WorkType.TIEFGRUBBERN,
    WorkType.FRAESEN,
    WorkType.WALZEN,
]

PLANTING_WORKTYPES = [
    WorkType.SAEEN,
    WorkType.PFLANZEN,
    WorkType.KARTOFFELN_LEGEN,
]

FERTILIZATION_WORKTYPES = [
    WorkType.ORGANISCHE_DUENGUNG,
    WorkType.MINERALISCHE_DUENGUNG,
]

PROTECTION_WORKTYPES = [
    WorkType.SPRITZEN,
]

HARVEST_WORKTYPES = [
    WorkType.DRESCHEN,
    WorkType.RODEN,
    WorkType.HAECKSELN,
]

TRANSPORT_WORKTYPES = [
    WorkType.TRANSPORTIEREN,
    WorkType.VERLADEN,
    WorkType.BE_UND_ENTLADEN,
]

# Niedrig-Prioritäts-Worktypes (für DecisionManager)
LOW_PRIORITY_WORKTYPES = [
    WorkType.SPRITZEN,
    WorkType.BEREGNEN,
]
