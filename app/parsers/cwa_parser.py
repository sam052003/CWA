"""CWA JSON Parser - parses and normalizes raw CWA JSON payload into structured forecast records."""

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
