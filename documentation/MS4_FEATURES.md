# MS4 Features Documentation

This document describes the new features implemented in Milestone 4 (MS4) - Erweiterte Simulationsplattform.

## Overview

MS4 introduces three major enhancements to DigiSim:

1. **Replay Simulation** (Issue #44) - Re-simulate past time periods deterministically
2. **Fast-Forward Simulation** (Issue #45) - Rapid simulation for data generation
3. **External Data Sources** (Issue #46) - Integration of weather, soil, and sensor data

---

## 1. Replay Simulation (Issue #44)

### Purpose

Enable DigiSim to re-simulate a past time period deterministically, useful for:
- Catching up with missed simulation periods
- Validating simulation accuracy against historical data
- Generating historical event data for analysis

### Usage

#### CLI Command

```bash
replay --from YYYY-MM-DD --to YYYY-MM-DD [--output json|stdout|digizert]
```

#### Example

```bash
# Replay the 2024 growing season
replay --from 2024-01-01 --to 2024-12-31 --output json

# Replay with stdout output
replay --from 2024-03-01 --to 2024-06-30 --output stdout
```

#### Python API

```python
from scheduler.replay_runner import ReplayRunner
from models.sim_context import SimContext
import datetime

context = SimContext(
    field_size=10.0,
    crop_type="potato",
    variety="Agria",
    field_id=12345,
    field_name="Test Field",
    # ... other parameters
)

runner = ReplayRunner(
    context=context,
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 12, 31),
    output_target="json",
)

events = runner.run()
```

### Features

- **Deterministic**: Same inputs always produce same outputs
- **Isolated**: Does not modify live simulation state
- **Configurable Output**: JSON export, DigiZert dispatch, or stdout
- **Domain Events**: Captures both integration and domain events

### Output

Replay generates two files:
- `replay_<field_id>_<start>_to_<end>.json` - Integration events (FieldOperationEvents)
- `replay_<field_id>_<start>_to_<end>_domain_events.json` - Domain events

---

## 2. Fast-Forward Simulation (Issue #45)

### Purpose

Run multiple days or full seasons as fast as possible without real-time delay, useful for:
- Demo preparation
- Synthetic data generation
- Testing seasonal scenarios
- Batch processing

### Usage

#### CLI Command

```bash
fast_forward --days N [--output json|stdout|digizert]
```

#### Example

```bash
# Fast-forward 365 days (full season)
fast_forward --days 365 --output json

# Fast-forward 30 days with stdout output
fast_forward --days 30 --output stdout
```

#### Python API

```python
from scheduler.fast_forward_runner import FastForwardRunner
from models.sim_context import SimContext

context = SimContext(
    field_size=10.0,
    crop_type="potato",
    variety="Agria",
    field_id=12345,
    field_name="Test Field",
    # ... other parameters
)

runner = FastForwardRunner(context=context, n_days=365, output_target="json")

events = runner.run()
```

### Features

- **No Real-Time Delay**: Decoupled from wall-clock time
- **Progress Reporting**: Updates every 30 days
- **Memory Efficient**: Periodic flushing for large simulations
- **Error Handling**: Continues on errors, tracks error count

### Output

Fast-forward generates:
- `fast_forward_<field_id>_<n_days>days_<timestamp>.json` - All generated events
- Console summary with event type breakdown

---

## 3. External Data Sources (Issue #46)

### Purpose

Integrate real-world data sources to make simulations more realistic:
- Weather data (precipitation, temperature, evapotranspiration)
- Soil parameters (field capacity, wilting point, pH)
- Sensor data (soil moisture, leaf wetness)

### Architecture

All data source adapters implement the `DataSourceAdapter` interface:

```python
class DataSourceAdapter(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        """Check if data source is available."""
        pass
    
    @abstractmethod
    def get_data(self, **kwargs) -> Dict[str, Any]:
        """Fetch data from external source."""
        pass
    
    @abstractmethod
    def get_fallback_data(self, **kwargs) -> Dict[str, Any]:
        """Get fallback data when source is unavailable."""
        pass
```

### Weather Data Adapters

#### Open-Meteo Weather Adapter

Free weather data without API key requirement.

```python
from services.weather_adapters import OpenMeteoWeatherAdapter
import datetime

adapter = OpenMeteoWeatherAdapter(latitude=52.52, longitude=13.41, enabled=True)

weather_data = adapter.get_data(
    start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 12, 31)
)

# Output format:
# {
#     'dates': [datetime.date, ...],
#     'precipitation': [float, ...],  # mm per day
#     'temperature_min': [float, ...],  # °C
#     'temperature_max': [float, ...],  # °C
#     'evapotranspiration': [float, ...],  # mm per day
#     'source': 'open-meteo'
# }
```

**Features:**
- Historical weather data
- Weather forecasts
- No API key required
- Automatic fallback to synthetic data

**Configuration:**

Set via environment variables or code:

```python
# Enable/disable via constructor
adapter = OpenMeteoWeatherAdapter(
    latitude=52.52,
    longitude=13.41,
    enabled=True,  # or False to use fallback
)
```

#### DWD Weather Adapter

Placeholder for future DWD (Deutscher Wetterdienst) integration.

```python
from services.weather_adapters import DWDWeatherAdapter

adapter = DWDWeatherAdapter(
    station_id="12345",
    enabled=False,  # Not yet implemented
)
```

### Soil Data Adapters

#### Config File Soil Adapter

Load soil parameters from JSON configuration files.

```python
from services.soil_adapters import ConfigFileSoilAdapter

adapter = ConfigFileSoilAdapter(config_path="config/soil_parameters.json", enabled=True)

soil_data = adapter.get_data(field_id="12345")

# Output format:
# {
#     'soil_type': 'sandy_loam',
#     'field_capacity': 180.0,  # % nFK
#     'wilting_point': 80.0,    # % nFK
#     'organic_matter': 2.5,    # %
#     'ph': 6.5,
#     'source': 'config_file'
# }
```

**Configuration File Format:**

Create `config/soil_parameters.json`:

```json
{
  "12345": {
    "soil_type": "sandy_loam",
    "field_capacity": 180,
    "wilting_point": 80,
    "organic_matter": 2.5,
    "ph": 6.5
  },
  "67890": {
    "soil_type": "clay_loam",
    "field_capacity": 220,
    "wilting_point": 120,
    "organic_matter": 3.0,
    "ph": 7.0
  }
}
```

**Create Default Config:**

```python
adapter = ConfigFileSoilAdapter()
adapter.create_default_config()
```

### Fallback Behavior

All adapters implement automatic fallback:

1. **Primary**: Try to fetch from external source
2. **Fallback**: If unavailable, use synthetic/default data
3. **Logging**: All fallback usage is logged

This ensures simulations always run, even without external connectivity.

---

## Configuration

### Environment Variables

Create a `.env` file (copy from `.env.example`):

```bash
# Weather Data
WEATHER_ADAPTER_ENABLED=true
WEATHER_LATITUDE=52.52
WEATHER_LONGITUDE=13.41

# Soil Data
SOIL_ADAPTER_ENABLED=true
SOIL_CONFIG_PATH=config/soil_parameters.json
```

### Dependencies

New dependencies for MS4:

```bash
# Install via uv
uv pip install requests

# Or via pip
pip install requests
```

---

## Testing

Run tests for new features:

```bash
# Test replay runner
pytest tests/test_replay_runner.py -v

# Test fast-forward runner
pytest tests/test_fast_forward_runner.py -v

# Test weather adapters
pytest tests/test_weather_adapters.py -v

# Test soil adapters
pytest tests/test_soil_adapters.py -v

# Run all MS4 tests
pytest tests/test_replay_runner.py tests/test_fast_forward_runner.py tests/test_weather_adapters.py tests/test_soil_adapters.py -v
```

---

## Integration with Existing Code

### CalendarDrivenRunner

Both ReplayRunner and FastForwardRunner use `CalendarDrivenRunner` internally:

```python
# ReplayRunner creates a modified context
replay_context = copy.deepcopy(self.context)
replay_context.start_date = replay_start_date

self.calendar_runner = CalendarDrivenRunner(context=replay_context, event_bus=self.event_bus)

# FastForwardRunner uses context as-is
self.calendar_runner = CalendarDrivenRunner(context=self.context, event_bus=self.event_bus)
```

### Event-Driven Architecture

All new features follow the event-driven core principle:

1. **Domain Events**: Internal simulation events (DailyTickStarted, OperationApproved, etc.)
2. **Integration Events**: External events (FieldOperationEvent for DigiZert)
3. **Event Bus**: Optional, injected via constructor

---

## Examples

### Example 1: Generate Full Season Data

```python
from scheduler.fast_forward_runner import FastForwardRunner
from models.sim_context import SimContext
import datetime

context = SimContext(
    field_size=15.0,
    soil_type="sandy_loam",
    start_date=datetime.datetime(2024, 1, 1),
    crop_type="potato",
    variety="Agria",
    field_id=12345,
    field_name="Demo Field",
    fuel_variation=0.1,
)

runner = FastForwardRunner(context=context, n_days=365, output_target="json")

events = runner.run()
print(f"Generated {len(events)} events for full season")
```

### Example 2: Replay with Weather Data

```python
from scheduler.replay_runner import ReplayRunner
from services.weather_adapters import OpenMeteoWeatherAdapter
from models.sim_context import SimContext
import datetime

# Get weather data
weather_adapter = OpenMeteoWeatherAdapter(latitude=52.52, longitude=13.41)

weather_data = weather_adapter.get_data(
    start_date=datetime.date(2024, 3, 1), end_date=datetime.date(2024, 9, 30)
)

# Run replay
context = SimContext(
    field_size=10.0,
    crop_type="potato",
    variety="Agria",
    field_id=12345,
    field_name="Weather Test Field",
    # ... other parameters
)

runner = ReplayRunner(
    context=context,
    start_date=datetime.date(2024, 3, 1),
    end_date=datetime.date(2024, 9, 30),
    output_target="json",
)

events = runner.run()
```

### Example 3: Custom Soil Parameters

```python
from services.soil_adapters import ConfigFileSoilAdapter

# Create custom soil config
adapter = ConfigFileSoilAdapter(config_path="config/my_soil_params.json")

# Get soil data for field
soil_data = adapter.get_data(field_id="12345")

# Use in simulation context
context = SimContext(
    field_size=10.0,
    soil_type=soil_data["soil_type"],
    # ... other parameters
)
```

---

## Troubleshooting

### Replay Not Deterministic

Ensure:
- Same `SimContext` configuration
- Same random seed (if using randomization)
- Same planting plan configuration

### Fast-Forward Memory Issues

For very large simulations (>1000 days):
- Reduce `flush_interval` parameter
- Use JSON output instead of keeping all events in memory
- Consider splitting into multiple smaller runs

### Weather API Unavailable

- Check internet connectivity
- Verify latitude/longitude are valid
- Check Open-Meteo API status
- Fallback data will be used automatically

### Soil Config Not Found

- Verify `config/soil_parameters.json` exists
- Use `adapter.create_default_config()` to create template
- Check file permissions
- Fallback data will be used automatically

---

## Future Enhancements

Planned improvements for future milestones:

1. **DigiZert Integration**: Direct dispatch of replay/fast-forward results
2. **DWD Weather Adapter**: Full implementation of DWD data source
3. **Sensor Data Adapter**: Real-time sensor integration
4. **Streaming Output**: Memory-efficient streaming for very large simulations
5. **Parallel Execution**: Multi-field parallel fast-forward
6. **State Snapshots**: Save/restore simulation state for replay

---

## References

- Issue #44: [Replay Simulation for past time periods](https://github.com/LucasJohannsen/DigiSim/issues/44)
- Issue #45: [Fast-Forward Simulation for multiple days or full seasons](https://github.com/LucasJohannsen/DigiSim/issues/45)
- Issue #46: [Integration of additional external data sources](https://github.com/LucasJohannsen/DigiSim/issues/46)
- MS3 Documentation: Domain Events and Event-Driven Architecture
- Open-Meteo API: https://open-meteo.com/
- DWD Open Data: https://opendata.dwd.de/
