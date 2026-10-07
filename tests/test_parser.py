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


# ==============================================================================
# Phase 8B: F-C0032-001 Short-Term 36h Parser Tests
# ==============================================================================

from app.parsers.cwa_parser import parse_short_term_forecast


@pytest.fixture
def sample_36h_payload():
    """Sanitized realistic fixture matching CWA F-C0032-001 datastore JSON structure."""
    return {
        "success": "true",
        "result": {
            "resource_id": "F-C0032-001",
            "fields": [{"id": "datasetDescription", "type": "String"}],
        },
        "records": {
            "datasetDescription": "三十六小時天氣預報",
            "location": [
                {
                    "locationName": "臺中市",
                    "weatherElement": [
                        {
                            "elementName": "Wx",
                            "time": [
                                {
                                    "startTime": "2026-10-05 18:00:00",
                                    "endTime": "2026-10-06 06:00:00",
                                    "parameter": {"parameterName": "多雲短暫陣雨", "parameterValue": "08"},
                                },
                                {
                                    "startTime": "2026-10-06 06:00:00",
                                    "endTime": "2026-10-06 18:00:00",
                                    "parameter": {"parameterName": "多雲午後短暫雷陣雨", "parameterValue": "22"},
                                },
                                {
                                    "startTime": "2026-10-06 18:00:00",
                                    "endTime": "2026-10-07 06:00:00",
                                    "parameter": {"parameterName": "晴時多雲", "parameterValue": "02"},
                                },
                            ],
                        },
                        {
                            "elementName": "MaxT",
                            "time": [
                                {
                                    "startTime": "2026-10-05 18:00:00",
                                    "endTime": "2026-10-06 06:00:00",
                                    "parameter": {"parameterName": "29", "parameterUnit": "C"},
                                },
                                {
                                    "startTime": "2026-10-06 06:00:00",
                                    "endTime": "2026-10-06 18:00:00",
                                    "parameter": {"parameterName": "33.5", "parameterUnit": "C"},
                                },
                                {
                                    "startTime": "2026-10-06 18:00:00",
                                    "endTime": "2026-10-07 06:00:00",
                                    "parameter": {"parameterName": "28", "parameterUnit": "C"},
                                },
                            ],
                        },
                        {
                            "elementName": "MinT",
                            "time": [
                                {
                                    "startTime": "2026-10-05 18:00:00",
                                    "endTime": "2026-10-06 06:00:00",
                                    "parameter": {"parameterName": "25", "parameterUnit": "C"},
                                },
                                {
                                    "startTime": "2026-10-06 06:00:00",
                                    "endTime": "2026-10-06 18:00:00",
                                    "parameter": {"parameterName": "26", "parameterUnit": "C"},
                                },
                                {
                                    "startTime": "2026-10-06 18:00:00",
                                    "endTime": "2026-10-07 06:00:00",
                                    "parameter": {"parameterName": "24", "parameterUnit": "C"},
                                },
                            ],
                        },
                        {
                            "elementName": "PoP",
                            "time": [
                                {
                                    "startTime": "2026-10-05 18:00:00",
                                    "endTime": "2026-10-06 06:00:00",
                                    "parameter": {"parameterName": "40", "parameterUnit": "百分比"},
                                },
                                {
                                    "startTime": "2026-10-06 06:00:00",
                                    "endTime": "2026-10-06 18:00:00",
                                    "parameter": {"parameterName": "70", "parameterUnit": "百分比"},
                                },
                                {
                                    "startTime": "2026-10-06 18:00:00",
                                    "endTime": "2026-10-07 06:00:00",
                                    "parameter": {"parameterName": "10", "parameterUnit": "百分比"},
                                },
                            ],
                        },
                        {
                            "elementName": "CI",
                            "time": [
                                {
                                    "startTime": "2026-10-05 18:00:00",
                                    "endTime": "2026-10-06 06:00:00",
                                    "parameter": {"parameterName": "舒適至悶熱"},
                                },
                                {
                                    "startTime": "2026-10-06 06:00:00",
                                    "endTime": "2026-10-06 18:00:00",
                                    "parameter": {"parameterName": "悶熱"},
                                },
                                {
                                    "startTime": "2026-10-06 18:00:00",
                                    "endTime": "2026-10-07 06:00:00",
                                    "parameter": {"parameterName": "舒適"},
                                },
                            ],
                        },
                    ],
                }
            ],
        },
    }


def test_parse_short_term_forecast_success(sample_36h_payload):
    """Verify parse_short_term_forecast parses 3 intervals with all fields and dataset_id."""
    records = parse_short_term_forecast(sample_36h_payload)
    assert len(records) == 3

    r0 = records[0]
    assert r0["dataset_id"] == "F-C0032-001"
    assert r0["region_name"] == "臺中市"
    assert r0["start_time"] == "2026-10-05 18:00:00"
    assert r0["end_time"] == "2026-10-06 06:00:00"
    assert r0["weather"] == "多雲短暫陣雨"
    assert r0["weather_code"] == "08"
    assert r0["min_temp"] == 25.0
    assert r0["max_temp"] == 29.0
    assert r0["pop"] == 40
    assert r0["comfort_index"] == "舒適至悶熱"

    r1 = records[1]
    assert r1["weather"] == "多雲午後短暫雷陣雨"
    assert r1["weather_code"] == "22"
    assert r1["min_temp"] == 26.0
    assert r1["max_temp"] == 33.5
    assert r1["pop"] == 70
    assert r1["comfort_index"] == "悶熱"


