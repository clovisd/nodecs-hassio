"""Keeps the panel's push channel open and turns each message into a read."""

from __future__ import annotations

from asyncio import sleep
from collections.abc import Awaitable, Callable
import logging

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

from .api import NodeCSClient, NodeCSError
from .const import PUSH_RETRY_MAX, PUSH_RETRY_MIN
from .coordinator import NodeCSConfigEntry

_LOGGER = logging.getLogger(__name__)


class PushListener:
    """Holds the channel open; reconnects after 1 s, doubling to 30 s."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NodeCSConfigEntry,
        client: NodeCSClient,
        on_message: Callable[[], Awaitable[None]],
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._client = client
        self._on_message = on_message
        self._listeners: list[Callable[[], None]] = []
        self._down_logged = False
        self.connected = False

    @callback
    def async_add_listener(self, update_callback: Callable[[], None]) -> CALLBACK_TYPE:
        """Be told when the channel opens or closes."""
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    async def run(self) -> None:
        """Run until the entry unloads, which cancels this task."""
        delay = PUSH_RETRY_MIN
        while True:
            try:
                channel = await self._client.open_push()
            except NodeCSError as err:
                self._log_down(err)
            except Exception:
                _LOGGER.exception(
                    "Unexpected error opening %s's live updates", self._name
                )
                self._down_logged = True
            else:
                delay = PUSH_RETRY_MIN
                if self._down_logged:
                    _LOGGER.info("Live updates from %s are back", self._name)
                    self._down_logged = False
                self._set_connected(True)
                try:
                    async for _message in channel:
                        await self._on_message()
                except NodeCSError as err:
                    self._log_down(err)
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error in %s's live updates", self._name
                    )
                    self._down_logged = True
                finally:
                    self._set_connected(False)
                    await channel.close()
            await sleep(delay)
            delay = min(delay * 2, PUSH_RETRY_MAX)

    @property
    def _name(self) -> str:
        return self._entry.title

    def _log_down(self, err: NodeCSError) -> None:
        if self._down_logged:
            _LOGGER.debug("Live updates from %s still down: %s", self._name, err)
            return
        _LOGGER.warning(
            "Live updates from %s are down (%s); reading the panel every second "
            "until they are back",
            self._name,
            err,
        )
        self._down_logged = True

    @callback
    def _set_connected(self, connected: bool) -> None:
        if connected == self.connected:
            return
        self.connected = connected
        for update_callback in list(self._listeners):
            update_callback()
