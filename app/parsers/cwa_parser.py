"""CWA JSON Parser - parses and normalizes raw CWA JSON payload into structured forecast records."""

import math
from typing import Any, Dict, List, Optional, Tuple


class CWAParser:
    """Parser for normalizing Central Weather Administration (CWA) forecast JSON payloads."""

    def __init__(self, dataset_id: str = "F-C0032-005"):
        self.dataset_id = dataset_id

    def parse(self, data: Any) -> List[Dict[str, Any]]:
        """Parse raw CWA JSON payload into a sorted list of normalized forecast records.

        Expected CWA structure:
            cwaopendata -> dataset -> location[] -> [locationName, weatherElement[]]

        Each normalized record contains:
            - dataset_id: str
            - region_name: str
            - start_time: str (ISO 8601)
            - end_time: str (ISO 8601)
            - weather: str
            - min_temp: int
            - max_temp: int

        Alignment:
            Uses composite key (startTime, endTime) to align Wx, MinT, and MaxT.
            If any of the three core elements is missing or invalid for an interval,
            that interval is excluded.

        Sorting:
            Sorted by region_name ascending, then start_time ascending.
        """
        if not isinstance(data, dict):
            return []

        cwa_obj = data.get("cwaopendata")
        if not isinstance(cwa_obj, dict):
            return []

        dataset_obj = cwa_obj.get("dataset")
        if not isinstance(dataset_obj, dict):
            return []

        locations = dataset_obj.get("location")
        if not isinstance(locations, list) or not locations:
            return []

        normalized_records: List[Dict[str, Any]] = []

        for loc in locations:
            if not isinstance(loc, dict):
                continue

            region_name = loc.get("locationName")
            if not region_name or not isinstance(region_name, str) or not region_name.strip():
                # Skip location missing valid locationName
                continue

            weather_elements = loc.get("weatherElement")
            if not isinstance(weather_elements, list) or not weather_elements:
                continue

            wx_map: Dict[Tuple[str, str], str] = {}
            maxt_map: Dict[Tuple[str, str], int] = {}
            mint_map: Dict[Tuple[str, str], int] = {}

            for element in weather_elements:
                if not isinstance(element, dict):
                    continue

                element_name = element.get("elementName")
                if element_name not in ("Wx", "MaxT", "MinT"):
                    continue

                time_list = element.get("time")
                if not isinstance(time_list, list):
                    continue

                for t_entry in time_list:
                    if not isinstance(t_entry, dict):
                        continue

                    start_time = t_entry.get("startTime")
                    end_time = t_entry.get("endTime")
                    if (
                        not start_time
                        or not end_time
                        or not isinstance(start_time, str)
                        or not isinstance(end_time, str)
                    ):
                        continue

                    param = t_entry.get("parameter")
                    if not isinstance(param, dict):
                        continue

                    param_name = param.get("parameterName")
                    if param_name is None:
                        continue

                    time_key = (start_time, end_time)

                    if element_name == "Wx":
                        weather_text = str(param_name).strip()
                        if weather_text:
                            wx_map[time_key] = weather_text

                    elif element_name == "MaxT":
                        try:
                            # Parse temperature string to integer (supports "27", "27.0")
                            maxt_val = int(round(float(str(param_name).strip())))
                            maxt_map[time_key] = maxt_val
                        except (ValueError, TypeError):
                            # Non-numeric temperature parameter, skip interval
                            continue

                    elif element_name == "MinT":
                        try:
                            mint_val = int(round(float(str(param_name).strip())))
                            mint_map[time_key] = mint_val
                        except (ValueError, TypeError):
                            continue

            # Strict alignment: (startTime, endTime) must exist across Wx, MinT, and MaxT
            common_intervals = set(wx_map.keys()) & set(maxt_map.keys()) & set(mint_map.keys())

            for start_time, end_time in common_intervals:
                record = {
                    "dataset_id": self.dataset_id,
                    "region_name": region_name.strip(),
                    "start_time": start_time,
                    "end_time": end_time,
                    "weather": wx_map[(start_time, end_time)],
                    "min_temp": mint_map[(start_time, end_time)],
                    "max_temp": maxt_map[(start_time, end_time)],
                }
                normalized_records.append(record)

        # Sort primarily by region_name ascending, then by start_time ascending
        normalized_records.sort(key=lambda r: (r["region_name"], r["start_time"]))

        return normalized_records


