"""CWA JSON Parser - parses and normalizes raw CWA JSON payload into structured forecast records."""

import math
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
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


# ==============================================================================
# Phase 8D: O-A0058-001 Radar Reflectivity Metadata XML Parser
# ==============================================================================

def parse_radar_metadata_xml(xml_content: str) -> Dict[str, Any]:
    """Parse CWA O-A0058-001 radar metadata XML.

    Extracts:
        - product_url (str): Image ProductURL
        - radar_time (str): Official meteorological DateTime
        - sent_time (str): Feed sent timestamp
        - west, east (float): Longitude range
        - south, north (float): Latitude range
        - image_width, image_height (int): Pixel dimensions

    Handles XML namespaces robustly by inspecting local tag names.
    Returns empty dict on parse error or invalid payload.
    """
    if not xml_content or not isinstance(xml_content, str):
        return {}

    try:
        root = ET.fromstring(xml_content.strip())
    except ET.ParseError:
        return {}

    def find_local(parent: ET.Element, tag_name: str) -> Optional[ET.Element]:
        for elem in parent.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == tag_name:
                return elem
        return None

    def find_text(parent: ET.Element, tag_name: str) -> Optional[str]:
        elem = find_local(parent, tag_name)
        if elem is not None and elem.text:
            val = elem.text.strip()
            return val if val else None
        return None

    product_url = find_text(root, "ProductURL")
    date_time = find_text(root, "DateTime")
    sent_time = find_text(root, "sent")
    lon_range_str = find_text(root, "LongitudeRange")
    lat_range_str = find_text(root, "LatitudeRange")
    dim_str = find_text(root, "ImageDimension")

    west = None
    east = None
    if lon_range_str:
        # Expected format: "115.00-126.50" or "115.00 - 126.50"
        parts = [p.strip() for p in lon_range_str.split("-") if p.strip()]
        if len(parts) == 2:
            try:
                west = float(parts[0])
                east = float(parts[1])
            except ValueError:
                pass

    south = None
    north = None
    if lat_range_str:
        # Expected format: "17.75-29.25" or "17.75 - 29.25"
        parts = [p.strip() for p in lat_range_str.split("-") if p.strip()]
        if len(parts) == 2:
            try:
                south = float(parts[0])
                north = float(parts[1])
            except ValueError:
                pass

    width = None
    height = None
    if dim_str:
        # Expected format: "3600x3600" or "3600X3600"
        parts = [p.strip() for p in dim_str.lower().split("x") if p.strip()]
        if len(parts) == 2:
            try:
                width = int(parts[0])
                height = int(parts[1])
            except ValueError:
                pass

    result: Dict[str, Any] = {}
    if product_url:
        result["product_url"] = product_url
    if date_time:
        result["radar_time"] = date_time
    if sent_time:
        result["sent_time"] = sent_time
    if west is not None and east is not None:
        result["west"] = west
        result["east"] = east
    if south is not None and north is not None:
        result["south"] = south
        result["north"] = north
    if width is not None and height is not None:
        result["image_width"] = width
        result["image_height"] = height

    return result


# ==============================================================================
# Phase 8E: W-C0034-005 Tropical Cyclone Track & Analysis Parser
# ==============================================================================

def _safe_parse_int(val: Any) -> Optional[int]:
    """Parse integer, returning None on invalid/sentinel values."""
    if val is None:
        return None
    val_str = str(val).strip()
    if val_str in ("", "-99", "-999", "X", "x", "null", "none", "nan", "undefined", "-"):
        return None
    try:
        return int(float(val_str))
    except (ValueError, TypeError):
        return None


def _derive_valid_time(init_time_str: Optional[str], tau: Optional[int]) -> Optional[str]:
    """Derive valid forecast timestamp from init_time + tau hours."""
    if not init_time_str or tau is None:
        return None
    try:
        clean = init_time_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        vt = dt + timedelta(hours=int(tau))
        return vt.isoformat()
    except Exception:
        return None


