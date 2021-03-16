"""Support for DomesticHotWaterProduction."""
from homeassistant.components.climate.const import SUPPORT_TARGET_TEMPERATURE
from homeassistant.components.water_heater import (
    STATE_ECO,
    STATE_HIGH_DEMAND,
    SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE,
    WaterHeaterEntity,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, STATE_ON, TEMP_CELSIUS

from ..tahoma_entity import TahomaEntity

CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE_STATE = "core:MaximalTemperatureManualModeState"
CORE_MINIMAL_TEMPERATURE_MANUAL_MODE_STATE = "core:MinimalTemperatureManualModeState"
CORE_TARGET_TEMPERATURE_STATE = "core:TargetTemperatureState"
CORE_OPERATING_MODE_STATE = "core:OperatingModeState"

IO_DHW_MODE_STATE = "io:DHWModeState"
IO_DHW_BOOST_MODE_STATE = "io:DHWBoostModeState"
IO_MIDDLE_WATER_TEMPERATURE_STATE = "io:MiddleWaterTemperatureState"

STATE_MANUAL = "manual"
STATE_AUTO = "auto"
STATE_ABSENCE = "absence"
STATE_RELAUNCH = "relaunch"

COMMAND_SET_TARGET_TEMPERATURE = "setTargetTemperature"
COMMAND_SET_DHW_MODE = "setDHWMode"
COMMAND_SET_CURRENT_OPERATING_MODE = "setCurrentOperatingMode"
COMMAND_SET_BOOST_MODE_DURATION = "setBoostModeDuration"
COMMAND_SET_AWAY_MODE_DURATION = "setAwayModeDuration"

MODE_AUTO = "autoMode"
MODE_BOOST = "boost"
MODE_MANUAL_ECO_ACTIVE = "manualEcoActive"
MODE_MANUAL_ECO_INACTIVE = "manualEcoInactive"

TAHOMA_TO_OPERATION_MODE = {
    MODE_MANUAL_ECO_ACTIVE: STATE_ECO,
    MODE_MANUAL_ECO_INACTIVE: STATE_MANUAL,
    MODE_AUTO: STATE_AUTO,
    MODE_BOOST: STATE_HIGH_DEMAND,
}

OPERATION_MODE_TO_TAHOMA = {v: k for k, v in TAHOMA_TO_OPERATION_MODE.items()}


class DomesticHotWaterProduction(TahomaEntity, WaterHeaterEntity):
    """Representation of a DomesticHotWaterProduction Water Heater."""

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.select_state(CORE_MINIMAL_TEMPERATURE_MANUAL_MODE_STATE)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.select_state(CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE_STATE)

    @property
    def current_operation(self):
        """Return current operation ie. eco, electric, performance, ..."""
        if self.select_state(IO_DHW_BOOST_MODE_STATE) == STATE_ON:
            return STATE_HIGH_DEMAND

        return TAHOMA_TO_OPERATION_MODE[self.select_state(IO_DHW_MODE_STATE)]

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [*OPERATION_MODE_TO_TAHOMA]

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.select_state(IO_MIDDLE_WATER_TEMPERATURE_STATE)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.select_state(CORE_TARGET_TEMPERATURE_STATE)

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self.select_state(CORE_MAXIMAL_TEMPERATURE_MANUAL_MODE_STATE)

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self.select_state(CORE_MINIMAL_TEMPERATURE_MANUAL_MODE_STATE)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        await self.async_execute_command(
            COMMAND_SET_TARGET_TEMPERATURE, target_temperature
        )

    async def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        if (
            self.current_operation == STATE_HIGH_DEMAND
            and operation_mode != STATE_HIGH_DEMAND
        ):
            await self.async_execute_command(
                COMMAND_SET_CURRENT_OPERATING_MODE,
                {
                    STATE_RELAUNCH: STATE_OFF,
                    STATE_ABSENCE: STATE_OFF,
                },
            )

        if operation_mode == STATE_HIGH_DEMAND:
            await self.async_execute_command(
                COMMAND_SET_CURRENT_OPERATING_MODE,
                {
                    STATE_RELAUNCH: STATE_ON,
                    STATE_ABSENCE: STATE_OFF,
                },
            )
            await self.async_execute_command(COMMAND_SET_BOOST_MODE_DURATION, 1)
        else:
            await self.async_execute_command(
                COMMAND_SET_DHW_MODE, OPERATION_MODE_TO_TAHOMA[operation_mode]
            )

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE | SUPPORT_TARGET_TEMPERATURE

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return (
            self.select_state(CORE_OPERATING_MODE_STATE).get(STATE_ABSENCE) == STATE_ON
        )

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        await self.async_execute_command(
            COMMAND_SET_CURRENT_OPERATING_MODE,
            {
                STATE_RELAUNCH: STATE_OFF,
                STATE_ABSENCE: STATE_ON,
            },
        )

        await self.async_execute_command(COMMAND_SET_AWAY_MODE_DURATION, 2)

    async def async_turn_away_mode_off(self):
        """Turn away mode off."""
        await self.async_execute_command(
            COMMAND_SET_CURRENT_OPERATING_MODE,
            {
                STATE_RELAUNCH: STATE_OFF,
                STATE_ABSENCE: STATE_OFF,
            },
        )

        await self.async_execute_command(COMMAND_SET_AWAY_MODE_DURATION, 0)
