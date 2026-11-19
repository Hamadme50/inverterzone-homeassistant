"""Config flow for inverterzone: sign in once, keep only the token."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import ConnectResult, InverterZoneApi, InverterZoneAuthError, InverterZoneError
from .const import CONF_EXPIRES_AT, CONF_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

_EMAIL = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username"))
_PASSWORD = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): _EMAIL,
        vol.Required(CONF_PASSWORD): _PASSWORD,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD})


class InverterZoneConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sign in to an inverterzone account."""

    VERSION = 1

    async def _connect(
        self, email: str, password: str
    ) -> tuple[ConnectResult | None, dict[str, str]]:
        """Sign in. Returns the result, or the form errors to show."""
        api = InverterZoneApi(async_get_clientsession(self.hass))
        try:
            return await api.connect(email, password), {}
        except InverterZoneAuthError:
            return None, {"base": "invalid_auth"}
        except InverterZoneError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error signing in to inverterzone")
            return None, {"base": "unknown"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the account email and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            result, errors = await self._connect(email, user_input[CONF_PASSWORD])
            if result is not None and not result.devices:
                errors = {"base": "no_devices"}
            elif result is not None:
                # The password is not stored: the token is enough, and a reauth asks again.
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_TOKEN: result.token,
                        CONF_EXPIRES_AT: result.expires_at,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, {CONF_EMAIL: (user_input or {}).get(CONF_EMAIL)}
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The token expired or the account password changed."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password again and issue a new token."""
        entry = self._get_reauth_entry()
        email = entry.data[CONF_EMAIL]
        errors: dict[str, str] = {}
        if user_input is not None:
            result, errors = await self._connect(email, user_input[CONF_PASSWORD])
            if result is not None:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_TOKEN: result.token,
                        CONF_EXPIRES_AT: result.expires_at,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"email": email},
            errors=errors,
        )
