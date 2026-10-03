"""Fetch 1-week weather forecast from CWA Open Data API and output safe summary."""

import json
import sys
from pathlib import Path

from app.clients.cwa_client import CWAClient, CWAClientError
from app.core.config import get_settings


def fetch_and_summarize() -> None:
    """Fetch CWA forecast, save fixture, and display a safe summary without exposing secrets."""
    settings = get_settings()

    if not settings.cwa_api_key:
        print("ERROR: CWA_API_KEY is not configured in .env", file=sys.stderr)
        sys.exit(1)

    print("Fetching 1-week forecast from CWA API (F-C0032-005)...")
    client = CWAClient(timeout=20.0)

    try:
        data = client.fetch_forecast_1week()
    except CWAClientError as exc:
        print(f"ERROR: CWA API request failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Security verification: Ensure raw API key is never in the payload
    data_str = json.dumps(data)
    if settings.cwa_api_key in data_str:
        print("SECURITY ERROR: API Key detected in payload! Aborting.", file=sys.stderr)
        sys.exit(1)

    # Extract summary info safely (supporting both File API cwaopendata and Datastore records)
    if "cwaopendata" in data:
        cwa_obj = data.get("cwaopendata", {})
        dataset_obj = cwa_obj.get("dataset", {})
        dataset_info = dataset_obj.get("datasetInfo", {})
        dataset_description = dataset_info.get("datasetDescription", "一週天氣預報")
        location_list = dataset_obj.get("location", [])
        request_success = "True (Status: " + str(cwa_obj.get("status", "Actual")) + ")"
    else:
        records_obj = data.get("records", {})
        dataset_description = records_obj.get("datasetDescription", "N/A")
        location_list = records_obj.get("location", [])
        request_success = str(data.get("success", "true"))

    location_count = len(location_list)
    first_location_name = "N/A"
    weather_element_names = []
    if location_list:
        first_loc = location_list[0]
        first_location_name = first_loc.get("locationName", "N/A")
        elements = first_loc.get("weatherElement", [])
        weather_element_names = [el.get("elementName") for el in elements if "elementName" in el]

    # Save to tests/fixtures/cwa_f_c0032_005_sample.json
    output_dir = Path("tests/fixtures")
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_file = output_dir / "cwa_f_c0032_005_sample.json"

    with open(sample_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n--- CWA Fetch Summary ---")
    print(f"Request success        : {request_success}")
    print(f"Dataset ID             : {CWAClient.DATASET_FORECAST_1WEEK}")
    print(f"Dataset description    : {dataset_description}")
    print(f"Location count         : {location_count}")
    print(f"First location name    : {first_location_name}")
    print(f"WeatherElement names   : {weather_element_names}")
    print(f"Sample JSON saved to   : {sample_file.as_posix()} ({sample_file.stat().st_size:,} bytes)")
    print("-------------------------\n")


def main() -> None:
    fetch_and_summarize()


if __name__ == "__main__":
    main()
