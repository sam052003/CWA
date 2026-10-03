"""Tests for CWA JSON Parser and fixture structures."""

import json
from pathlib import Path
import pytest

from app.parsers.cwa_parser import CWAParser, parse_cwa_forecast

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "cwa_f_c0032_005_sample.json"


@pytest.fixture
def sample_json_data():
    """Load sample JSON fixture data."""
    assert FIXTURE_PATH.exists(), f"Fixture file not found: {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ==============================================================================
# Fixture Raw Structure Tests
# ==============================================================================


def test_fixture_root_and_dataset(sample_json_data):
    """Verify root has cwaopendata and dataset exists."""
    assert "cwaopendata" in sample_json_data
    cwa_data = sample_json_data["cwaopendata"]
    assert "dataset" in cwa_data


def test_fixture_location_count_and_names(sample_json_data):
    """Verify locations list has exactly 22 items and each has locationName."""
    dataset = sample_json_data["cwaopendata"]["dataset"]
    locations = dataset.get("location", [])
    assert len(locations) == 22

    for loc in locations:
        assert "locationName" in loc
        assert isinstance(loc["locationName"], str) and len(loc["locationName"]) > 0


def test_fixture_weather_elements_and_time_structure(sample_json_data):
    """Verify first location has Wx, MaxT, MinT and time contains startTime/endTime/parameter."""
    first_loc = sample_json_data["cwaopendata"]["dataset"]["location"][0]
    elements_map = {
        el.get("elementName"): el for el in first_loc.get("weatherElement", [])
    }

    for required_name in ("Wx", "MaxT", "MinT"):
        assert required_name in elements_map
        el_obj = elements_map[required_name]
        time_list = el_obj.get("time", [])
        assert isinstance(time_list, list) and len(time_list) > 0

        for time_entry in time_list:
            assert "startTime" in time_entry
            assert "endTime" in time_entry
            assert "parameter" in time_entry
            assert isinstance(time_entry["parameter"], dict)


# ==============================================================================
# Parser Tests with Real Fixture
# ==============================================================================


def test_real_fixture_successful_parse(sample_json_data):
    """1. Verify real fixture can be parsed into normalized records."""
    records = parse_cwa_forecast(sample_json_data)
    assert isinstance(records, list)
    assert len(records) == 330  # 22 locations * 15 intervals


def test_all_22_regions_present(sample_json_data):
    """2. Verify all 22 regions are present in parsed records."""
    records = parse_cwa_forecast(sample_json_data)
    regions = sorted(set(r["region_name"] for r in records))
    assert len(regions) == 22
    assert "臺北市" in regions
    assert "高雄市" in regions
    assert "連江縣" in regions


def test_taipei_first_record_fields(sample_json_data):
    """3. Verify Taipei first record fields match exact expected values from fixture."""
    records = parse_cwa_forecast(sample_json_data)
    taipei_records = [r for r in records if r["region_name"] == "臺北市"]
    assert len(taipei_records) == 15

    # Look up raw Taipei data from fixture to compare
    taipei_raw = [
        l for l in sample_json_data["cwaopendata"]["dataset"]["location"]
        if l["locationName"] == "臺北市"
    ][0]
    raw_elements = {
        el["elementName"]: el for el in taipei_raw["weatherElement"]
    }
    expected_start = raw_elements["Wx"]["time"][0]["startTime"]
    expected_end = raw_elements["Wx"]["time"][0]["endTime"]
    expected_wx = raw_elements["Wx"]["time"][0]["parameter"]["parameterName"]
    expected_mint = int(raw_elements["MinT"]["time"][0]["parameter"]["parameterName"])
    expected_maxt = int(raw_elements["MaxT"]["time"][0]["parameter"]["parameterName"])

    first = taipei_records[0]
    assert first["dataset_id"] == "F-C0032-005"
    assert first["region_name"] == "臺北市"
    assert first["start_time"] == expected_start
    assert first["end_time"] == expected_end
    assert first["weather"] == expected_wx
    assert first["min_temp"] == expected_mint
    assert first["max_temp"] == expected_maxt


