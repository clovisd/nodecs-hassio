"""Fixtures for the NodeCS tests."""

from __future__ import annotations

from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nodecs.const import DOMAIN

from .payloads import BASE

USERNAME = "admin"
PASSWORD = "hunter2"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry for the panel at panel.example.lan."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="panel.example.lan",
        data={
            CONF_URL: BASE,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_VERIFY_SSL: True,
        },
        unique_id="panel.example.lan:443",
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