def test_parse_short_term_forecast_legacy_file_style(sample_36h_payload):
    """Verify legacy fileapi style (cwaopendata -> dataset -> location) is parsed."""
    legacy_payload = {
        "cwaopendata": {
            "dataset": {
                "location": sample_36h_payload["records"]["location"]
            }
        }
    }
    records = parse_short_term_forecast(legacy_payload)
    assert len(records) == 3
    assert records[0]["region_name"] == "臺中市"


def test_parse_short_term_forecast_exact_composite_alignment():
    """Verify intervals are aligned by (startTime, endTime) and NOT by array index."""
    payload = {
        "records": {
            "location": [
                {
                    "locationName": "高雄市",
                    "weatherElement": [
                        {
                            "elementName": "Wx",
                            "time": [
                                # Order reversed in Wx!
                                {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "晴天"}},
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "雨天"}},
                            ],
                        },
                        {
                            "elementName": "PoP",
                            "time": [
                                # Normal order in PoP
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "90"}},
                                {"startTime": "2026-10-06 06:00:00", "endTime": "2026-10-06 18:00:00", "parameter": {"parameterName": "10"}},
                            ],
                        },
                    ],
                }
            ]
        }
    }
    records = parse_short_term_forecast(payload)
    assert len(records) == 2
    # Records are sorted by start_time: 10-05 18:00 comes first
    assert records[0]["start_time"] == "2026-10-05 18:00:00"
    assert records[0]["weather"] == "雨天"
    assert records[0]["pop"] == 90

    assert records[1]["start_time"] == "2026-10-06 06:00:00"
    assert records[1]["weather"] == "晴天"
    assert records[1]["pop"] == 10


def test_parse_short_term_forecast_missing_and_invalid_fields():
    """Verify missing/invalid PoP, CI, or temperature become None without discarding the interval."""
    payload = {
        "records": {
            "location": [
                {
                    "locationName": "臺北市",
                    "weatherElement": [
                        {
                            "elementName": "Wx",
                            "time": [
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "陰天"}},
                            ],
                        },
                        {
                            "elementName": "PoP",
                            "time": [
                                # Invalid sentinel value
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "-999"}},
                            ],
                        },
                        {
                            "elementName": "MaxT",
                            "time": [
                                # Sentinel NaN
                                {"startTime": "2026-10-05 18:00:00", "endTime": "2026-10-06 06:00:00", "parameter": {"parameterName": "NaN"}},
                            ],
                        },
                        # CI element is completely missing!
                    ],
                }
            ]
        }
    }
    records = parse_short_term_forecast(payload)
    assert len(records) == 1
    r = records[0]
    assert r["weather"] == "陰天"
    assert r["pop"] is None  # -999 filtered to None
    assert r["max_temp"] is None  # NaN filtered to None
    assert r["min_temp"] is None
    assert r["comfort_index"] is None  # Missing CI is None


# ==============================================================================
# Phase 8C: O-A0001 Observation Parser Tests
# ==============================================================================

from app.parsers.cwa_parser import parse_observation_stations, get_wind_direction_text

OBS_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "cwa_o_a0001_sample.json"