def parse_cwa_forecast(data: Any, dataset_id: str = "F-C0032-005") -> List[Dict[str, Any]]:
    """Convenience helper to parse CWA forecast data into normalized records."""
    return CWAParser(dataset_id=dataset_id).parse(data)


def _safe_parse_pop(val: Any) -> Optional[int]:
    """Parse PoP parameter into an integer percentage (0-100) or None."""
    if val is None:
        return None
    try:
        val_str = str(val).strip().rstrip("%")
        if not val_str or val_str.lower() in ("null", "none", "nan", "-999", "undefined"):
            return None
        num = float(val_str)
        import math
        if math.isnan(num) or math.isinf(num):
            return None
        rounded = int(round(num))
        if 0 <= rounded <= 100:
            return rounded
        return None
    except (ValueError, TypeError):
        return None


def _safe_parse_temp(val: Any) -> Optional[float]:
    """Parse temperature parameter into a float or None, filtering out sentinels (-999, NaN)."""
    if val is None:
        return None
    try:
        val_str = str(val).strip().rstrip("C").rstrip("°C").rstrip("°")
        if not val_str or val_str.lower() in ("null", "none", "nan", "-999", "undefined"):
            return None
        num = float(val_str)
        import math
        if math.isnan(num) or math.isinf(num) or num < -100 or num > 100:
            return None
        return num
    except (ValueError, TypeError):
        return None


def parse_short_term_forecast(
    data: Any,
    dataset_id: str = "F-C0032-001",
) -> List[Dict[str, Any]]:
    """Parse CWA F-C0032-001 36-hour forecast data into normalized records.

    Supports CWA datastore payload:
        records -> location[] -> [locationName, weatherElement[]]
    And legacy/file-style payload:
        cwaopendata -> dataset -> location[]

    Elements parsed:
        - Wx (weather text & weather_code)
        - MinT (minimum temperature, float)
        - MaxT (maximum temperature, float)
        - PoP (probability of precipitation, 0-100 int)
        - CI (comfort index description, str)

    Alignment:
        Strict composite alignment by (start_time, end_time). Does NOT align by array index.
        Nullable fields (PoP, CI, Wx, MinT, MaxT) become None if missing or invalid without
        discarding the entire interval.

    Sorting:
        Sorted by region_name ascending, then start_time ascending.
    """
    if not isinstance(data, dict):
        return []

    locations: List[Dict[str, Any]] = []

    # 1. Primary: CWA Datastore format (records -> location)
    records_obj = data.get("records")
    if isinstance(records_obj, dict):
        loc_candidate = records_obj.get("location")
        if isinstance(loc_candidate, list):
            locations = loc_candidate

    # 2. Fallback: CWA File API format (cwaopendata -> dataset -> location)
    if not locations:
        cwa_obj = data.get("cwaopendata")
        if isinstance(cwa_obj, dict):
            dataset_obj = cwa_obj.get("dataset")
            if isinstance(dataset_obj, dict):
                loc_candidate = dataset_obj.get("location")
                if isinstance(loc_candidate, list):
                    locations = loc_candidate

    if not locations:
        return []

    normalized_records: List[Dict[str, Any]] = []

    for loc in locations:
        if not isinstance(loc, dict):
            continue

        region_name = loc.get("locationName")
        if not region_name or not isinstance(region_name, str) or not region_name.strip():
            continue
        clean_region = region_name.strip()

        weather_elements = loc.get("weatherElement")
        if not isinstance(weather_elements, list) or not weather_elements:
            continue

        # Intervals mapped by exact (start_time, end_time) composite key
        intervals: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for element in weather_elements:
            if not isinstance(element, dict):
                continue

            element_name = element.get("elementName")
            if element_name not in ("Wx", "MaxT", "MinT", "PoP", "CI"):
                continue

            time_list = element.get("time")
            if not isinstance(time_list, list):
                continue

            for t_entry in time_list:
                if not isinstance(t_entry, dict):
                    continue

                start_time = t_entry.get("startTime")
                end_time = t_entry.get("endTime")
                if (
                    not start_time
                    or not end_time
                    or not isinstance(start_time, str)
                    or not isinstance(end_time, str)
                ):
                    continue

                clean_start = start_time.strip()
                clean_end = end_time.strip()
                if not clean_start or not clean_end:
                    continue

                time_key = (clean_start, clean_end)
                if time_key not in intervals:
                    intervals[time_key] = {
                        "weather": None,
                        "weather_code": None,
                        "min_temp": None,
                        "max_temp": None,
                        "pop": None,
                        "comfort_index": None,
                    }

                param = t_entry.get("parameter")
                if not isinstance(param, dict):
                    continue

                param_name = param.get("parameterName")
                param_value = param.get("parameterValue")

                if element_name == "Wx":
                    if param_name is not None and str(param_name).strip():
                        intervals[time_key]["weather"] = str(param_name).strip()
                    if param_value is not None and str(param_value).strip():
                        intervals[time_key]["weather_code"] = str(param_value).strip()

                elif element_name == "MaxT":
                    intervals[time_key]["max_temp"] = _safe_parse_temp(param_name)

                elif element_name == "MinT":
                    intervals[time_key]["min_temp"] = _safe_parse_temp(param_name)

                elif element_name == "PoP":
                    intervals[time_key]["pop"] = _safe_parse_pop(param_name)

                elif element_name == "CI":
                    if param_name is not None and str(param_name).strip():
                        intervals[time_key]["comfort_index"] = str(param_name).strip()

        # Emit records for all aligned intervals
        for (start_time, end_time), fields in intervals.items():
            record = {
                "dataset_id": dataset_id,
                "region_name": clean_region,
                "start_time": start_time,
                "end_time": end_time,
                "weather": fields["weather"],
                "weather_code": fields["weather_code"],
                "min_temp": fields["min_temp"],
                "max_temp": fields["max_temp"],
                "pop": fields["pop"],
                "comfort_index": fields["comfort_index"],
            }
            normalized_records.append(record)

    # Sort primarily by region_name ascending, then start_time ascending
    normalized_records.sort(key=lambda r: (r["region_name"], r["start_time"]))
    return normalized_records


