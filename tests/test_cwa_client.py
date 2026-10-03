"""Unit tests for CWA API Client (using mock responses, no real network calls)."""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app.clients.cwa_client import (
    CWAClient,
    CWAClientError,
    CWAConnectionError,
    CWAHTTPError,
    CWAInvalidJSONError,
    CWAMissingAPIKeyError,
    CWARequestFailedError,
    CWATimeoutError,
)


@pytest.fixture
def mock_client():
    """Return a CWAClient initialized with a dummy test key."""
    return CWAClient(api_key="CWA-TEST-DUMMY-KEY-12345", timeout=5.0)


def test_missing_api_key():
    """Verify CWAMissingAPIKeyError is raised when API key is missing."""
    client = CWAClient(api_key="")
    with pytest.raises(CWAMissingAPIKeyError) as exc_info:
        client.fetch_forecast_1week()
    assert "CWA_API_KEY is not configured" in str(exc_info.value)


@patch("requests.get")
def test_successful_response(mock_get, mock_client):
    """Verify successful response returns parsed payload."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": "true",
        "result": {"resource_id": "F-C0032-005"},
        "records": {"location": []},
    }
    mock_get.return_value = mock_resp

    data = mock_client.fetch_forecast_1week()

    assert data["success"] == "true"
    assert "records" in data
    mock_get.assert_called_once()
    # Verify Authorization header was passed without leaking in URL
    call_kwargs = mock_get.call_args[1]
    assert call_kwargs["headers"]["Authorization"] == "CWA-TEST-DUMMY-KEY-12345"


@patch("requests.get")
def test_timeout_error(mock_get, mock_client):
    """Verify CWATimeoutError is raised when request times out."""
    mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

    with pytest.raises(CWATimeoutError) as exc_info:
        mock_client.fetch_forecast_1week()
    assert "timed out after" in str(exc_info.value)


@patch("requests.get")
def test_connection_error(mock_get, mock_client):
    """Verify CWAConnectionError is raised when connection fails."""
    mock_get.side_effect = requests.exceptions.ConnectionError("DNS lookup failed")

    with pytest.raises(CWAConnectionError) as exc_info:
        mock_client.fetch_forecast_1week()
    assert "Failed to connect to CWA API endpoint" in str(exc_info.value)


@patch("requests.get")
def test_non_2xx_response(mock_get, mock_client):
    """Verify CWAHTTPError is raised for non-2xx HTTP status codes."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_get.return_value = mock_resp

    with pytest.raises(CWAHTTPError) as exc_info:
        mock_client.fetch_dataset("NON_EXISTENT_DATASET")
    assert exc_info.value.status_code == 500
    assert "500" in str(exc_info.value)


@patch("requests.get")
def test_invalid_json(mock_get, mock_client):
    """Verify CWAInvalidJSONError is raised when response is not valid JSON."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value = mock_resp

    with pytest.raises(CWAInvalidJSONError) as exc_info:
        mock_client.fetch_forecast_1week()
    assert "Failed to parse CWA response" in str(exc_info.value)


@patch("requests.get")
def test_request_failed_success_false(mock_get, mock_client):
    """Verify CWARequestFailedError is raised when success=false in JSON."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": "false",
        "result": {"message": "Invalid request parameters"},
    }
    mock_get.return_value = mock_resp

    with pytest.raises(CWARequestFailedError) as exc_info:
        mock_client.fetch_forecast_1week()
    assert "unsuccessful status" in str(exc_info.value)


# ==============================================================================
# Fallback Tests: Datastore API (404) -> File API
# ==============================================================================


@patch("requests.get")
def test_fallback_successful_response(mock_get, mock_client):
    """Verify Datastore 404 seamlessly falls back to File API 200 and returns payload."""
    datastore_404 = MagicMock(status_code=404)
    fileapi_200 = MagicMock(status_code=200)
    fileapi_200.json.return_value = {
        "cwaopendata": {
            "dataset": {
                "datasetInfo": {"datasetDescription": "一週天氣預報"},
                "location": [{"locationName": "臺北市"}],
            }
        }
    }
    mock_get.side_effect = [datastore_404, fileapi_200]

    data = mock_client.fetch_forecast_1week()

    assert mock_get.call_count == 2
    assert "cwaopendata" in data
    # Verify fallback URL targeted File API with format=JSON
    second_call_url = mock_get.call_args_list[1][0][0]
    second_call_params = mock_get.call_args_list[1][1]["params"]
    assert "fileapi/v1/opendataapi/F-C0032-005" in second_call_url
    assert second_call_params.get("format") == "JSON"


@patch("requests.get")
def test_fallback_timeout_error(mock_get, mock_client):
    """Verify Datastore 404 -> File API timeout properly raises CWATimeoutError."""
    datastore_404 = MagicMock(status_code=404)
    mock_get.side_effect = [
        datastore_404,
        requests.exceptions.Timeout("File API timed out"),
    ]

    with pytest.raises(CWATimeoutError) as exc_info:
        mock_client.fetch_forecast_1week()

    assert mock_get.call_count == 2
    assert "CWA File API dataset 'F-C0032-005' timed out" in str(exc_info.value)


@patch("requests.get")
def test_fallback_connection_error(mock_get, mock_client):
    """Verify Datastore 404 -> File API connection error properly raises CWAConnectionError."""
    datastore_404 = MagicMock(status_code=404)
    mock_get.side_effect = [
        datastore_404,
        requests.exceptions.ConnectionError("File API connection failed"),
    ]

    with pytest.raises(CWAConnectionError) as exc_info:
        mock_client.fetch_forecast_1week()

    assert mock_get.call_count == 2
    assert "Failed to connect to CWA File API endpoint" in str(exc_info.value)


@patch("requests.get")
def test_fallback_non_2xx_response(mock_get, mock_client):
    """Verify Datastore 404 -> File API non-2xx (e.g. 500) properly raises CWAHTTPError."""
    datastore_404 = MagicMock(status_code=404)
    fileapi_500 = MagicMock(status_code=500)
    mock_get.side_effect = [datastore_404, fileapi_500]

    with pytest.raises(CWAHTTPError) as exc_info:
        mock_client.fetch_forecast_1week()

    assert mock_get.call_count == 2
    assert exc_info.value.status_code == 500
    assert "500" in str(exc_info.value)


@patch("requests.get")
def test_fallback_invalid_json(mock_get, mock_client):
    """Verify Datastore 404 -> File API invalid JSON properly raises CWAInvalidJSONError."""
    datastore_404 = MagicMock(status_code=404)
    fileapi_invalid_json = MagicMock(status_code=200)
    fileapi_invalid_json.json.side_effect = ValueError("Corrupted JSON body")
    mock_get.side_effect = [datastore_404, fileapi_invalid_json]

    with pytest.raises(CWAInvalidJSONError) as exc_info:
        mock_client.fetch_forecast_1week()

    assert mock_get.call_count == 2
    assert "Failed to parse CWA response" in str(exc_info.value)
