"""NodeCS: a CS2 server panel's servers and matches in Home Assistant."""

from __future__ import annotations

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NodeCSClient
from .const import DOMAIN
from .coordinator import (
    MatchCoordinator,
    NodeCSConfigEntry,
    NodeCSRuntime,
    StatusCoordinator,
)
from .entity import panel_device_info, server_device_info
from .push import PushListener

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NodeCSConfigEntry) -> bool:
    """Read the panel, register its devices, and start listening for changes."""
    client = NodeCSClient(
        async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL]),
        entry.data[CONF_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    matches = MatchCoordinator(hass, entry, client)
    status = StatusCoordinator(hass, entry, client)
    await matches.async_config_entry_first_refresh()
    await status.async_config_entry_first_refresh()

    push = PushListener(hass, entry, client, matches.async_request_refresh)
    entry.runtime_data = NodeCSRuntime(client, matches, status, push)

    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=entry.entry_id, **panel_device_info(entry)
    )
    seen: set[tuple[str, str]] = set()

    @callback
    def sync_devices() -> None:
        """Add a device for each new server; follow the panel's renames."""
        current = {(server.id, server.name) for server in matches.data.values()}
        if current == seen:
            return
        for server_id, name in current - seen:
            registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                **server_device_info(entry, server_id, name),
            )
        seen.clear()
        seen.update(current)

    sync_devices()
    entry.async_on_unload(matches.async_add_listener(sync_devices))

    entry.async_create_background_task(
        hass, push.run(), f"{DOMAIN} live updates for {entry.title}"
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NodeCSConfigEntry) -> bool:
    """Stop reading; unloading cancels the live updates task."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: NodeCSConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Only a server the panel no longer has can be deleted."""
    kept = {(DOMAIN, f"{entry.entry_id}_panel")} | {
        (DOMAIN, f"{entry.entry_id}_{server_id}")
        for server_id in entry.runtime_data.matches.data
    }
    return not device_entry.identifiers & kept