def parse_typhoon_coordinate(value: Any, parent_obj: Any = None) -> Tuple[Optional[float], Optional[float]]:
    """Parse tropical cyclone coordinate into (latitude, longitude).

    Supports:
        - String format: "120.5,20.5" -> (lat=20.5, lon=120.5) [Note: Official string format is "longitude,latitude"]
        - Dict format: {"longitude": 120.5, "latitude": 20.5} or {"CoordinateLongitude": ..., "CoordinateLatitude": ...}
        - Parent object fallback if value is None or incomplete: parent_obj.get("latitude") / parent_obj.get("CoordinateLatitude"), etc.

    Validation:
        - latitude: -90.0 .. 90.0
        - longitude: -180.0 .. 180.0
        - Invalid / malformed: returns (None, None)
    """
    lat: Optional[float] = None
    lon: Optional[float] = None

    if isinstance(value, str) and value.strip():
        parts = [p.strip() for p in value.split(",") if p.strip()]
        if len(parts) == 2:
            lon_cand = _safe_parse_float(parts[0], min_val=-180.0, max_val=180.0)
            lat_cand = _safe_parse_float(parts[1], min_val=-90.0, max_val=90.0)
            if lat_cand is not None and lon_cand is not None:
                return (lat_cand, lon_cand)
    elif isinstance(value, dict):
        lat_cand = value.get("latitude") or value.get("CoordinateLatitude") or value.get("lat") or value.get("Latitude")
        lon_cand = value.get("longitude") or value.get("CoordinateLongitude") or value.get("lon") or value.get("Longitude")
        lat = _safe_parse_float(lat_cand, min_val=-90.0, max_val=90.0)
        lon = _safe_parse_float(lon_cand, min_val=-180.0, max_val=180.0)
        if lat is not None and lon is not None:
            return (lat, lon)

    if (lat is None or lon is None) and isinstance(parent_obj, dict):
        coord_val = parent_obj.get("coordinate") or parent_obj.get("Coordinate")
        if isinstance(coord_val, str) and coord_val.strip() and coord_val != value:
            c_lat, c_lon = parse_typhoon_coordinate(coord_val)
            if c_lat is not None and c_lon is not None:
                return (c_lat, c_lon)
        lat_cand = parent_obj.get("CoordinateLatitude") or parent_obj.get("coordinateLatitude") or parent_obj.get("latitude") or parent_obj.get("Latitude")
        lon_cand = parent_obj.get("CoordinateLongitude") or parent_obj.get("coordinateLongitude") or parent_obj.get("longitude") or parent_obj.get("Longitude")
        lat = _safe_parse_float(lat_cand, min_val=-90.0, max_val=90.0)
        lon = _safe_parse_float(lon_cand, min_val=-180.0, max_val=180.0)

    if lat is not None and lon is not None:
        return (lat, lon)

    return (None, None)


def _parse_quadrant_radii(circle_obj: Any) -> Optional[Dict[str, Optional[float]]]:
    """Parse 4-quadrant radii dictionary (NE, SE, SW, NW in km)."""
    if not isinstance(circle_obj, dict):
        return None
    q_obj = circle_obj.get("quadrantRadii") or circle_obj.get("QuadrantRadii") or circle_obj.get("quadrant_radii") or circle_obj
    if not isinstance(q_obj, dict):
        return None

    dir_map = {
        "ne": "NE", "northeast": "NE",
        "se": "SE", "southeast": "SE",
        "sw": "SW", "southwest": "SW",
        "nw": "NW", "northwest": "NW",
    }
    direct_quads = {}
    for k, v in q_obj.items():
        k_lower = str(k).strip().lower()
        if k_lower in dir_map:
            val = _safe_parse_float(v)
            if val is not None:
                direct_quads[dir_map[k_lower]] = val
    if len(direct_quads) == 4:
        return direct_quads

    r_list = q_obj.get("radius") or q_obj.get("Radius") or []
    if isinstance(r_list, dict):
        r_list = [r_list]
    if not isinstance(r_list, list):
        return None
    quads: Dict[str, Optional[float]] = {}
    for item in r_list:
        if isinstance(item, dict):
            direction = item.get("@dir") or item.get("dir") or item.get("direction")
            val = _safe_parse_float(item.get("value") or item.get("#text") or item.get("Radius") or item.get("radius"))
            if direction and val is not None:
                d_key = dir_map.get(str(direction).strip().lower(), str(direction).strip().upper())
                quads[d_key] = val
    return quads if quads else None