def test_records_schema_and_types(sample_json_data):
    """4 & 5. Verify every record has required keys and min_temp/max_temp are int."""
    records = parse_cwa_forecast(sample_json_data)
    expected_keys = {
        "dataset_id",
        "region_name",
        "start_time",
        "end_time",
        "weather",
        "min_temp",
        "max_temp",
    }

    for record in records:
        assert set(record.keys()) == expected_keys
        assert isinstance(record["dataset_id"], str)
        assert isinstance(record["region_name"], str)
        assert isinstance(record["start_time"], str)
        assert "+08:00" in record["start_time"]
        assert isinstance(record["end_time"], str)
        assert "+08:00" in record["end_time"]
        assert isinstance(record["weather"], str)
        assert isinstance(record["min_temp"], int)
        assert isinstance(record["max_temp"], int)


# ==============================================================================
# Parser Tests for Missing Fields & Anomaly Handling
# ==============================================================================


def _make_dummy_cwa_data(weather_elements, location_name="測試市"):
    """Helper to build a small synthetic CWA payload."""
    return {
        "cwaopendata": {
            "dataset": {
                "location": [
                    {
                        "locationName": location_name,
                        "weatherElement": weather_elements,
                    }
                ]
            }
        }
    }


def test_missing_wx_omits_interval():
    """6. Verify interval missing Wx is omitted from parsed records."""
    t_interval = {"startTime": "2026-10-03T18:00:00+08:00", "endTime": "2026-10-04T06:00:00+08:00"}
    elements = [
        {"elementName": "MaxT", "time": [{**t_interval, "parameter": {"parameterName": "28"}}]},
        {"elementName": "MinT", "time": [{**t_interval, "parameter": {"parameterName": "22"}}]},
    ]
    data = _make_dummy_cwa_data(elements)
    records = parse_cwa_forecast(data)
    assert records == []


def test_missing_mint_omits_interval():
    """7. Verify interval missing MinT is omitted from parsed records."""
    t_interval = {"startTime": "2026-10-03T18:00:00+08:00", "endTime": "2026-10-04T06:00:00+08:00"}
    elements = [
        {"elementName": "Wx", "time": [{**t_interval, "parameter": {"parameterName": "多雲"}}]},
        {"elementName": "MaxT", "time": [{**t_interval, "parameter": {"parameterName": "28"}}]},
    ]
    data = _make_dummy_cwa_data(elements)
    records = parse_cwa_forecast(data)
    assert records == []


def test_missing_maxt_omits_interval():
    """8. Verify interval missing MaxT is omitted from parsed records."""
    t_interval = {"startTime": "2026-10-03T18:00:00+08:00", "endTime": "2026-10-04T06:00:00+08:00"}
    elements = [
        {"elementName": "Wx", "time": [{**t_interval, "parameter": {"parameterName": "多雲"}}]},
        {"elementName": "MinT", "time": [{**t_interval, "parameter": {"parameterName": "22"}}]},
    ]
    data = _make_dummy_cwa_data(elements)
    records = parse_cwa_forecast(data)
    assert records == []


