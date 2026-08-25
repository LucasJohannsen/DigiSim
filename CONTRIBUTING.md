# Contributing zu DigiSim 🌱

Vielen Dank für dein Interesse, zu DigiSim beizutragen! Dieses Dokument erklärt, wie du am besten zum Projekt beitragen kannst.

## 📋 Inhaltsverzeichnis
- [Code of Conduct](#code-of-conduct)
- [Wie kann ich beitragen?](#wie-kann-ich-beitragen)
- [Entwicklungs-Workflow](#entwicklungs-workflow)
- [Issue-Guidelines](#issue-guidelines)
- [Pull-Request-Prozess](#pull-request-prozess)
- [Code-Style](#code-style)
- [Testing](#testing)

---

## 🤝 Code of Conduct

Dieses Projekt folgt einem freundlichen und respektvollen Umgang. Wir erwarten von allen Contributors:
- Respektvolle und konstruktive Kommunikation
- Offenheit für Feedback und unterschiedliche Perspektiven
- Fokus auf das Beste für das Projekt und die Community

---

## 💡 Wie kann ich beitragen?

### 1. **Issues melden**
- **Bugs**: Nutze das [Bug-Report-Template](.github/ISSUE_TEMPLATE/bug_report.md)
- **Features**: Nutze das [Feature-Request-Template](.github/ISSUE_TEMPLATE/feature_request.md)
- **Fragen**: Nutze das [Question-Template](.github/ISSUE_TEMPLATE/question.md)

### 2. **Code beitragen**
- Suche nach Issues mit dem Label `good first issue` für Einstieg
- Issues mit `help wanted` sind besonders willkommen

### 3. **Dokumentation verbessern**
- Tippfehler korrigieren
- Unklare Abschnitte verbessern
- Beispiele hinzufügen

---

## 🔧 Entwicklungs-Workflow

### Setup
1. **Fork das Repository** auf GitHub
2. **Clone deinen Fork**:
   ```bash
   git clone https://github.com/DEIN-USERNAME/DigiSim.git
   cd DigiSim
   ```
3. **Erstelle ein virtuelles Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   .venv\Scripts\activate     # Windows
   ```
4. **Installiere Dependencies**:
   ```bash
   pip install .
   pip install -e ".[dev]"  # Falls dev-dependencies vorhanden
   ```

### Branch-Strategie
- **`dev`**: Entwicklungs-Branch (Default, protected — CI muss grün)
- **`test`**: Auslieferungs-Branch (protected — PR + CI erforderlich, auto-Deploy)
- **Feature-Branches**: `feature/MSX-XX-beschreibung` (vom `dev`)
- **Bug-Fix-Branches**: `fix/MSX-XX-beschreibung` (vom `dev`)

**Deploy-Flow:** `dev` → PR → `test` → Docker-Build → SSH-Deploy auf Server

### Workflow
1. **Erstelle einen Branch** vom `dev`-Branch:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b feature/SIM-XX-mein-feature
   ```
2. **Mache deine Änderungen** und committe regelmäßig:
   ```bash
   git add .
   git commit -m "SIM-XX: Beschreibung der Änderung"
   ```
3. **Pushe deinen Branch**:
   ```bash
   git push origin feature/SIM-XX-mein-feature
   ```
4. **Erstelle einen Pull Request** auf GitHub

---

## 📝 Issue-Guidelines

### Bevor du ein Issue erstellst
- [ ] Suche nach existierenden Issues (auch geschlossene)
- [ ] Prüfe die [Dokumentation](README.md)
- [ ] Stelle sicher, dass du die neueste Version verwendest

### Gute Issue-Beschreibungen enthalten
- **Klare Titel**: `[BUG] Simulation stürzt bei leeren Feldern ab`
- **Reproduktionsschritte**: Wie kann der Fehler nachgestellt werden?
- **Erwartetes vs. tatsächliches Verhalten**
- **Umgebung**: OS, Python-Version, DigiSim-Version
- **Logs/Screenshots**: Falls relevant

---

## 🔀 Pull-Request-Prozess

### Vor dem PR
1. **Verlinke das zugehörige Issue** (erstelle eins, falls keins existiert)
2. **Lokale Checks ausführen**:
   ```bash
   uv run ruff check .       # Linting
   uv run ruff format --check .  # Format-Check
   uv run pytest -q           # Test-Suite
   ```
3. **Aktualisiere die Dokumentation** (README, Docstrings, etc.)
4. **Prüfe Code-Style** (siehe unten)

### PR-Checkliste
- [ ] Branch ist aktuell mit `dev`
- [ ] `ruff check .` ist clean
- [ ] `ruff format --check .` ist clean
- [ ] Alle Tests laufen erfolgreich (`pytest`)
- [ ] Dokumentation ist aktualisiert
- [ ] Commit-Messages sind aussagekräftig
- [ ] PR-Template ist vollständig ausgefüllt

### Review-Prozess
1. **Automatische CI-Checks**: ruff + format + mypy + pytest
2. **Formale Prüfung** durch Maintainer:
   - Ist das Issue verlinkt?
   - Ist die Dokumentation aktuell?
   - Sind Breaking Changes dokumentiert?
3. **Code-Review** durch Entwickler (technische Prüfung)
4. **Merge** nach Approval

### Nach dem Merge
- Feature-Branch kann gelöscht werden
- Das verlinkte Issue wird geschlossen
- Für Deploy: PR `dev` → `test` erstellen + mergen (triggert Docker-Build + Auto-Deploy)

---

## 🎨 Code-Style

### Python-Konventionen
- **PEP 8** Style Guide befolgen
- **Type Hints** verwenden wo sinnvoll
- **Docstrings** für Klassen und Funktionen:
  ```python
  def calculate_irrigation(soil_moisture: float, threshold: float) -> bool:
      """
      Bestimmt, ob Bewässerung notwendig ist.
      
      Args:
          soil_moisture: Aktuelle Bodenfeuchte (0.0 - 1.0)
          threshold: Schwellenwert für Bewässerung
          
      Returns:
          True wenn Bewässerung notwendig, sonst False
      """
      return soil_moisture < threshold
  ```

### Naming Conventions
- **Klassen**: `PascalCase` (z.B. `SimulationRunner`)
- **Funktionen/Variablen**: `snake_case` (z.B. `get_field_data`)
- **Konstanten**: `UPPER_SNAKE_CASE` (z.B. `MAX_FIELD_SIZE`)
- **Private Members**: `_leading_underscore` (z.B. `_internal_state`)

### Imports
- Standard Library zuerst
- Third-Party Libraries danach
- Lokale Imports zuletzt
- Alphabetisch sortiert innerhalb der Gruppen

```python
import datetime
import json
from typing import List, Optional

import simpy
from dataclasses import dataclass

from models.field import Field
from services.config_service import ConfigService
```

---

## 🧪 Testing

### Manuelle Tests
Vor jedem PR solltest du mindestens folgende Szenarien testen:
```bash
# Einzelfeld-Simulation
python main.py
> pick_field
> run

# Batch-Simulation (falls implementiert)
python main.py
> run_batch
```

### Unit-Tests (falls vorhanden)
```bash
pytest tests/
pytest tests/ -v  # Verbose output
pytest tests/test_irrigation.py  # Einzelne Datei
```

### Test-Coverage
- Neue Features sollten Tests haben
- Bug-Fixes sollten Regressions-Tests haben
- Ziel: >80% Coverage (langfristig)

---

## 🏷️ Labels und Priorisierung

### Issue-Labels
- **`bug`**: Fehler im bestehenden Code
- **`enhancement`**: Feature-Requests und Verbesserungen
- **`documentation`**: Dokumentations-Updates
- **`question`**: Fragen zur Verwendung
- **`mvp`**: Kritisch für MVP-Funktionalität
- **`post-mvp`**: Features für spätere Versionen
- **`help wanted`**: Community-Hilfe erwünscht
- **`good first issue`**: Einsteigerfreundlich

### Prioritäten
1. **Critical**: Blocker für MVP-Release
2. **High**: MVP-Features
3. **Medium**: Nice-to-have für MVP
4. **Low**: Post-MVP

---

## 📦 Release-Prozess

### Versioning
DigiSim folgt [Semantic Versioning](https://semver.org/):
- **`0.1.x`**: MVP-Iterationen (Breaking Changes erlaubt)
- **`0.2.x`**: Post-MVP-Features (ESDB-Anbindung)
- **`1.0.0`**: Erste stabile Version

### Release-Workflow
1. Alle MVP-Ziele erreicht?
2. Critical Bugs geschlossen?
3. README und CHANGELOG aktualisiert?
4. Tag in GitHub erstellt
5. Release Notes veröffentlicht

---

## 🎯 MVP-Scope

### Im MVP-Scope (prioritär)
✅ Simulation eines Beispielfeldes  
✅ Mindestens eine Maßnahme (Düngung/Pflanzenschutz)  
✅ JSON-Output der Zeitreihen  
✅ Lokale Speicherung  
✅ Fehlerbehandlung bei ungültigen Eingaben  

### Außerhalb MVP-Scope (Post-MVP)
❌ Komplexe Batch-Konfigurationen  
❌ Import echter Betriebsdaten  
❌ ESDB-Anbindung  
❌ Web-UI  
❌ Multi-User-Features  

---

## 🙋 Fragen?

- **Dokumentation**: Siehe [README.md](README.md)
- **Issues**: [GitHub Issues](https://github.com/FARMWISSEN/DigiSim/issues)
- **Diskussionen**: [GitHub Discussions](https://github.com/FARMWISSEN/DigiSim/discussions)

---

## 🙏 Danke!

Jeder Beitrag zählt – egal ob Code, Dokumentation, Bug-Reports oder Feedback. Danke, dass du DigiSim unterstützt! 🌱
