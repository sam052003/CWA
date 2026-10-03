import json
from pathlib import Path

EXPECTED_22_COUNTIES = {
    "基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣",
    "苗栗縣", "臺中市", "彰化縣", "南投縣", "雲林縣", "嘉義市",
    "嘉義縣", "臺南市", "高雄市", "屏東縣", "宜蘭縣", "花蓮縣",
    "臺東縣", "澎湖縣", "金門縣", "連江縣",
}


def test_taiwan_counties_geojson_exists_and_valid():
    """Verify that taiwan_counties.geojson exists, parses cleanly, and is a FeatureCollection."""
    geojson_path = Path(__file__).resolve().parent.parent / "app" / "static" / "data" / "taiwan_counties.geojson"
    assert geojson_path.exists(), f"GeoJSON file does not exist at {geojson_path}"

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("type") == "FeatureCollection"
    assert "features" in data
    assert len(data["features"]) == 22, f"Expected exactly 22 features, got {len(data['features'])}"


def test_taiwan_counties_names_match_cwa_regions():
    """Verify that every feature has a county name matching the official 22 CWA region set."""
    geojson_path = Path(__file__).resolve().parent.parent / "app" / "static" / "data" / "taiwan_counties.geojson"
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    geojson_counties = set()
    for feature in data["features"]:
        props = feature.get("properties", {})
        name = props.get("COUNTYNAME") or props.get("name")
        assert name, f"Feature missing COUNTYNAME/name property: {feature}"
        assert isinstance(name, str) and len(name.strip()) > 0
        geojson_counties.add(name.strip())

    assert geojson_counties == EXPECTED_22_COUNTIES, (
        f"Mismatch between GeoJSON counties and expected regions.\n"
        f"Missing: {EXPECTED_22_COUNTIES - geojson_counties}\n"
        f"Extra: {geojson_counties - EXPECTED_22_COUNTIES}"
    )

    # Cross-verify with the official CWA sample fixture
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "cwa_f_c0032_005_sample.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)
        locations = fixture_data["cwaopendata"]["dataset"]["location"]
        fixture_counties = {loc["locationName"] for loc in locations}
        assert geojson_counties == fixture_counties


def test_taiwan_counties_geometry_types_and_wgs84_bounds():
    """Verify that geometries are Polygon or MultiPolygon with coordinates in plausible WGS84 Taiwan bounds."""
    geojson_path = Path(__file__).resolve().parent.parent / "app" / "static" / "data" / "taiwan_counties.geojson"
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Taiwan and offshore islands (Kinmen, Matsu, Penghu) lie within:
    # Longitude: ~118.0 to ~123.5 E
    # Latitude: ~21.5 to ~26.5 N
    min_lon, max_lon = 118.0, 123.5
    min_lat, max_lat = 21.5, 26.5

    for feature in data["features"]:
        geometry = feature.get("geometry", {})
        gtype = geometry.get("type")
        assert gtype in ("Polygon", "MultiPolygon"), f"Unexpected geometry type: {gtype}"

        coords = geometry.get("coordinates", [])
        assert len(coords) > 0, f"Empty coordinates for feature {feature.get('properties')}"

        def check_coords(ring):
            for pt in ring:
                if isinstance(pt[0], list):
                    check_coords(pt)
                else:
                    lon, lat = pt[0], pt[1]
                    assert min_lon <= lon <= max_lon, f"Longitude {lon} out of Taiwan WGS84 range ({min_lon}, {max_lon})"
                    assert min_lat <= lat <= max_lat, f"Latitude {lat} out of Taiwan WGS84 range ({min_lat}, {max_lat})"

        check_coords(coords)
