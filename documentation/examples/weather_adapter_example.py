#!/usr/bin/env python3
"""
Example: Using Weather Data Adapters.

Use case: Integrate real weather data into simulations.
"""
import datetime
from services.weather_adapters import OpenMeteoWeatherAdapter


def main():
    # Initialize weather adapter
    adapter = OpenMeteoWeatherAdapter(
        latitude=52.52,  # Berlin
        longitude=13.41,
        enabled=True
    )
    
    # Check availability
    if adapter.is_available():
        print("✅ Weather API is available")
    else:
        print("⚠️  Weather API unavailable, will use fallback data")
    
    # Fetch weather data
    weather_data = adapter.get_data(
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31)
    )
    
    print(f"\nWeather data retrieved:")
    print(f"  Source: {weather_data['source']}")
    print(f"  Days: {len(weather_data['dates'])}")
    print(f"  Avg precipitation: {sum(weather_data['precipitation'])/len(weather_data['precipitation']):.1f} mm/day")
    print(f"  Avg temp (max): {sum(weather_data['temperature_max'])/len(weather_data['temperature_max']):.1f} °C")


if __name__ == "__main__":
    main()