# ==============================================================================
# Phase 8C: O-A0001 Current Weather Station Observation Parser
# ==============================================================================

def get_wind_direction_text(
    wind_dir: Optional[float],
    wind_speed: Optional[float] = None,
) -> Optional[str]:
    """Convert meteorological wind direction degrees (0-360) into traditional compass label.

    Special cases:
        - wind_speed == 0: '靜風'
        - wind_dir in (990, 999): '風向不定'
        - invalid or outside 0-360: None
    """
    if wind_speed is not None and wind_speed == 0:
        return "靜風"
    if wind_dir is None:
        return None
    if wind_dir in (990, 999, 990.0, 999.0):
        return "風向不定"
    if not (0 <= wind_dir <= 360):
        return None
    if 337.5 <= wind_dir <= 360 or 0 <= wind_dir < 22.5:
        return "北風"
    elif 22.5 <= wind_dir < 67.5:
        return "東北風"
    elif 67.5 <= wind_dir < 112.5:
        return "東風"
    elif 112.5 <= wind_dir < 157.5:
        return "東南風"
    elif 157.5 <= wind_dir < 202.5:
        return "南風"
    elif 202.5 <= wind_dir < 247.5:
        return "西南風"
    elif 247.5 <= wind_dir < 292.5:
        return "西風"
    elif 292.5 <= wind_dir < 337.5:
        return "西北風"
    return None


def _normalize_iso_time(time_str: Any) -> Optional[str]:
    """Clean and normalize time string to ISO 8601 representation (+08:00 offset)."""
    if not time_str or not isinstance(time_str, str):
        return None
    cleaned = time_str.strip()
    if not cleaned or cleaned in ("-99", "null", "none"):
        return None
    cleaned = cleaned.replace(" ", "T")
    if "+" not in cleaned and not cleaned.endswith("Z"):
        return f"{cleaned}+08:00"
    return cleaned


