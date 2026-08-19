import json

from services.soil_adapters import ConfigFileSoilAdapter


class TestConfigFileSoilAdapter:
    """Test suite for ConfigFileSoilAdapter (Issue #46)."""

    def test_adapter_initialization(self):
        """Test adapter can be initialized."""
        adapter = ConfigFileSoilAdapter()

        assert adapter.enabled is True

    def test_adapter_disabled(self):
        """Test adapter respects enabled flag."""
        adapter = ConfigFileSoilAdapter(enabled=False)

        assert adapter.is_available() is False

    def test_fallback_data(self):
        """Test fallback data generation."""
        adapter = ConfigFileSoilAdapter(enabled=False)

        data = adapter.get_fallback_data(field_id="12345")

        assert "soil_type" in data
        assert "field_capacity" in data
        assert "wilting_point" in data
        assert "organic_matter" in data
        assert "ph" in data
        assert data["source"] == "fallback"

    def test_get_data_with_config(self, tmp_path):
        """Test loading data from config file."""
        # Create test config file
        config_path = tmp_path / "soil_params.json"
        config_data = {
            "12345": {
                "soil_type": "sandy_loam",
                "field_capacity": 180,
                "wilting_point": 80,
                "organic_matter": 2.5,
                "ph": 6.5,
            }
        }

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        adapter = ConfigFileSoilAdapter(config_path=str(config_path))

        data = adapter.get_data(field_id="12345")

        assert data["soil_type"] == "sandy_loam"
        assert data["field_capacity"] == 180.0
        assert data["wilting_point"] == 80.0
        assert data["organic_matter"] == 2.5
        assert data["ph"] == 6.5
        assert data["source"] == "config_file"

    def test_get_data_missing_field(self, tmp_path):
        """Test fallback when field not in config."""
        # Create test config file
        config_path = tmp_path / "soil_params.json"
        config_data = {"12345": {"soil_type": "sandy_loam", "field_capacity": 180}}

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        adapter = ConfigFileSoilAdapter(config_path=str(config_path))

        # Request data for non-existent field
        data = adapter.get_data(field_id="99999")

        # Should return fallback
        assert data["source"] == "fallback"

    def test_create_default_config(self, tmp_path):
        """Test creating default configuration file."""
        config_path = tmp_path / "soil_params.json"

        adapter = ConfigFileSoilAdapter(config_path=str(config_path))
        adapter.create_default_config()

        # Check file was created
        assert config_path.exists()

        # Check content is valid JSON
        with open(config_path) as f:
            data = json.load(f)

        assert "example_field_1" in data
        assert "example_field_2" in data

    def test_config_caching(self, tmp_path):
        """Test that config is cached after first load."""
        config_path = tmp_path / "soil_params.json"
        config_data = {"12345": {"soil_type": "sandy_loam", "field_capacity": 180}}

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        adapter = ConfigFileSoilAdapter(config_path=str(config_path))

        # First load
        data1 = adapter.get_data(field_id="12345")

        # Modify file
        config_data["12345"]["field_capacity"] = 200
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        # Second load should use cache
        data2 = adapter.get_data(field_id="12345")

        assert data1["field_capacity"] == data2["field_capacity"]

    def test_validation_numeric_conversion(self, tmp_path):
        """Test that numeric values are converted to float."""
        config_path = tmp_path / "soil_params.json"
        config_data = {
            "12345": {
                "soil_type": "sandy_loam",
                "field_capacity": "180",  # String instead of number
                "wilting_point": 80,
            }
        }

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        adapter = ConfigFileSoilAdapter(config_path=str(config_path))
        data = adapter.get_data(field_id="12345")

        # Should be converted to float
        assert isinstance(data["field_capacity"], float)
        assert data["field_capacity"] == 180.0