def _parse_movement_prediction(pred_obj: Any) -> Optional[str]:
    """Extract Chinese or primary text from moving prediction field."""
    if pred_obj is None:
        return None
    if isinstance(pred_obj, str):
        return pred_obj.strip() or None
    if isinstance(pred_obj, dict):
        return pred_obj.get("#text") or pred_obj.get("text") or pred_obj.get("value")
    if isinstance(pred_obj, list):
        for item in pred_obj:
            if isinstance(item, dict):
                lang = str(item.get("@lang", item.get("lang", ""))).lower()
                if "zh" in lang or "hant" in lang:
                    return item.get("#text") or item.get("text") or item.get("value")
        for item in pred_obj:
            if isinstance(item, dict) and (item.get("#text") or item.get("text") or item.get("value")):
                return item.get("#text") or item.get("text") or item.get("value")
            elif isinstance(item, str) and item.strip():
                return item.strip()
    return None


def _parse_state_transfer(st_obj: Any) -> Optional[str]:
    """Extract Chinese or primary text description from StateTransfer field."""
    if st_obj is None:
        return None
    if isinstance(st_obj, str):
        return st_obj.strip() or None
    if isinstance(st_obj, dict):
        return st_obj.get("value") or st_obj.get("#text") or st_obj.get("text")
    if isinstance(st_obj, list):
        for item in st_obj:
            if isinstance(item, dict):
                lang = str(item.get("@lang", item.get("lang", ""))).lower()
                if "zh" in lang or "hant" in lang:
                    return item.get("value") or item.get("#text") or item.get("text")
        for item in st_obj:
            if isinstance(item, dict):
                val = item.get("value") or item.get("#text") or item.get("text")
                if val:
                    return val
            elif isinstance(item, str) and item.strip():
                return item.strip()
    return None


