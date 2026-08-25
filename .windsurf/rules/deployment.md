---
trigger: model_decision
description: deployment workflow dev -> test with CI/CD pipeline, Docker, GHCR, SSH-Deploy
---
Deploy-Workflow für DigiSim (verbindlich)

DigiSim nutzt eine automatisierte CI/CD-Pipeline. Code wird nicht manuell auf den Server deployed. Der folgende Weg ist immer zu gehen.

Branch-Modell

| Branch | Schutz | Zweck | Deploy |
|---|---|---|---|
| dev | protected (CI muss grün) | Entwicklung | nein |
| test | protected (PR + CI erforderlich) | Auslieferung | Docker-Deploy auf Server |

Es gibt keinen main-Branch mehr. test ist der Deploy-Branch.

Regulärer Deploy-Weg (immer gehen)

1. Feature-Branch von dev erstellen: feature/<milestone>-<issue>-<kurzname>
2. Änderungen committen, pushen
3. PR nach dev erstellen, CI muss grün sein (ruff check, ruff format --check, mypy non-blocking, pytest)
4. PR nach dev mergen
5. PR von dev nach test erstellen
6. CI auf test muss grün sein
7. PR nach test mergen — das triggert automatisch:
   a. Docker Build & Push -> ghcr.io/lucasjohannsen/digisim:latest
   b. Deploy to Test Server (SSH: git reset --hard origin/test, docker compose pull, docker compose up -d, healthcheck max 120s)

Nie tun

- Nie direkt auf test pushen (Branch-Protection verhindert es, aber auch manuell nicht versuchen)
- Nie manuell per SSH auf den Server einloggen und Code pullen/builden — die Pipeline macht das
- Nie docker compose build auf dem Server ausführen — Image kommt vom GHCR
- Nie den dev-Branch überspringen (kein direkter PR feature -> test)
- Nie Secrets (SSH-Keys, PATs, API-Tokens) in den Code committen — GitHub Secrets nutzen

CI-Checks (muessen gruen sein)

- uv sync --frozen (Lockfile-Drift wird abgefangen)
- ruff check . (Linting)
- ruff format --check . (Formatierung)
- mypy (Type-Check, Phase 1 non-blocking)
- pytest (Test-Suite, alle Tests muessen gruen sein)

Lokale Checks vor jedem Commit

- uv run ruff check .
- uv run ruff format --check .
- uv run pytest -q

Server-Details (nur zur Info, nicht manuell aendern)

- Host: 78.47.90.30 (ubuntu-digizert, Ubuntu 24.04)
- Deploy-User: lucas (Gruppe docker, kein sudo noetig)
- Deploy-Pfad: /home/lucas/DigiSim
- Image: ghcr.io/lucasjohannsen/digisim:latest
- GHCR-Login: docker login ghcr.io (PAT mit read:packages, bereits eingerichtet)
- Container: digisim (docker compose, healthcheck via scripts/healthcheck.py)
- GitHub Secrets: TEST_SSH_HOST, TEST_SSH_USER, TEST_SSH_KEY, TEST_DEPLOY_PATH

Wenn der Deploy fehlschlaegt

1. GitHub Actions Logs pruefen (gh run list --branch test, gh run view <id> --log)
2. Haeufige Ursachen:
   - CI rot: ruff/pytest fehlgeschlagen -> Code fixen, neuen PR nach dev dann nach test
   - Docker-Build rot: Dockerfile-Fehler oder setup-buildx-action Problem
   - Deploy rot: SSH-Key falsch, Server nicht erreichbar, Health-Check Timeout
3. Nur im Notfall manuell eingreifen — danach die Pipeline-Ursache beheben

Hotfix-Szenario

Fuer dringende Fixes den gleichen Weg gehen (feature-branch -> dev -> test).
Branch-Protection fuer test kann temporaer per Admin-Merge umgangen werden
(gh pr merge --admin), aber CI sollte trotzdem vorher gruen sein.
