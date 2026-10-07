"""CWA Open Data API Client - handles HTTP requests, authentication, and error handling."""

from typing import Any, Dict, Optional
import requests

from app.core.config import get_settings


class CWAClientError(Exception):
    """Base exception for all CWA client errors."""
    pass


class CWAMissingAPIKeyError(CWAClientError):
    """Raised when CWA_API_KEY is not configured or provided."""
    pass


class CWATimeoutError(CWAClientError):
    """Raised when the request to CWA API times out."""
    pass


class CWAConnectionError(CWAClientError):
    """Raised when connection to CWA API fails."""
    pass


class CWAHTTPError(CWAClientError):
    """Raised when CWA API returns a non-2xx HTTP status code."""

    def __init__(self, status_code: int, message: str = "HTTP request failed"):
        super().__init__(f"CWA API returned HTTP {status_code}: {message}")
        self.status_code = status_code


class CWAInvalidJSONError(CWAClientError):
    """Raised when CWA API returns a response that cannot be parsed as JSON."""
    pass


class CWARequestFailedError(CWAClientError):
    """Raised when CWA API returns success=false in JSON response."""
    pass


class CWAClient:
    """Client for retrieving data from Central Weather Administration (CWA) Open Data API."""

    DEFAULT_BASE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
    FILE_API_BASE_URL = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi"
    DATASET_FORECAST_1WEEK = "F-C0032-005"
    DATASET_FORECAST_36H = "F-C0032-001"
    DATASET_OBSERVATION = "O-A0001"
    DEFAULT_TIMEOUT = 15.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.cwa_api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def fetch_forecast_1week(self) -> Dict[str, Any]:
        """Fetch 1-week weather forecast dataset (F-C0032-005)."""
        return self.fetch_dataset(self.DATASET_FORECAST_1WEEK)

    def fetch_forecast_36h(self, region_name: Optional[str] = None) -> Dict[str, Any]:
        """Fetch 36-hour weather forecast dataset (F-C0032-001).

        Args:
            region_name: Optional county name filter, e.g. '臺中市'.
                         When supplied, sets locationName query parameter.
        """
        params: Optional[Dict[str, Any]] = None
        if region_name and region_name.strip():
            params = {"locationName": region_name.strip()}
        return self.fetch_dataset(self.DATASET_FORECAST_36H, params=params)

    def fetch_observations(self) -> Dict[str, Any]:
        """Fetch current weather observations dataset (O-A0001)."""
        return self.fetch_dataset(self.DATASET_OBSERVATION)

    def fetch_dataset(
        self,
        dataset_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch a specific dataset from CWA Open Data API.

        Calls the Datastore API endpoint first (https://opendata.cwa.gov.tw/api/v1/rest/datastore/{dataset_id}).
        If dataset F-C0032-005 returns 404 from datastore (due to CWA publishing it under Open Data File API),
        falls back to https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/{dataset_id}?format=JSON.

        Raises:
            CWAMissingAPIKeyError: If API key is missing.
            CWATimeoutError: If HTTP request times out.
            CWAConnectionError: If network connection fails.
            CWAHTTPError: If HTTP status code is non-2xx.
            CWAInvalidJSONError: If response body is not valid JSON.
            CWARequestFailedError: If CWA JSON payload has success=false.
            CWAClientError: For any other request failure.
        """
        if not self._api_key:
            raise CWAMissingAPIKeyError(
                "CWA_API_KEY is not configured. Please set it in .env or environment variables."
            )

        url = f"{self.base_url}/{dataset_id}"
        headers = {
            "Authorization": self._api_key,
            "Accept": "application/json",
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise CWATimeoutError(
                f"Request to CWA dataset '{dataset_id}' timed out after {self.timeout}s."
            ) from exc
        except requests.exceptions.SSLError as exc:
            raise CWAConnectionError(
                f"TLS verification failed for CWA dataset '{dataset_id}'."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise CWAConnectionError(
                f"Failed to connect to CWA API endpoint for dataset '{dataset_id}'."
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise CWAClientError(
                f"HTTP request to CWA API dataset '{dataset_id}' failed: {exc.__class__.__name__}"
            ) from exc

        # Handle CWA platform difference: F-C0032-005 returns 404 on datastore, fallback to File API
        if response.status_code == 404 and dataset_id == self.DATASET_FORECAST_1WEEK:
            file_url = f"{self.FILE_API_BASE_URL}/{dataset_id}"
            file_params = dict(params or {})
            file_params.setdefault("format", "JSON")
            try:
                response = requests.get(
                    file_url,
                    headers=headers,
                    params=file_params,
                    timeout=self.timeout,
                )
            except requests.exceptions.Timeout as exc:
                raise CWATimeoutError(
                    f"Request to CWA File API dataset '{dataset_id}' timed out after {self.timeout}s."
                ) from exc
            except requests.exceptions.SSLError as exc:
                raise CWAConnectionError(
                    f"TLS verification failed for CWA dataset '{dataset_id}'."
                ) from exc
            except requests.exceptions.ConnectionError as exc:
                raise CWAConnectionError(
                    f"Failed to connect to CWA File API endpoint for dataset '{dataset_id}'."
                ) from exc
            except requests.exceptions.RequestException as exc:
                raise CWAClientError(
                    f"HTTP request to CWA File API dataset '{dataset_id}' failed: {exc.__class__.__name__}"
                ) from exc

        # Handle CWA platform difference: O-A0001 in Datastore REST API is published under resource ID O-A0001-001
        if response.status_code == 404 and dataset_id in (self.DATASET_OBSERVATION, "O-A0001"):
            alt_url = f"{self.base_url}/O-A0001-001"
            try:
                response = requests.get(
                    alt_url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                )
            except requests.exceptions.Timeout as exc:
                raise CWATimeoutError(
                    f"Request to CWA Datastore dataset 'O-A0001-001' timed out after {self.timeout}s."
                ) from exc
            except requests.exceptions.SSLError as exc:
                raise CWAConnectionError(
                    f"TLS verification failed for CWA dataset 'O-A0001-001'."
                ) from exc
            except requests.exceptions.ConnectionError as exc:
                raise CWAConnectionError(
                    f"Failed to connect to CWA API endpoint for dataset 'O-A0001-001'."
                ) from exc
            except requests.exceptions.RequestException as exc:
                raise CWAClientError(
                    f"HTTP request to CWA API dataset 'O-A0001-001' failed: {exc.__class__.__name__}"
                ) from exc

        if not (200 <= response.status_code < 300):
            raise CWAHTTPError(
                status_code=response.status_code,
                message=f"Dataset '{dataset_id}' request failed with status {response.status_code}.",
            )

        try:
            payload = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as exc:
            raise CWAInvalidJSONError(
                f"Failed to parse CWA response for dataset '{dataset_id}' as JSON."
            ) from exc

        # Check payload success flag if present
        if "success" in payload:
            success_val = str(payload.get("success", "")).strip().lower()
            if success_val != "true":
                raise CWARequestFailedError(
                    f"CWA API returned unsuccessful status for dataset '{dataset_id}' (success={payload.get('success')})."
                )

        return payload