def parse_typhoon_data(data: Any) -> Dict[str, Any]:
    """Parse CWA W-C0034-005 tropical cyclone dataset (JSON dict or XML string).

    Normalizes active cyclones in Western North Pacific & South China Sea.
    Returns:
        {
            "dataset_id": "W-C0034-005",
            "updated_at": "... (ISO string)",
            "active_count": int,
            "cyclones": [
                {
                    "id": "...",
                    "year": 2026,
                    "name_en": "NOLO",
                    "name_zh": "諾羅",
                    "cwa_td_no": "32",
                    "cwa_ty_no": "27",
                    "analysis_points": [...],
                    "current": {...},
                    "forecast_points": [...]
                },
                ...
            ]
        }
    If empty or no active cyclones, returns active_count=0 and cyclones=[].
    """
    empty_result = {
        "dataset_id": "W-C0034-005",
        "updated_at": None,
        "active_count": 0,
        "cyclones": [],
    }

    if data is None:
        return empty_result

    # -------------------------------------------------------------------------
    # Branch 1: XML String payload
    # -------------------------------------------------------------------------
    if isinstance(data, str):
        if not data.strip():
            return empty_result
        try:
            root = ET.fromstring(data.strip())
        except ET.ParseError:
            return empty_result

        def find_local(parent: ET.Element, tag_name: str) -> Optional[ET.Element]:
            for elem in parent.iter():
                local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if local.lower() == tag_name.lower():
                    return elem
            return None

        def find_text(parent: ET.Element, tag_name: str) -> Optional[str]:
            elem = find_local(parent, tag_name)
            if elem is not None and elem.text:
                val = elem.text.strip()
                return val if val else None
            return None

        def find_all_local(parent: ET.Element, tag_name: str) -> List[ET.Element]:
            matches = []
            for elem in parent.iter():
                local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if local.lower() == tag_name.lower():
                    matches.append(elem)
            return matches

        def find_text_any(parent: ET.Element, names: List[str]) -> Optional[str]:
            for n in names:
                t = find_text(parent, n)
                if t:
                    return t
            return None

        def find_local_any(parent: ET.Element, names: List[str]) -> Optional[ET.Element]:
            for n in names:
                el = find_local(parent, n)
                if el is not None:
                    return el
            return None

        def extract_quadrant_xml(circle_elem: Optional[ET.Element]) -> Optional[Dict[str, float]]:
            if circle_elem is None:
                return None
            quad_dict = {}
            q_elem = find_local_any(circle_elem, ["quadrantRadii", "quadrant_radii", "QuadrantRadii"])
            target = q_elem if q_elem is not None else circle_elem
            dir_map = {
                "northeast": "NE", "ne": "NE",
                "southeast": "SE", "se": "SE",
                "southwest": "SW", "sw": "SW",
                "northwest": "NW", "nw": "NW",
            }
            for child in target:
                local_tag = child.tag.split("}")[-1].lower()
                if local_tag in dir_map and child.text:
                    val = _safe_parse_float(child.text)
                    if val is not None:
                        quad_dict[dir_map[local_tag]] = val
                elif local_tag == "radius" and child.text:
                    d = child.attrib.get("dir") or child.attrib.get("direction")
                    if d:
                        d_key = dir_map.get(str(d).strip().lower(), str(d).strip().upper())
                        val = _safe_parse_float(child.text)
                        if val is not None:
                            quad_dict[d_key] = val
            return quad_dict if len(quad_dict) == 4 else None

        updated_at = find_text_any(root, ["Sent", "sent", "DateTime", "dateTime"])
        tc_elements = find_all_local(root, "TropicalCyclone")
        if not tc_elements:
            tc_elements = find_all_local(root, "tropicalCyclone")
        cyclones = []

        for tc in tc_elements:
            year = _safe_parse_int(find_text_any(tc, ["Year", "year"]))
            name_en = find_text_any(tc, ["TyphoonName", "typhoon_name", "typhoonName", "name"])
            name_zh = find_text_any(tc, ["CwaTyphoonName", "cwa_typhoon_name", "cwaTyphoonName", "cwa_name"])
            cwa_td_no = find_text_any(tc, ["CwaTdNo", "cwa_td_no", "cwaTdNo"])
            cwa_ty_no = find_text_any(tc, ["CwaTyNo", "cwa_ty_no", "cwaTyNo"])
            tc_id = f"{year or datetime.now().year}_{cwa_ty_no or cwa_td_no or name_en or len(cyclones)+1}"

            # Analysis Points
            analysis_elem = find_local_any(tc, ["AnalysisData", "analysis_data", "analysisData"])
            fixes = []
            if analysis_elem is not None:
                fixes = find_all_local(analysis_elem, "Fix") or find_all_local(analysis_elem, "fix")
            analysis_points = []

            for fix in fixes:
                coord_elem = find_local_any(fix, ["Coordinate", "coordinate"])
                coord_text = coord_elem.text.strip() if (coord_elem is not None and coord_elem.text and not list(coord_elem)) else None
                if coord_text:
                    lat, lon = parse_typhoon_coordinate(coord_text)
                else:
                    lat_raw = find_text_any(fix, ["CoordinateLatitude", "latitude"]) or (find_text_any(coord_elem, ["Latitude", "latitude"]) if coord_elem is not None else None)
                    lon_raw = find_text_any(fix, ["CoordinateLongitude", "longitude"]) or (find_text_any(coord_elem, ["Longitude", "longitude"]) if coord_elem is not None else None)
                    lat, lon = parse_typhoon_coordinate(None, {"latitude": lat_raw, "longitude": lon_raw})
                if lat is None or lon is None:
                    continue

                c15_elem = find_local_any(fix, ["circleOf15Ms", "Circle15ms", "circle_of_15ms", "circle15ms"])
                c25_elem = find_local_any(fix, ["circleOf25Ms", "Circle25ms", "circle_of_25ms", "circle25ms"])
                r15 = None
                if c15_elem is not None:
                    r15 = _safe_parse_float(find_text_any(c15_elem, ["Radius", "radius"]))
                    if r15 is None and c15_elem.text and not list(c15_elem):
                        r15 = _safe_parse_float(c15_elem.text)

                r25 = None
                if c25_elem is not None:
                    r25 = _safe_parse_float(find_text_any(c25_elem, ["Radius", "radius"]))
                    if r25 is None and c25_elem.text and not list(c25_elem):
                        r25 = _safe_parse_float(c25_elem.text)

                p = {
                    "time": _normalize_iso_time(find_text_any(fix, ["fixTime", "DateTime", "fix_time", "dateTime", "time"])),
                    "latitude": lat,
                    "longitude": lon,
                    "max_wind_speed": _safe_parse_float(find_text_any(fix, ["maxWindSpeed", "MaxWindSpeed", "max_wind_speed"])),
                    "max_gust_speed": _safe_parse_float(find_text_any(fix, ["maxGustSpeed", "MaxGustSpeed", "max_gust_speed"])),
                    "pressure": _safe_parse_float(find_text_any(fix, ["pressure", "Pressure"])),
                    "radius_15ms": r15,
                    "radius_25ms": r25,
                    "quadrant_15ms": extract_quadrant_xml(c15_elem),
                    "quadrant_25ms": extract_quadrant_xml(c25_elem),
                    "movement_speed": _safe_parse_float(find_text_any(fix, ["movingSpeed", "MovingSpeed", "speed"])),
                    "movement_direction": find_text_any(fix, ["movingDirection", "MovingDirection", "moving_direction"]),
                    "movement_prediction": _parse_movement_prediction(find_text_any(fix, ["movingPrediction", "MovingPrediction", "moving_prediction"])),
                }
                analysis_points.append(p)

            analysis_points.sort(key=lambda pt: pt.get("time") or "")
            current_pt = analysis_points[-1] if analysis_points else None

            # Forecast Points
            forecast_elem = find_local_any(tc, ["forecastData", "ForecastData", "forecast_data"])
            f_fixes = []
            if forecast_elem is not None:
                f_fixes = find_all_local(forecast_elem, "Fix") or find_all_local(forecast_elem, "fix")
            forecast_points = []

            for fix in f_fixes:
                coord_elem = find_local_any(fix, ["Coordinate", "coordinate"])
                coord_text = coord_elem.text.strip() if (coord_elem is not None and coord_elem.text and not list(coord_elem)) else None
                if coord_text:
                    lat, lon = parse_typhoon_coordinate(coord_text)
                else:
                    lat_raw = find_text_any(fix, ["CoordinateLatitude", "latitude"]) or (find_text_any(coord_elem, ["Latitude", "latitude"]) if coord_elem is not None else None)
                    lon_raw = find_text_any(fix, ["CoordinateLongitude", "longitude"]) or (find_text_any(coord_elem, ["Longitude", "longitude"]) if coord_elem is not None else None)
                    lat, lon = parse_typhoon_coordinate(None, {"latitude": lat_raw, "longitude": lon_raw})
                if lat is None or lon is None:
                    continue

                init_time = _normalize_iso_time(find_text_any(fix, ["initTime", "InitialTime", "initialTime", "init_time"]))
                tau = _safe_parse_int(find_text_any(fix, ["tau", "ForecastHour", "forecastHour"]))
                valid_time = _derive_valid_time(init_time, tau)

                c15_elem = find_local_any(fix, ["circleOf15Ms", "Circle15ms", "circle_of_15ms", "circle15ms"])
                c25_elem = find_local_any(fix, ["circleOf25Ms", "Circle25ms", "circle_of_25ms", "circle25ms"])
                r15 = None
                if c15_elem is not None:
                    r15 = _safe_parse_float(find_text_any(c15_elem, ["Radius", "radius"]))
                    if r15 is None and c15_elem.text and not list(c15_elem):
                        r15 = _safe_parse_float(c15_elem.text)

                r25 = None
                if c25_elem is not None:
                    r25 = _safe_parse_float(find_text_any(c25_elem, ["Radius", "radius"]))
                    if r25 is None and c25_elem.text and not list(c25_elem):
                        r25 = _safe_parse_float(c25_elem.text)

                fp = {
                    "init_time": init_time,
                    "tau": tau,
                    "valid_time": valid_time,
                    "latitude": lat,
                    "longitude": lon,
                    "max_wind_speed": _safe_parse_float(find_text_any(fix, ["maxWindSpeed", "MaxWindSpeed", "max_wind_speed"])),
                    "max_gust_speed": _safe_parse_float(find_text_any(fix, ["maxGustSpeed", "MaxGustSpeed", "max_gust_speed"])),
                    "pressure": _safe_parse_float(find_text_any(fix, ["pressure", "Pressure"])),
                    "radius_15ms": r15,
                    "radius_25ms": r25,
                    "probability_70_radius": _safe_parse_float(find_text_any(fix, ["radiusOf70PercentProbability", "Radius70PercentProbability", "radius_of_70percent_probability"])),
                    "state_transfer": _parse_state_transfer(find_text_any(fix, ["stateTransfer", "StateTransfer", "state_transfer"])),
                }
                forecast_points.append(fp)

            forecast_points.sort(key=lambda pt: (pt.get("tau") or 0, pt.get("valid_time") or ""))

            cyclones.append({
                "id": tc_id,
                "year": year,
                "name_en": name_en,
                "name_zh": name_zh,
                "cwa_td_no": cwa_td_no,
                "cwa_ty_no": cwa_ty_no,
                "analysis_points": analysis_points,
                "current": current_pt,
                "forecast_points": forecast_points,
            })

        if not updated_at and cyclones:
            for c in cyclones:
                if c.get("current") and c["current"].get("time"):
                    updated_at = c["current"]["time"]
                    break

        return {
            "dataset_id": "W-C0034-005",
            "updated_at": updated_at,
            "active_count": len(cyclones),
            "cyclones": cyclones,
        }

    # -------------------------------------------------------------------------
    # Branch 2: JSON Dict payload
    # -------------------------------------------------------------------------
    if not isinstance(data, dict):
        return empty_result

    cwa_obj = data.get("cwaopendata", data)
    updated_at = cwa_obj.get("Sent") or cwa_obj.get("sent") or cwa_obj.get("DateTime")

    dataset_obj = cwa_obj.get("Dataset") or cwa_obj.get("dataset") or data.get("records") or {}
    tc_parent = dataset_obj.get("tropicalCyclones") or dataset_obj.get("TropicalCyclones") or {}
    if isinstance(tc_parent, list):
        tc_list = tc_parent
    elif isinstance(tc_parent, dict):
        tc_list = tc_parent.get("tropicalCyclone") or tc_parent.get("TropicalCyclone") or []
        if isinstance(tc_list, dict):
            tc_list = [tc_list]
    else:
        tc_list = []

    if not isinstance(tc_list, list):
        tc_list = []

    cyclones = []
    for tc in tc_list:
        if not isinstance(tc, dict):
            continue
        year = _safe_parse_int(tc.get("year") or tc.get("Year"))
        name_en = tc.get("typhoonName") or tc.get("TyphoonName") or tc.get("name")
        name_zh = tc.get("cwaTyphoonName") or tc.get("CwaTyphoonName") or tc.get("cwa_name")
        cwa_td_no = tc.get("cwaTdNo") or tc.get("CwaTdNo")
        cwa_ty_no = tc.get("cwaTyNo") or tc.get("CwaTyNo")
        tc_id = f"{year or datetime.now().year}_{cwa_ty_no or cwa_td_no or name_en or len(cyclones)+1}"

        # Analysis Points
        analysis_obj = tc.get("analysisData") or tc.get("AnalysisData") or tc.get("analysis_data") or {}
        if isinstance(analysis_obj, list):
            fixes = analysis_obj
        else:
            fixes = analysis_obj.get("fix") or analysis_obj.get("Fix") or []
        if isinstance(fixes, dict):
            fixes = [fixes]
        if not isinstance(fixes, list):
            fixes = []

        analysis_points = []
        for fix in fixes:
            if not isinstance(fix, dict):
                continue
            lat, lon = parse_typhoon_coordinate(fix.get("coordinate") or fix.get("Coordinate"), fix)
            if lat is None or lon is None:
                continue

            c15 = fix.get("circleOf15Ms") or fix.get("Circle15ms") or fix.get("circle15ms") or fix.get("circle_of_15ms") or {}
            c25 = fix.get("circleOf25Ms") or fix.get("Circle25ms") or fix.get("circle25ms") or fix.get("circle_of_25ms") or {}

            r15_val = c15.get("radius") or c15.get("Radius") if isinstance(c15, dict) else c15
            r25_val = c25.get("radius") or c25.get("Radius") if isinstance(c25, dict) else c25

            p = {
                "time": _normalize_iso_time(fix.get("fixTime") or fix.get("DateTime") or fix.get("dateTime") or fix.get("time") or fix.get("fix_time")),
                "latitude": lat,
                "longitude": lon,
                "max_wind_speed": _safe_parse_float(fix.get("maxWindSpeed") or fix.get("MaxWindSpeed") or fix.get("max_wind_speed")),
                "max_gust_speed": _safe_parse_float(fix.get("maxGustSpeed") or fix.get("MaxGustSpeed") or fix.get("max_gust_speed")),
                "pressure": _safe_parse_float(fix.get("pressure") or fix.get("Pressure")),
                "radius_15ms": _safe_parse_float(r15_val),
                "radius_25ms": _safe_parse_float(r25_val),
                "quadrant_15ms": _parse_quadrant_radii(c15),
                "quadrant_25ms": _parse_quadrant_radii(c25),
                "movement_speed": _safe_parse_float(fix.get("movingSpeed") or fix.get("MovingSpeed") or fix.get("speed")),
                "movement_direction": fix.get("movingDirection") or fix.get("MovingDirection") or fix.get("moving_direction"),
                "movement_prediction": _parse_movement_prediction(fix.get("movingPrediction") or fix.get("MovingPrediction") or fix.get("moving_prediction")),
            }
            analysis_points.append(p)

        analysis_points.sort(key=lambda pt: pt.get("time") or "")
        current_pt = analysis_points[-1] if analysis_points else None

        # Forecast Points
        forecast_obj = tc.get("forecastData") or tc.get("ForecastData") or tc.get("forecast_data") or {}
        if isinstance(forecast_obj, list):
            f_fixes = forecast_obj
        else:
            f_fixes = forecast_obj.get("fix") or forecast_obj.get("Fix") or []
        if isinstance(f_fixes, dict):
            f_fixes = [f_fixes]
        if not isinstance(f_fixes, list):
            f_fixes = []

        forecast_points = []
        for fix in f_fixes:
            if not isinstance(fix, dict):
                continue
            lat, lon = parse_typhoon_coordinate(fix.get("coordinate") or fix.get("Coordinate"), fix)
            if lat is None or lon is None:
                continue

            init_time = _normalize_iso_time(fix.get("initTime") or fix.get("InitialTime") or fix.get("initialTime") or fix.get("init_time"))
            tau = _safe_parse_int(fix.get("tau") or fix.get("ForecastHour") or fix.get("forecastHour"))
            valid_time = _derive_valid_time(init_time, tau)

            c15 = fix.get("circleOf15Ms") or fix.get("Circle15ms") or fix.get("circle15ms") or fix.get("circle_of_15ms") or {}
            c25 = fix.get("circleOf25Ms") or fix.get("Circle25ms") or fix.get("circle25ms") or fix.get("circle_of_25ms") or {}

            r15_val = c15.get("radius") or c15.get("Radius") if isinstance(c15, dict) else c15
            r25_val = c25.get("radius") or c25.get("Radius") if isinstance(c25, dict) else c25

            fp = {
                "init_time": init_time,
                "tau": tau,
                "valid_time": valid_time,
                "latitude": lat,
                "longitude": lon,
                "max_wind_speed": _safe_parse_float(fix.get("maxWindSpeed") or fix.get("MaxWindSpeed") or fix.get("max_wind_speed")),
                "max_gust_speed": _safe_parse_float(fix.get("maxGustSpeed") or fix.get("MaxGustSpeed") or fix.get("max_gust_speed")),
                "pressure": _safe_parse_float(fix.get("pressure") or fix.get("Pressure")),
                "radius_15ms": _safe_parse_float(r15_val),
                "radius_25ms": _safe_parse_float(r25_val),
                "probability_70_radius": _safe_parse_float(fix.get("radiusOf70PercentProbability") or fix.get("Radius70PercentProbability") or fix.get("radius_of_70percent_probability")),
                "state_transfer": _parse_state_transfer(fix.get("stateTransfer") or fix.get("StateTransfer") or fix.get("state_transfer")),
            }
            forecast_points.append(fp)

        forecast_points.sort(key=lambda pt: (pt.get("tau") or 0, pt.get("valid_time") or ""))

        cyclones.append({
            "id": tc_id,
            "year": year,
            "name_en": name_en,
            "name_zh": name_zh,
            "cwa_td_no": cwa_td_no,
            "cwa_ty_no": cwa_ty_no,
            "analysis_points": analysis_points,
            "current": current_pt,
            "forecast_points": forecast_points,
        })

    if not updated_at and cyclones:
        for c in cyclones:
            if c.get("current") and c["current"].get("time"):
                updated_at = c["current"]["time"]
                break

    return {
        "dataset_id": "W-C0034-005",
        "updated_at": updated_at,
        "active_count": len(cyclones),
        "cyclones": cyclones,
    }