def _safe_parse_float(
    val: Any,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> Optional[float]:
    """Parse numeric float, handling missing/sentinel strings (-99, X, NaN)."""
    if val is None:
        return None
    val_str = str(val).strip().rstrip("C").rstrip("°C").rstrip("°").rstrip("hPa").rstrip("m/s")
    if val_str in ("", "-99", "-99.0", "-99.00", "X", "x", "null", "none", "nan", "undefined", "-"):
        return None
    try:
        num = float(val_str)
        if math.isnan(num) or math.isinf(num) or num in (-99.0, -999.0):
            return None
        if min_val is not None and num < min_val:
            return None
        if max_val is not None and num > max_val:
            return None
        return num
    except (ValueError, TypeError):
        return None


def _safe_parse_humidity(val: Any) -> Optional[float]:
    """Parse relative humidity parameter clamped to valid 0-100 range."""
    if val is None:
        return None
    val_str = str(val).strip().rstrip("%")
    if val_str in ("", "-99", "-99.0", "X", "x", "null", "none", "nan", "undefined"):
        return None
    try:
        num = float(val_str)
        if math.isnan(num) or math.isinf(num) or num < 0 or num > 100:
            return None
        return num
    except (ValueError, TypeError):
        return None


def _safe_parse_precipitation(val: Any) -> Tuple[Optional[float], Optional[str]]:
    """Parse precipitation value, preserving semantic precipitation_status."""
    if val is None:
        return (None, "missing")
    val_str = str(val).strip().rstrip("mm")
    if val_str in ("", "-99", "-99.0", "null", "none", "nan", "undefined"):
        return (None, "missing")
    if val_str.upper() == "X":
        return (None, "instrument_error")
    if val_str.upper() == "T":
        return (None, "trace")
    if val_str in ("-98", "-98.0"):
        return (None, "no_precipitation_6h")
    try:
        num = float(val_str)
        if math.isnan(num) or math.isinf(num):
            return (None, "missing")
        if num == -98.0:
            return (None, "no_precipitation_6h")
        if num < 0:
            return (None, "missing")
        return (num, None)
    except (ValueError, TypeError):
        return (None, "missing")


def parse_observation_stations(data: Any) -> List[Dict[str, Any]]:
    """Parse CWA O-A0001 automatic weather station observation dataset.

    Supports:
        - Datastore format: records -> Station[]
        - File API format: cwaopendata -> dataset -> Station[]

    Coordinates:
        Searches GeoInfo.Coordinates for CoordinateName == 'WGS84'.
        Validates latitude (-90..90) and longitude (-180..180).
        Rejects TWD67 coordinates for Leaflet display.

    Missing / special value handling:
        - Sentinels (-99, X): parsed as None
        - Relative humidity: validated 0-100%
        - Precipitation: preserves numeric mm or None, with precipitation_status
        - Wind direction: converts valid 0-360 to compass text, maps 990 to '風向不定'

    Sorting:
        Sorted deterministically by (county_name, station_name, station_id).
    """
    if not isinstance(data, dict):
        return []

    stations_list: List[Dict[str, Any]] = []

    # 1. Primary: Datastore format (records -> Station)
    records_obj = data.get("records")
    if isinstance(records_obj, dict):
        st_candidate = records_obj.get("Station")
        if isinstance(st_candidate, list):
            stations_list = st_candidate

    # 2. Fallback: File API format (cwaopendata -> dataset -> Station)
    if not stations_list:
        cwa_obj = data.get("cwaopendata")
        if isinstance(cwa_obj, dict):
            ds_obj = cwa_obj.get("dataset")
            if isinstance(ds_obj, dict):
                st_candidate = ds_obj.get("Station")
                if isinstance(st_candidate, list):
                    stations_list = st_candidate

    if not stations_list:
        return []

    normalized_stations: List[Dict[str, Any]] = []

    for loc in stations_list:
        if not isinstance(loc, dict):
            continue

        raw_id = loc.get("StationId")
        raw_name = loc.get("StationName")
        if not raw_id or not str(raw_id).strip():
            continue
        if not raw_name or not str(raw_name).strip():
            continue

        station_id = str(raw_id).strip()
        station_name = str(raw_name).strip()

        # Observation time
        obs_time_raw = loc.get("ObsTime", {}).get("DateTime") if isinstance(loc.get("ObsTime"), dict) else None
        obs_time = _normalize_iso_time(obs_time_raw) if obs_time_raw else None

        # GeoInfo
        geo_info = loc.get("GeoInfo", {}) if isinstance(loc.get("GeoInfo"), dict) else {}
        county_name = str(geo_info.get("CountyName", "")).strip() or None
        town_name = str(geo_info.get("TownName", "")).strip() or None
        altitude = _safe_parse_float(geo_info.get("StationAltitude"))

        # WGS84 Coordinates selection
        latitude = None
        longitude = None
        coordinates = geo_info.get("Coordinates", [])
        if isinstance(coordinates, list):
            for coord in coordinates:
                if isinstance(coord, dict) and coord.get("CoordinateName") == "WGS84":
                    lat_cand = _safe_parse_float(coord.get("StationLatitude"), min_val=-90.0, max_val=90.0)
                    lon_cand = _safe_parse_float(coord.get("StationLongitude"), min_val=-180.0, max_val=180.0)
                    if lat_cand is not None and lon_cand is not None:
                        latitude = lat_cand
                        longitude = lon_cand
                    break

        # WeatherElement
        we = loc.get("WeatherElement", {}) if isinstance(loc.get("WeatherElement"), dict) else {}

        # Weather
        raw_wx = we.get("Weather")
        weather = None
        if raw_wx is not None:
            wx_str = str(raw_wx).strip()
            if wx_str and wx_str not in ("-99", "-99.0", "X", "x", "null", "none"):
                weather = wx_str

        # Temperature
        temperature = _safe_parse_float(we.get("AirTemperature"), min_val=-50.0, max_val=60.0)

        # Relative humidity
        relative_humidity = _safe_parse_humidity(we.get("RelativeHumidity"))

        # Wind direction & speed
        wind_dir = _safe_parse_float(we.get("WindDirection"), min_val=0.0, max_val=999.0)
        wind_speed = _safe_parse_float(we.get("WindSpeed"), min_val=0.0, max_val=150.0)
        wind_dir_text = get_wind_direction_text(wind_dir, wind_speed)

        # Air pressure
        air_pressure = _safe_parse_float(we.get("AirPressure"), min_val=300.0, max_val=1100.0)

        # Precipitation
        now_info = we.get("Now", {}) if isinstance(we.get("Now"), dict) else {}
        precip_cand = now_info.get("Precipitation") if "Precipitation" in now_info else we.get("Precipitation")
        precipitation, precipitation_status = _safe_parse_precipitation(precip_cand)

        # Peak gust speed
        gust_info = we.get("GustInfo", {}) if isinstance(we.get("GustInfo"), dict) else {}
        gust_cand = gust_info.get("PeakGustSpeed") if "PeakGustSpeed" in gust_info else we.get("PeakGustSpeed")
        peak_gust_speed = _safe_parse_float(gust_cand, min_val=0.0, max_val=200.0)

        station_record = {
            "station_id": station_id,
            "station_name": station_name,
            "observation_time": obs_time,
            "county_name": county_name,
            "town_name": town_name,
            "latitude": latitude,
            "longitude": longitude,
            "altitude": altitude,
            "weather": weather,
            "temperature": temperature,
            "relative_humidity": relative_humidity,
            "wind_direction": wind_dir,
            "wind_direction_text": wind_dir_text,
            "wind_speed": wind_speed,
            "air_pressure": air_pressure,
            "precipitation": precipitation,
            "precipitation_status": precipitation_status,
            "peak_gust_speed": peak_gust_speed,
        }
        normalized_stations.append(station_record)

    # Sort deterministically: county_name ASC, station_name ASC, station_id ASC
    normalized_stations.sort(
        key=lambda s: (s["county_name"] or "", s["station_name"] or "", s["station_id"] or "")
    )
    return normalized_stations