def test_inconsistent_time_intervals():
    """9. Verify only mutually common (startTime, endTime) intervals produce records."""
    t1 = {"startTime": "2026-10-03T18:00:00+08:00", "endTime": "2026-10-04T06:00:00+08:00"}
    t2 = {"startTime": "2026-10-04T06:00:00+08:00", "endTime": "2026-10-04T18:00:00+08:00"}
    t3 = {"startTime": "2026-10-04T18:00:00+08:00", "endTime": "2026-10-05T06:00:00+08:00"}

    elements = [
        {"elementName": "Wx", "time": [
            {**t1, "parameter": {"parameterName": "晴"}},
            {**t2, "parameter": {"parameterName": "陰"}},
        ]},
        {"elementName": "MaxT", "time": [
            {**t1, "parameter": {"parameterName": "30"}},
            {**t3, "parameter": {"parameterName": "32"}},
        ]},
        {"elementName": "MinT", "time": [
            {**t1, "parameter": {"parameterName": "24"}},
            {**t2, "parameter": {"parameterName": "25"}},
        ]},
    ]
    data = _make_dummy_cwa_data(elements)
    records = parse_cwa_forecast(data)

    # Only t1 exists in all three elements (Wx, MaxT, MinT)
    assert len(records) == 1
    assert records[0]["start_time"] == t1["startTime"]
    assert records[0]["end_time"] == t1["endTime"]
    assert records[0]["weather"] == "晴"
    assert records[0]["min_temp"] == 24
    assert records[0]["max_temp"] == 30


def test_non_numeric_temperature():
    """10. Verify non-numeric temperature values are safely skipped."""
    t1 = {"startTime": "2026-10-03T18:00:00+08:00", "endTime": "2026-10-04T06:00:00+08:00"}
    t2 = {"startTime": "2026-10-04T06:00:00+08:00", "endTime": "2026-10-04T18:00:00+08:00"}

    elements = [
        {"elementName": "Wx", "time": [
            {**t1, "parameter": {"parameterName": "晴"}},
            {**t2, "parameter": {"parameterName": "多雲"}},
        ]},
        {"elementName": "MaxT", "time": [
            {**t1, "parameter": {"parameterName": "not_a_number"}},  # Corrupted MaxT
            {**t2, "parameter": {"parameterName": "29"}},
        ]},
        {"elementName": "MinT", "time": [
            {**t1, "parameter": {"parameterName": "20"}},
            {**t2, "parameter": {"parameterName": "21"}},
        ]},
    ]
    data = _make_dummy_cwa_data(elements)
    records = parse_cwa_forecast(data)

    # t1 is skipped due to invalid MaxT, t2 is parsed successfully
    assert len(records) == 1
    assert records[0]["start_time"] == t2["startTime"]
    assert records[0]["max_temp"] == 29
    assert records[0]["min_temp"] == 21


def test_missing_location_name():
    """11. Verify location without locationName is skipped without crashing valid ones."""
    t1 = {"startTime": "2026-10-03T18:00:00+08:00", "endTime": "2026-10-04T06:00:00+08:00"}
    elements = [
        {"elementName": "Wx", "time": [{**t1, "parameter": {"parameterName": "晴"}}]},
        {"elementName": "MaxT", "time": [{**t1, "parameter": {"parameterName": "30"}}]},
        {"elementName": "MinT", "time": [{**t1, "parameter": {"parameterName": "24"}}]},
    ]

    data = {
        "cwaopendata": {
            "dataset": {
                "location": [
                    {"locationName": None, "weatherElement": elements},       # Invalid
                    {"locationName": "   ", "weatherElement": elements},     # Blank
                    {"locationName": "基隆市", "weatherElement": elements},   # Valid
                ]
            }
        }
    }
    records = parse_cwa_forecast(data)
    assert len(records) == 1
    assert records[0]["region_name"] == "基隆市"


def test_empty_locations():
    """12. Verify empty locations array returns empty records list."""
    data = {"cwaopendata": {"dataset": {"location": []}}}
    assert parse_cwa_forecast(data) == []


def test_malformed_root_structure():
    """13. Verify parser handles completely malformed or missing structures."""
    assert parse_cwa_forecast({}) == []
    assert parse_cwa_forecast(None) == []
    assert parse_cwa_forecast([]) == []
    assert parse_cwa_forecast("invalid string") == []
    assert parse_cwa_forecast({"cwaopendata": None}) == []
    assert parse_cwa_forecast({"cwaopendata": {}}) == []
    assert parse_cwa_forecast({"cwaopendata": {"dataset": None}}) == []
    assert parse_cwa_forecast({"cwaopendata": {"dataset": {"location": None}}}) == []
