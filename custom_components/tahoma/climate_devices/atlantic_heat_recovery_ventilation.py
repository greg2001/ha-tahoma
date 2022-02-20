"""Support for AtlanticHeatRecoveryVentilation."""
import logging
from typing import List, Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    FAN_AUTO,
    HVAC_MODE_FAN_ONLY,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
)
from homeassistant.const import EVENT_HOMEASSISTANT_START, STATE_UNKNOWN, TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change

from ..coordinator import OverkizDataUpdateCoordinator
from ..entity import OverkizEntity

FAN_BOOST = "home_boost"
FAN_KITCHEN = "kitchen_boost"
FAN_AWAY = "away"
FAN_BYPASS = "bypass_boost"

PRESET_AUTO = "auto"
PRESET_PROG = "prog"
PRESET_MANUAL = "manual"

COMMAND_SET_AIR_DEMAND_MODE = "setAirDemandMode"
COMMAND_SET_VENTILATION_CONFIGURATION_MODE = "setVentilationConfigurationMode"
COMMAND_SET_VENTILATION_MODE = "setVentilationMode"
COMMAND_REFRESH_VENTILATION_STATE = "refreshVentilationState"
COMMAND_REFRESH_VENTILATION_CONFIGURATION_MODE = "refreshVentilationConfigurationMode"

IO_AIR_DEMAND_MODE_STATE = "io:AirDemandModeState"
IO_VENTILATION_MODE_STATE = "io:VentilationModeState"
IO_VENTILATION_CONFIGURATION_MODE_STATE = "io:VentilationConfigurationModeState"

TAHOMA_TO_FAN_MODES = {
    "auto": FAN_AUTO,
    "away": FAN_BOOST,
    "boost": FAN_KITCHEN,
    "high": FAN_AWAY,
    None: FAN_BYPASS,
}

FAN_MODES_TO_TAHOMA = {v: k for k, v in TAHOMA_TO_FAN_MODES.items()}

PRESET_MODES = [PRESET_AUTO, PRESET_PROG, PRESET_MANUAL]

_LOGGER = logging.getLogger(__name__)


class AtlanticHeatRecoveryVentilation(OverkizEntity, ClimateEntity):
    """Representation of a AtlanticHeatRecoveryVentilation device."""

    def __init__(self, device_url: str, coordinator: OverkizDataUpdateCoordinator):
        """Init method."""
        super().__init__(device_url, coordinator)

        self._temp_sensor_entity_id = None
        self._current_temperature = None

    async def async_added_to_hass(self):
        """Register temperature sensor after added to hass."""
        await super().async_added_to_hass()

        base_url = self.get_base_device_url()
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        self._temp_sensor_entity_id = next(
            (
                entity_id
                for entity_id, entry in entity_registry.entities.items()
                if entry.unique_id == f"{base_url}#4"
            ),
            None,
        )

        if self._temp_sensor_entity_id:
            async_track_state_change(
                self.hass, self._temp_sensor_entity_id, self._async_temp_sensor_changed
            )

        else:
            _LOGGER.warning(
                "Temperature sensor could not be found for entity %s", self.name
            )

        @callback
        def _async_startup(event):
            """Init on startup."""
            if self._temp_sensor_entity_id:
                temp_sensor_state = self.hass.states.get(self._temp_sensor_entity_id)
                if temp_sensor_state and temp_sensor_state.state != STATE_UNKNOWN:
                    self.update_temp(temp_sensor_state)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        self.schedule_update_ha_state(True)

    async def _async_temp_sensor_changed(self, entity_id, old_state, new_state) -> None:
        """Handle temperature changes."""
        if new_state is None or old_state == new_state:
            return

        self.update_temp(new_state)
        self.schedule_update_ha_state()

    @callback
    def update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        if state is None or state.state == STATE_UNKNOWN:
            return

        try:
            self._current_temperature = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from sensor: %s", ex)

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self._current_temperature

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_PRESET_MODE | SUPPORT_FAN_MODE

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation ie. heat, cool mode."""
        return HVAC_MODE_FAN_ONLY

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_FAN_ONLY]

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Not implemented since there is only one hvac_mode."""

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., auto, smart, interval, favorite."""
        state_ventilation_configuration = self.executor.select_state(
            IO_VENTILATION_CONFIGURATION_MODE_STATE
        )
        state_ventilation_mode = self.executor.select_state(IO_VENTILATION_MODE_STATE)
        state_prog = state_ventilation_mode.get("prog")

        if state_prog == "on":
            return PRESET_PROG

        if state_ventilation_configuration == "comfort":
            return PRESET_AUTO

        if state_ventilation_configuration == "standard":
            return PRESET_MANUAL

        return None

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return PRESET_MODES

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == PRESET_AUTO:
            await self.executor.async_execute_command(
                COMMAND_SET_VENTILATION_CONFIGURATION_MODE, "comfort"
            )
            await self._set_ventilation_mode(prog="off")

        if preset_mode == PRESET_PROG:
            await self.executor.async_execute_command(
                COMMAND_SET_VENTILATION_CONFIGURATION_MODE, "standard"
            )
            await self._set_ventilation_mode(prog="on")

        if preset_mode == PRESET_MANUAL:
            await self.executor.async_execute_command(
                COMMAND_SET_VENTILATION_CONFIGURATION_MODE, "standard"
            )
            await self._set_ventilation_mode(prog="off")

        await self.executor.async_execute_command(
            COMMAND_REFRESH_VENTILATION_STATE,
        )
        await self.executor.async_execute_command(
            COMMAND_REFRESH_VENTILATION_CONFIGURATION_MODE,
        )

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan setting."""
        ventilation_mode_state = self.executor.select_state(IO_VENTILATION_MODE_STATE)
        cooling = ventilation_mode_state.get("cooling")

        if cooling == "on":
            return FAN_BYPASS
        else:
            return TAHOMA_TO_FAN_MODES[
                self.executor.select_state(IO_AIR_DEMAND_MODE_STATE)
            ]

    @property
    def fan_modes(self) -> Optional[List[str]]:
        """Return the list of available fan modes."""
        return [*FAN_MODES_TO_TAHOMA]

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode == FAN_BYPASS:
            await self.executor.async_execute_command(
                COMMAND_SET_AIR_DEMAND_MODE, "auto"
            )
        else:
            await self.executor.async_execute_command(
                COMMAND_SET_AIR_DEMAND_MODE, FAN_MODES_TO_TAHOMA[fan_mode]
            )

        await self.executor.async_execute_command(
            COMMAND_REFRESH_VENTILATION_STATE,
        )
        await self.executor.async_execute_command(
            COMMAND_REFRESH_VENTILATION_CONFIGURATION_MODE,
        )

    async def _set_ventilation_mode(
        self,
        cooling=None,
        prog=None,
    ):
        """Execute ventilation mode command with all parameters."""
        ventilation_mode_state = self.executor.select_state(IO_VENTILATION_MODE_STATE)

        if cooling:
            ventilation_mode_state["cooling"] = cooling

        if prog:
            ventilation_mode_state["prog"] = prog

        await self.executor.async_execute_command(
            COMMAND_SET_VENTILATION_MODE, ventilation_mode_state
        )
