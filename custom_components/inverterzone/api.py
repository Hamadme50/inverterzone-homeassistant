"""Client for the inverterzone cloud's Home Assistant API (/api/home).

Every response is an envelope: {"success": bool, "error": code, "message": text, "data": ...}.
Failures carry a real HTTP status (400/401/403/404/500) and a machine-readable error code.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import BASE_URL, REQUEST_TIMEOUT


class InverterZoneError(Exception):
    """Base error for the inverterzone API."""

    def __init__(self, message: str, code: str | None = None) -> None:
        """Keep the API error code next to the message."""
        super().__init__(message)
        self.code = code


class InverterZoneConnectionError(InverterZoneError):
    """The cloud could not be reached or answered with a server error."""


class InverterZoneAuthError(InverterZoneError):
    """Wrong email or password, or the token is invalid, expired or revoked."""


class InverterZoneDeviceNotLinkedError(InverterZoneError):
    """The device is no longer attached to the account."""


class InverterZoneNoDataError(InverterZoneError):
    """The device has not sent any reading yet."""


@dataclass(frozen=True, slots=True)
class Device:
    """An inverter (dongle) on the account."""

    mac: str
    name: str | None
    model: str | None
    brand: str | None
    online: bool

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Device:
        """Build from the API's device object."""
        return cls(
            mac=str(raw["mac"]),
            name=raw.get("name") or None,
            model=raw.get("model") or None,
            brand=raw.get("brand") or None,
            online=bool(raw.get("online")),
        )


@dataclass(frozen=True, slots=True)
class ConnectResult:
    """A fresh token and the account's devices."""

    token: str
    expires_at: str | None
    devices: list[Device]


class InverterZoneApi:
    """Talks to the inverterzone cloud on Home Assistant's shared aiohttp session."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        token: str | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        """Set up the client. Pass the stored token, or call connect() first."""
        self._session = session
        self._token = token
        self._base_url = base_url.rstrip("/")

    @property
    def token(self) -> str | None:
        """The bearer token in use."""
        return self._token

    async def connect(self, email: str, password: str) -> ConnectResult:
        """Sign in with the account email and password and keep the returned token."""
        data = await self._request(
            "POST",
            "/getConnected",
            json={"email": email, "password": password},
            auth=False,
        )
        if not isinstance(data, dict) or not data.get("token"):
            raise InverterZoneConnectionError("Sign-in answer has no token")
        self._token = str(data["token"])
        return ConnectResult(
            token=self._token,
            expires_at=data.get("expiresAt"),
            devices=[Device.from_api(d) for d in data.get("devices") or []],
        )

    async def devices(self) -> list[Device]:
        """The inverters on the account."""
        data = await self._request("GET", "/getDevices")
        if not isinstance(data, list):
            raise InverterZoneConnectionError("Device list has an unexpected shape")
        return [Device.from_api(d) for d in data]

    async def solar_data(self, mac: str) -> dict[str, Any]:
        """The latest live reading of one inverter."""
        return await self._object("/getSolarData", mac)

    async def energy_data(self, mac: str) -> dict[str, Any]:
        """Today's energy totals of one inverter."""
        return await self._object("/getEnergyData", mac)

    async def _object(self, path: str, mac: str) -> dict[str, Any]:
        data = await self._request("GET", path, params={"mac": mac})
        if not isinstance(data, dict):
            raise InverterZoneConnectionError(f"{path} answered with an unexpected shape")
        return data

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if auth:
            if not self._token:
                raise InverterZoneAuthError("Not signed in", "TOKEN_MISSING")
            headers["Authorization"] = f"Bearer {self._token}"

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.request(
                    method,
                    self._base_url + path,
                    params=params,
                    json=json,
                    headers=headers,
                ) as response:
                    status = response.status
                    try:
                        body = await response.json(content_type=None)
                    except (aiohttp.ContentTypeError, ValueError):
                        body = None
        except (TimeoutError, aiohttp.ClientError) as err:
            raise InverterZoneConnectionError(
                f"Cannot reach the inverterzone cloud: {err!r}"
            ) from err

        if status == 200 and isinstance(body, dict) and body.get("success") is True:
            return body.get("data")

        code = body.get("error") if isinstance(body, dict) else None
        message = (body.get("message") if isinstance(body, dict) else None) or f"HTTP {status}"
        if status == 401 or code == "INVALID_CREDENTIALS":
            raise InverterZoneAuthError(message, code)
        if status == 403 or code == "DEVICE_NOT_LINKED":
            raise InverterZoneDeviceNotLinkedError(message, code)
        if code == "NO_DATA":
            raise InverterZoneNoDataError(message, code)
        raise InverterZoneConnectionError(f"{message} (HTTP {status}, {code})", code)
