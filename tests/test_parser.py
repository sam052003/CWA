"""Tests for CWA JSON Parser and fixture structures."""

import json
from pathlib import Path
import pytest

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "cwa_f_c0032_005_sample.json"


@pytest.fixture
def sample_json_data():
    """Load sample JSON fixture data."""
    assert FIXTURE_PATH.exists(), f"Fixture file not found: {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_fixture_root_and_dataset(sample_json_data):
    """Verify root has cwaopendata and dataset exists."""
    assert "cwaopendata" in sample_json_data, "Root missing 'cwaopendata' key"
    cwa_data = sample_json_data["cwaopendata"]
    assert "dataset" in cwa_data, "'cwaopendata' missing 'dataset' key"


def test_fixture_location_count_and_names(sample_json_data):
    """Verify locations list has exactly 22 items and each has locationName."""
    dataset = sample_json_data["cwaopendata"]["dataset"]
    locations = dataset.get("location", [])
    assert len(locations) == 22, f"Expected 22 locations, got {len(locations)}"

    for loc in locations:
        assert "locationName" in loc, "Location missing 'locationName'"
        assert isinstance(loc["locationName"], str) and len(loc["locationName"]) > 0


def test_fixture_weather_elements_and_time_structure(sample_json_data):
    """Verify first location has Wx, MaxT, MinT and time contains startTime/endTime/parameter."""
    first_loc = sample_json_data["cwaopendata"]["dataset"]["location"][0]
    elements_map = {
        el.get("elementName"): el for el in first_loc.get("weatherElement", [])
    }

    # Verify at least Wx, MaxT, MinT exist
    for required_name in ("Wx", "MaxT", "MinT"):
        assert required_name in elements_map, f"Missing required weatherElement '{required_name}'"

        el_obj = elements_map[required_name]
        time_list = el_obj.get("time", [])
        assert isinstance(time_list, list) and len(time_list) > 0, f"'{required_name}' missing time list"

        for time_entry in time_list:
            assert "startTime" in time_entry, f"'{required_name}' time entry missing startTime"
            assert "endTime" in time_entry, f"'{required_name}' time entry missing endTime"
            assert "parameter" in time_entry, f"'{required_name}' time entry missing parameter"
            assert isinstance(time_entry["parameter"], dict), "parameter must be a dict"


def test_fixture_parameter_fields(sample_json_data):
    """Verify specific parameter structures for Wx, MaxT, and MinT."""
    first_loc = sample_json_data["cwaopendata"]["dataset"]["location"][0]
    elements_map = {
        el.get("elementName"): el for el in first_loc.get("weatherElement", [])
    }

    # Wx parameter has parameterName and parameterValue
    for time_entry in elements_map["Wx"]["time"]:
        param = time_entry["parameter"]
        assert "parameterName" in param
        assert "parameterValue" in param

    # MaxT and MinT have parameterName and parameterUnit == 'C'
    for temp_elem in ("MaxT", "MinT"):
        for time_entry in elements_map[temp_elem]["time"]:
            param = time_entry["parameter"]
            assert "parameterName" in param
            assert param.get("parameterUnit") == "C"
