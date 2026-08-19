#!/usr/bin/env python3
"""
Example: Using Soil Data Adapters.

Use case: Load field-specific soil parameters from configuration.
"""

from services.soil_adapters import ConfigFileSoilAdapter


def main():
    # Initialize soil adapter
    adapter = ConfigFileSoilAdapter(config_path="config/soil_parameters.json", enabled=True)

    # Create default config if it doesn't exist
    if not adapter.is_available():
        print("Creating default soil parameters config...")
        adapter.create_default_config()

    # Load soil data for a specific field
    soil_data = adapter.get_data(field_id="12345")

    print("Soil parameters for field 12345:")
    print(f"  Source: {soil_data['source']}")
    print(f"  Soil type: {soil_data['soil_type']}")
    print(f"  Field capacity: {soil_data['field_capacity']} % nFK")
    print(f"  Wilting point: {soil_data['wilting_point']} % nFK")
    print(f"  Organic matter: {soil_data['organic_matter']} %")
    print(f"  pH: {soil_data['ph']}")


if __name__ == "__main__":
    main()