@pytest.fixture
def obs_fixture_data():
    """Load sample O-A0001 JSON fixture data."""
    assert OBS_FIXTURE_PATH.exists(), f"Fixture file not found: {OBS_FIXTURE_PATH}"
    with open(OBS_FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_wind_direction_conversion():
    """Verify degrees converted to 8 compass directions and special cases handled."""
    assert get_wind_direction_text(0, wind_speed=0.0) == "靜風"
    assert get_wind_direction_text(0, wind_speed=2.0) == "北風"
    assert get_wind_direction_text(360, wind_speed=2.0) == "北風"
    assert get_wind_direction_text(45, wind_speed=2.0) == "東北風"
    assert get_wind_direction_text(90, wind_speed=2.0) == "東風"
    assert get_wind_direction_text(135, wind_speed=2.0) == "東南風"
    assert get_wind_direction_text(180, wind_speed=2.0) == "南風"
    assert get_wind_direction_text(225, wind_speed=2.0) == "西南風"
    assert get_wind_direction_text(270, wind_speed=2.0) == "西風"
    assert get_wind_direction_text(315, wind_speed=2.0) == "西北風"
    # Special variable wind sentinels
    assert get_wind_direction_text(990) == "風向不定"
    assert get_wind_direction_text(999) == "風向不定"
    # Invalid values
    assert get_wind_direction_text(-99) is None
    assert get_wind_direction_text(None) is None


def test_parse_observation_stations_with_fixture(obs_fixture_data):
    """Verify O-A0001 fixture parsing with WGS84 coordinates and special sentinels."""
    stations = parse_observation_stations(obs_fixture_data)
    assert isinstance(stations, list)
    assert len(stations) == 6

    # Test deterministic sorting: (county_name, station_name, station_id)
    # Counties in fixture: 嘉義縣, 臺中市, 臺北市, 臺東縣, 花蓮縣, 高雄市
    county_names = [s["county_name"] for s in stations]
    assert county_names == ["嘉義縣", "臺中市", "臺北市", "臺東縣", "花蓮縣", "高雄市"]

    # 1. 臺中 Station: WGS84 preferred over TWD67
    tc = next(s for s in stations if s["station_id"] == "467490")
    assert tc["station_name"] == "臺中"
    assert tc["observation_time"] == "2026-10-07T18:00:00+08:00"
    assert tc["county_name"] == "臺中市"
    assert tc["town_name"] == "北區"
    # WGS84 is 24.1453, 120.6841 (not TWD67 24.145, 120.683)
    assert tc["latitude"] == 24.1453
    assert tc["longitude"] == 120.6841
    assert tc["altitude"] == 84.0
    assert tc["weather"] == "多雲"
    assert tc["temperature"] == 27.4
    assert tc["relative_humidity"] == 76
    assert tc["wind_direction"] == 220
    assert tc["wind_direction_text"] == "西南風"
    assert tc["wind_speed"] == 2.1
    assert tc["air_pressure"] == 1008.4
    assert tc["precipitation"] == 0.0
    assert tc["precipitation_status"] is None
    assert tc["peak_gust_speed"] == 5.4

    # 2. 陽明山 Station: Trace precipitation ('T') & variable wind (990)
    ym = next(s for s in stations if s["station_id"] == "466910")
    assert ym["precipitation"] is None
    assert ym["precipitation_status"] == "trace"
    assert ym["wind_direction"] == 990
    assert ym["wind_direction_text"] == "風向不定"
    assert ym["temperature"] == 21.0
    assert ym["relative_humidity"] == 85

    # 3. 高雄 Station: -98 no-rain, -99 temperature/humidity missing, calm wind (0)
    kh = next(s for s in stations if s["station_id"] == "467440")
    assert kh["precipitation"] is None
    assert kh["precipitation_status"] == "no_precipitation_6h"
    assert kh["temperature"] is None  # -99 converted to None
    assert kh["relative_humidity"] is None  # -99 converted to None
    assert kh["peak_gust_speed"] is None  # -99 converted to None
    assert kh["wind_speed"] == 0.0
    assert kh["wind_direction_text"] == "靜風"

    # 4. 阿里山 Station: 'X' precipitation instrument error
    as_st = next(s for s in stations if s["station_id"] == "467530")
    assert as_st["precipitation"] is None
    assert as_st["precipitation_status"] == "instrument_error"
    assert as_st["temperature"] == 14.2
    assert as_st["altitude"] == 2213.0

    # 5. 無經緯測站: Only TWD67 -> coordinates become None
    no_wgs = next(s for s in stations if s["station_id"] == "C0X001")
    assert no_wgs["latitude"] is None
    assert no_wgs["longitude"] is None

    # 6. 超界經緯測站: Latitude 95.0 -> becomes None
    out_of_bounds = next(s for s in stations if s["station_id"] == "C0X002")
    assert out_of_bounds["latitude"] is None


def test_parse_observation_stations_file_style():
    """Verify cwaopendata -> dataset -> Station[] shape is supported."""
    file_style_data = {
        "cwaopendata": {
            "dataset": {
                "Station": [
                    {
                        "StationName": "基隆",
                        "StationId": "466940",
                        "ObsTime": {"DateTime": "2026-10-07T18:00:00+08:00"},
                        "GeoInfo": {
                            "Coordinates": [
                                {"CoordinateName": "WGS84", "StationLatitude": 25.133, "StationLongitude": 121.74}
                            ],
                            "CountyName": "基隆市",
                            "TownName": "仁愛區",
                        },
                        "WeatherElement": {
                            "AirTemperature": 26.5,
                            "RelativeHumidity": 80,
                        },
                    }
                ]
            }
        }
    }
    stations = parse_observation_stations(file_style_data)
    assert len(stations) == 1
    assert stations[0]["station_name"] == "基隆"
    assert stations[0]["latitude"] == 25.133
    assert stations[0]["temperature"] == 26.5


def test_parse_observation_stations_malformed_input():
    """Verify malformed stations or empty structures fail safely."""
    assert parse_observation_stations({}) == []
    assert parse_observation_stations(None) == []
    assert parse_observation_stations({"records": {"Station": "invalid"}}) == []
    assert parse_observation_stations({"records": {"Station": [None, {}, {"StationName": "無ID"}]}}) == []


