"""Unit tests for CWA API Client (using mock responses, no real network calls)."""

from unittest.mock import MagicMock, patch
import pytest
import requests

from app.clients.cwa_client import (
    CWAClient,
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
