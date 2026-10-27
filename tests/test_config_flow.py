"""Tests for adding, re-authenticating and reconfiguring a panel."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.nodecs.api import (
    NodeCSAuthError,
    NodeCSCertificateError,
    NodeCSConnectionError,
    NodeCSResponseError,
)
from custom_components.nodecs.config_flow import normalize_url, unique_id_for
from custom_components.nodecs.const import DOMAIN

from .conftest import PASSWORD, USERNAME
from .payloads import BASE, GRAPHQL, matches_reply, server_json

USER_INPUT = {
    CONF_URL: "panel.example.lan",
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_VERIFY_SSL: True,
}


@pytest.fixture(autouse=True)
def no_setup() -> Iterator[None]:
    """Creating an entry must not set the integration up in these tests."""
    with patch(
        "custom_components.nodecs.async_setup_entry", return_value=True, create=True
    ):
        yield


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("panel.example.lan", "https://panel.example.lan"),
        ("  https://Panel.Example.lan/ ", "https://panel.example.lan"),
        ("http://10.0.0.5:8080", "http://10.0.0.5:8080"),
        ("https://panel.example.lan/api/ui/graphql/query", "https://panel.example.lan"),
        ("https://panel.example.lan:443", "https://panel.example.lan"),
        ("https://panel.example.lan:8443/", "https://panel.example.lan:8443"),
        ("https://[2001:db8::1]:8443", "https://[2001:db8::1]:8443"),
    ],
)
def test_normalize_url(raw: str, expected: str) -> None:
    """Pasted addresses are reduced to scheme, host and port."""
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "ftp://panel.example.lan", "https://panel.example.lan/dashboard", "https://"],
)
def test_normalize_url_refuses(raw: str) -> None:
    """Anything that is not the panel's address is refused."""
    with pytest.raises(ValueError):
        normalize_url(raw)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://panel.example.lan", "panel.example.lan:443"),
        ("http://10.0.0.5", "10.0.0.5:80"),
        ("https://panel.example.lan:8443", "panel.example.lan:8443"),
    ],
)
def test_unique_id_for(url: str, expected: str) -> None:
    """One entry per host and port."""
    assert unique_id_for(url) == expected


async def _start(hass: HomeAssistant) -> dict[str, Any]:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A panel that answers is saved, with the address normalised."""
    aioclient_mock.post(GRAPHQL, json=matches_reply(server_json()))
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "panel.example.lan"
    assert result["data"] == {
        CONF_URL: BASE,
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == "panel.example.lan:443"


@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        (NodeCSConnectionError("down"), {"base": "cannot_connect"}),
        (NodeCSCertificateError("untrusted"), {"base": "certificate_error"}),
        (NodeCSAuthError("401"), {"base": "invalid_auth"}),
        (NodeCSResponseError("html"), {"base": "invalid_reply"}),
        (RuntimeError("bug"), {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    side_effect: Exception,
    errors: dict[str, str],
) -> None:
    """Each failure is named on the form, and a retry still works."""
    result = await _start(hass)
    with patch(
        "custom_components.nodecs.config_flow.NodeCSClient.fetch_matches",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    aioclient_mock.post(GRAPHQL, json=matches_reply())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_bad_url(hass: HomeAssistant) -> None:
    """A URL with a path is refused on the URL field."""
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_URL: "https://panel.example.lan/x"}
    )
    assert result["errors"] == {CONF_URL: "invalid_url"}


async def test_user_flow_verify_ssl_off(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Unticking the box uses Home Assistant's unverified session."""
    aioclient_mock.post(GRAPHQL, json=matches_reply())
    result = await _start(hass)
    with patch(
        "custom_components.nodecs.config_flow.async_get_clientsession",
        wraps=async_get_clientsession,
    ) as get_session:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**USER_INPUT, CONF_VERIFY_SSL: False}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_VERIFY_SSL] is False
    assert get_session.call_args.kwargs["verify_ssl"] is False


async def test_duplicate_aborts(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The same panel cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.post(GRAPHQL, json=matches_reply())
    result = await _start(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_URL: "https://PANEL.example.lan/"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_updates_login(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A new password is checked, then saved."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.post(GRAPHQL, status=401, text="<html>")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: "wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.post(GRAPHQL, json=matches_reply())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: "new"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new"
    assert mock_config_entry.data[CONF_URL] == BASE


async def test_reconfigure_changes_url_and_ssl(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A moved panel keeps its entry; the address and certificate setting change."""
    mock_config_entry.add_to_hass(hass)
    aioclient_mock.post(
        "https://panel2.example.lan/api/ui/graphql/query", json=matches_reply()
    )
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://panel2.example.lan", CONF_VERIFY_SSL: False},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_URL] == "https://panel2.example.lan"
    assert mock_config_entry.data[CONF_VERIFY_SSL] is False
    assert mock_config_entry.data[CONF_PASSWORD] == PASSWORD
    assert mock_config_entry.unique_id == "panel2.example.lan:443"


async def test_reconfigure_onto_another_panel_aborts(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Two entries can never point at the same panel."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN, unique_id="panel2.example.lan:443", data={}
    ).add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "https://panel2.example.lan", CONF_VERIFY_SSL: True},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
