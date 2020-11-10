"""Minimal clients for the IIASA Scenario Explorer APIs."""
import json
from abc import ABC, abstractmethod

import requests


class BaseClient(ABC):
    """Abstract base class for clients."""

    base_url = None
    _token = None

    def url(self, *parts):
        """Return a URL under base_url by combining *parts*."""
        return "/".join([self.base_url] + list(parts))

    @abstractmethod
    def set_token(self):
        """Set the token.

        This is called for every call of :meth:`get` (via :meth:`with_token`),
        and must ensure that self._token is set.
        """
        pass

    def with_token(self, headers={}):
        """Modify *headers* to include the token."""
        self.set_token()
        headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def get(self, *endpoint, params={}, headers={}):
        """Execute a GET request against *endpoint*, with auth."""
        response = requests.get(
            url=self.url(*endpoint),
            params=params,
            headers=self.with_token(headers),
        )
        response.raise_for_status()
        return response.json()

    def post(self, *endpoint, data=None, params={}, headers={}):
        """Execute a POST request against *endpoint*, with auth."""
        response = requests.post(
            url=self.url(*endpoint),
            data=data,
            params=params,
            headers=self.with_token(headers),
        )
        response.raise_for_status()
        return response.json()


class AuthClient(BaseClient):
    """Client for the SE authentication API."""

    # Fixed base_url
    base_url = "https://db1.ene.iiasa.ac.at/EneAuth/config/v1"

    def __init__(self, **credentials):
        self.credentials = credentials

    def set_token(self):
        """Use the 'login' endpoint to get a token if none is set."""
        if self._token is not None:
            return

        r = requests.post(
            self.url("login"),
            headers={"Content-Type": "application/json"},
            data=json.dumps(self.credentials),
        )
        r.raise_for_status()
        self._token = r.json()

    # Particular endpoints
    def applications(self):
        """List of applications."""
        return self.get("applications")

    def app_config(self, name):
        """List of configuration keys for application **name**."""
        return self.get("applications", name, "config")

    # Convenience method
    def get_app(self, name):
        """Return a client for a particular application **name**."""
        app_config = {entry["path"]: entry["value"] for entry in self.app_config(name)}
        return AppClient(app_config["baseUrl"], app_config, self._token)


class AppClient(BaseClient):
    """Client for the SE application API."""

    def __init__(self, base_url, app_config, token):
        self.base_url = base_url
        self.config = app_config
        self._token = token

    def set_token(self, value=None):
        # Do nothing; use the token passed to the constructor
        pass

    # Endpoints
    def runs(self, get_only_default_runs=True):
        """List of model runs."""
        return self.get(
            "runs",
            params={"getOnlyDefaultRuns": str(get_only_default_runs).lower()},
        )

    def runs_bulk_ts(self, **filters):
        """Bulk timeseries data."""
        # NB the API returns 500 errors if any of these are not set
        for key in "regions", "runs", "times", "units", "variables", "years":
            filters.setdefault(key, [])

        return self.post(
            "runs/bulk/ts",
            data=json.dumps(dict(filters=filters)),
            headers={"Content-Type": "application/json"},
        )

    def variables(self, run_id, filters=[]):
        return self.get(f"runs/{run_id}/vars", params={"filters": "[]"})
