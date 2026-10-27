"""Add a panel, log in to it again, or point an entry at its new address."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol
from yarl import URL

from .api import (
    NodeCSAuthError,
    NodeCSCertificateError,
    NodeCSClient,
    NodeCSConnectionError,
    NodeCSResponseError,
)
from .const import DOMAIN, GRAPHQL_PATH, SETUP_TIMEOUT

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
_DEFAULT_PORTS = {"http": 80, "https": 443}

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): _PASSWORD,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)
REAUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): _PASSWORD}
)
RECONFIGURE_SCHEMA = vol.Schema(
    {vol.Required(CONF_URL): str, vol.Required(CONF_VERIFY_SSL): bool}
)


def normalize_url(raw: str) -> str:
    """The panel's scheme, host and port from whatever was typed or pasted.

    A bare host gets https. The API's own path is accepted, so a pasted endpoint
    works; any other path is refused.
    """
    text = raw.strip()
    if not text:
        raise ValueError("empty URL")
    if "://" not in text:
        text = f"https://{text}"
    url = URL(text)
    if url.scheme not in _DEFAULT_PORTS or not url.host:
        raise ValueError(f"not a panel address: {raw!r}")
    path = url.path.rstrip("/")
    if path in (GRAPHQL_PATH, GRAPHQL_PATH.rstrip("/")):
        path = ""
    if path or url.query_string or url.fragment:
        raise ValueError(f"a page, not the panel's address: {raw!r}")
    port = url.explicit_port
    if port == _DEFAULT_PORTS[url.scheme]:
        port = None
    return str(URL.build(scheme=url.scheme, host=url.host.lower(), port=port))


def unique_id_for(url: str) -> str:
    """host:port, with the scheme's default port filled in."""
    parsed = URL(url)
    return f"{parsed.host}:{parsed.port}"


class NodeCSConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per panel."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the panel's address and login, and check them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                url = normalize_url(user_input[CONF_URL])
            except ValueError:
                errors[CONF_URL] = "invalid_url"
            else:
                await self.async_set_unique_id(unique_id_for(url))
                self._abort_if_unique_id_configured()
                data = {
                    CONF_URL: url,
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                }
                if not (error := await self._async_check(data)):
                    return self.async_create_entry(title=URL(url).host, data=data)
                errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """The panel refused the saved login."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the login again, and check it."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (error := await self._async_check({**entry.data, **user_input})):
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, {CONF_USERNAME: entry.data[CONF_USERNAME]}
            ),
            errors=errors,
            description_placeholders={"url": entry.data[CONF_URL]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point the entry at the panel's new address or certificate setting."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                url = normalize_url(user_input[CONF_URL])
            except ValueError:
                errors[CONF_URL] = "invalid_url"
            else:
                unique_id = unique_id_for(url)
                await self.async_set_unique_id(unique_id)
                if unique_id != entry.unique_id:
                    self._abort_if_unique_id_configured()
                updates = {CONF_URL: url, CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL]}
                if not (error := await self._async_check({**entry.data, **updates})):
                    title = entry.title
                    if title == URL(entry.data[CONF_URL]).host:
                        title = URL(url).host
                    return self.async_update_reload_and_abort(
                        entry, unique_id=unique_id, title=title, data_updates=updates
                    )
                errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def _async_check(self, data: Mapping[str, Any]) -> str | None:
        """Read the panel once; the form's error key if that fails."""
        client = NodeCSClient(
            async_get_clientsession(self.hass, verify_ssl=data[CONF_VERIFY_SSL]),
            data[CONF_URL],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        try:
            await client.fetch_matches(timeout=SETUP_TIMEOUT)
        except NodeCSCertificateError:
            return "certificate_error"
        except NodeCSConnectionError:
            return "cannot_connect"
        except NodeCSAuthError:
            return "invalid_auth"
        except NodeCSResponseError:
            return "invalid_reply"
        except Exception:
            _LOGGER.exception("Unexpected error reading %s", data[CONF_URL])
            return "unknown"
        return None
