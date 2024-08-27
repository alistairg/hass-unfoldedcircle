"""Unfolded Circle Repairs"""

from __future__ import annotations
import logging
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import RepairsFlow
from homeassistant.helpers import issue_registry
from homeassistant.core import HomeAssistant
from .helpers import validate_dock_password
from .config_flow import CannotConnect, InvalidDockPassword
from .const import DOMAIN, UNFOLDED_CIRCLE_COORDINATOR

_LOGGER = logging.getLogger(__name__)


class DockPasswordRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, hass, issue_id, data) -> None:
        super().__init__()
        self.data = data
        self.issue_id = issue_id
        self.hass = hass
        self.coordinator = self.hass.data[DOMAIN][self.data.get("config_entry_id")][
            UNFOLDED_CIRCLE_COORDINATOR
        ]
        self.config_entry = self.coordinator.config_entry
        self.dock_total = 0
        self.dock_count = 0

        for dock in self.config_entry.data["docks"]:
            if dock["password"] == "":
                self.dock_total += 1

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self.data["password"] = user_input.get("password")
                coordinator = self.hass.data[DOMAIN][self.data.get("config_entry_id")][
                    UNFOLDED_CIRCLE_COORDINATOR
                ]
                existing_entry = coordinator.config_entry
                is_valid = await validate_dock_password(coordinator.api, self.data)
                if is_valid:
                    config_data = existing_entry
                    for info in config_data.data["docks"]:
                        if info.get("id") == self.data.get("id"):
                            info["password"] = self.data["password"]
                    self.hass.config_entries.async_update_entry(
                        existing_entry, data=config_data.data
                    )

                    await self.hass.config_entries.async_reload(existing_entry.entry_id)

                    issue_registry.async_delete_issue(self.hass, DOMAIN, self.issue_id)

                    return self.async_abort(reason="reauth_successful")
                else:
                    raise InvalidDockPassword

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidDockPassword:
                errors["base"] = "invalid_dock_password"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="confirm",
            errors=errors,
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders={"name": self.data["name"]},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("dock_password"):
        return DockPasswordRepairFlow(hass, issue_id, data)