# DigiSim MS4 Examples

This directory contains example scripts demonstrating the new MS4 features.

## Examples

### 1. Replay Simulation
**File:** `replay_example.py`

Re-simulate past time periods to recover missing data.

```bash
python documentation/examples/replay_example.py
```

### 2. Fast-Forward Simulation
**File:** `fast_forward_example.py`

Rapidly simulate multiple days or full seasons for data generation.

```bash
python documentation/examples/fast_forward_example.py
```

### 3. Weather Data Integration
**File:** `weather_adapter_example.py`

Fetch real weather data from Open-Meteo API.

```bash
python documentation/examples/weather_adapter_example.py
```

### 4. Soil Parameters
**File:** `soil_adapter_example.py`

Load field-specific soil parameters from configuration files.

```bash
python documentation/examples/soil_adapter_example.py
```

## CLI Usage

You can also use the CLI commands directly:

```bash
# Replay simulation
replay --from 2025-04-01 --to 2025-10-31 --output json

# Fast-forward simulation
fast_forward --days 500 --output json
```

## Documentation

For detailed documentation, see:
- [MS4 Features Documentation](../MS4_FEATURES.md)
- [Main README](../../README.md)
