import logging
from urllib.parse import urlparse
import ipaddress
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (CONF_HOST, CONF_NAME, CONF_PORT,
                                 CONF_SCAN_INTERVAL, CONF_TYPE)
from homeassistant.core import HomeAssistant, callback
_LOGGER = logging.getLogger(__name__)

from .const import (
	DEFAULT_NAME,
	DEFAULT_PORT,
	DEFAULT_SCAN_INTERVAL,
    DEFAULT_TYPE,
	DOMAIN,
    TYPE_3080,
    TYPE_3080T,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_TYPE, default=DEFAULT_TYPE):vol.In([TYPE_3080T, TYPE_3080]),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
    }
)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version == (4 or 6):
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))


@callback
def iammeter_modbus_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return set(
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    )


class IammeterModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Iammeter Modbus configflow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if host exists in configuration."""
        if host in iammeter_modbus_entries(self.hass):
            return True
        return False

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Heos device."""
        friendly_name = discovery_info.upnp[ssdp.ATTR_UPNP_FRIENDLY_NAME]
        host = urlparse(discovery_info.ssdp_location).hostname
        dev_sn = friendly_name[-8:]
        self.host = host
        self.discovered_conf = {
            CONF_NAME: friendly_name + "_MB",
            CONF_HOST: host,
        }
        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = self.discovered_conf
        if self._host_in_configuration_exists(friendly_name + "_MB"):
            return self.async_abort(reason="already_configured")

        # unique_id should be serial for services purpose
        await self.async_set_unique_id(dev_sn, raise_on_progress=False)

        # Check if already configured
        self._abort_if_unique_id_configured()
        return await self.async_step_user()


    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            if self._host_in_configuration_exists(host):
                errors[CONF_HOST] = "already_configured"
            elif not host_valid(user_input[CONF_HOST]):
                errors[CONF_HOST] = "invalid host IP"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
        elif hasattr(self, 'discovered_conf'):
                user_input = {}
                user_input[CONF_NAME] = self.discovered_conf[CONF_NAME]
                user_input[CONF_HOST] = self.discovered_conf[CONF_HOST]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)): str,
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
                    vol.Required(CONF_TYPE, default=DEFAULT_TYPE):vol.In([TYPE_3080T, TYPE_3080]),
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
                }
            ),
            errors=errors
        )