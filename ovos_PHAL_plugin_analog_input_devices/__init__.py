from mycroft_bus_client import Message
from os.path import join, dirname
from ovos_PHAL_plugin_analog_input_devices.analog import get_devices, get_device_json

from ovos_plugin_manager.phal import PHALPlugin


class AnalogInputDevicesPlugin(PHALPlugin):
    def __init__(self, bus=None, config=None):
        super().__init__(bus=bus, name="ovos-PHAL-plugin-analog-input-devices", config=config)
        self.video_player = None
        self.audio_player = None
        self.paused = False
        self.audio_device = None
        self.video_device = None

        self.bus.on("ovos.common_play.analog.get", self.handle_device_request)
        self.bus.on("ovos.common_play.analog.play", self.handle_play)
        self.bus.on("ovos.common_play.analog.pause", self.handle_pause)
        self.bus.on("ovos.common_play.analog.resume", self.handle_resume)
        self.bus.on("ovos.common_play.analog.stop", self.handle_stop)
        self.bus.on("mycroft.stop", self.handle_stop)

    @property
    def devices(self):
        return get_device_json()

    def handle_device_request(self, message):
        self.bus.emit(message.response(data=self.devices))

    def handle_play(self, message):
        self.stop()
        device_name = message.data["uri"].split("analog://")[-1]
        data = self.devices[device_name]

        self.audio_device = data.get("audio")
        self.video_device = data.get("video")
        if self.video_device:
            self.video_player = AnalogVideo(self.video_device,
                                            player=self.settings.get("video_player", "auto"))

        if self.audio_device:
            self.audio_player = AnalogAudio(self.audio_device)

        if self.video_player:
            self.video_player.start()

        if self.audio_player:
            self.audio_player.start()

    def handle_pause(self, message):
        if self.audio_player:
            self.paused = True
            self.audio_player.stop()
            self.audio_player = None

    def handle_resume(self, message):
        if self.paused and self.audio_device:
            self.audio_player = AnalogAudio(self.audio_device)
            self.audio_player.start()
            self.paused = False

    def handle_stop(self, message):
        self.stop()

    def stop(self):
        if self.video_player:
            self.video_player.stop()
        if self.audio_player:
            self.audio_player.stop()
        self.video_player = None
        self.audio_player = None
        self.audio_device = None
        self.video_device = None
        self.paused = False

    def shutdown(self):
        self.stop()
        self.bus.remove("ovos.common_play.analog.get", self.handle_device_request)
        self.bus.remove("ovos.common_play.analog.play", self.handle_play)
        self.bus.remove("ovos.common_play.analog.pause", self.handle_pause)
        self.bus.remove("ovos.common_play.analog.resume", self.handle_resume)
        self.bus.remove("ovos.common_play.analog.stop", self.handle_stop)
        self.bus.remove("mycroft.stop", self.handle_stop)
        super().shutdown()
