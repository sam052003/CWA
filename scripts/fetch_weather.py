"""Fetch 1-week weather forecast from CWA Open Data API and output safe summary."""

import argparse
import json
import sys
from pathlib import Path

from app.clients.cwa_client import CWAClient, CWAClientError
from app.core.config import get_settings
from app.db.database import SessionLocal
from app.parsers.cwa_parser import parse_cwa_forecast
from app.services.weather_service import refresh_forecasts, sanitize_error


def fetch_and_summarize(save_fixture: bool = False, save_db: bool = False) -> None:
    """Fetch CWA forecast, parse records, and display a safe summary without exposing secrets.

    Args:
        save_fixture: If True, writes raw payload to tests/fixtures/cwa_f_c0032_005_sample.json.
                      If False (default), fixture file is not modified.
        save_db: If True, triggers Weather Service refresh to persist records into Supabase PostgreSQL.
                 If False (default), database is not accessed or modified.
    """
    settings = get_settings()

    if not settings.cwa_api_key:
        print("ERROR: CWA_API_KEY is not configured in .env", file=sys.stderr)
        sys.exit(1)

    print("Fetching 1-week forecast from CWA API (F-C0032-005)...")
    client = CWAClient(timeout=20.0)

    try:
        data = client.fetch_forecast_1week()
    except CWAClientError as exc:
        print(f"ERROR: CWA API request failed: {sanitize_error(exc)}", file=sys.stderr)
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

    # Save fixture file only if explicitly requested via --save-fixture
    fixture_status = "[Skipped] (use --save-fixture to update fixture file)"
    if save_fixture:
        output_dir = Path("tests/fixtures")
        output_dir.mkdir(parents=True, exist_ok=True)
        sample_file = output_dir / "cwa_f_c0032_005_sample.json"
        with open(sample_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        fixture_status = f"Saved to {sample_file.as_posix()} ({sample_file.stat().st_size:,} bytes)"

    # Parse and validate records with CWAParser
    parsed_records = parse_cwa_forecast(data)
    parsed_regions = sorted(set(r["region_name"] for r in parsed_records))
    first_parsed_record = parsed_records[0] if parsed_records else None

    print("\n--- CWA Fetch Summary ---")
    print(f"Request success        : {request_success}")
    print(f"Dataset ID             : {CWAClient.DATASET_FORECAST_1WEEK}")
    print(f"Dataset description    : {dataset_description}")
    print(f"Raw location count     : {location_count}")
    print(f"First raw location     : {first_location_name}")
    print(f"WeatherElement names   : {weather_element_names}")
    print(f"Fixture update status  : {fixture_status}")
    print(f"Parsed records count   : {len(parsed_records)}")
    print(f"Parsed regions count   : {len(parsed_regions)}")
    print(f"First parsed record    : {first_parsed_record}")
    print("-------------------------\n")

    # Delegate database write to Weather Service if --save-db flag is provided
    if save_db:
        print("Writing parsed records to Supabase PostgreSQL via Weather Service...")
        session = SessionLocal()
        try:
            summary = refresh_forecasts(session=session, client=client)
            print("Database write success")
            print(f"Upserted forecast records: {summary['records_count']}")
            print(f"Regions: {summary['regions_count']}\n")
        except Exception as err:
            print(f"ERROR: {sanitize_error(err)}", file=sys.stderr)
            sys.exit(1)
        finally:
            session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch 1-week weather forecast from CWA Open Data API and display safe summary."
    )
    parser.add_argument(
        "--save-fixture",
        action="store_true",
        help="Explicitly save the fetched response to tests/fixtures/cwa_f_c0032_005_sample.json (default: False).",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        help="Explicitly persist parsed forecast records into Supabase PostgreSQL (default: False).",
    )
    args = parser.parse_args()
    fetch_and_summarize(save_fixture=args.save_fixture, save_db=args.save_db)


if __name__ == "__main__":
    main()
