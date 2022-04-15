from ovos_plugin_manager.phal import PHALPlugin
from os.path import join, dirname
from mycroft_bus_client import Message
from json_database import JsonConfigXDG


class AnalogInputDevicesPlugin(PHALPlugin):
    def __init__(self, bus=None, config=None):
        super().__init__(bus=bus, name="ovos-PHAL-plugin-analog-input-devices", config=config)
        self.settings = JsonConfigXDG(self.name, subfolder="OpenVoiceOS")
