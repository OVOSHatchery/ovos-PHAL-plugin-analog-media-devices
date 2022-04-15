import subprocess
import threading
from distutils.spawn import find_executable

from ovos_utils.configuration import read_mycroft_config
from ovos_utils.log import LOG
from ovos_utils.parse import fuzzy_match, MatchStrategy, match_one

# add any fingerprints here
# useful to define default icons and pretty names
# can also be used to force split a audio+video source into 2
# see Playstation Eye for an example where we do not want mic feedback
FINGERPRINTS = {
    "Playstation Eye": {"card_name": 'USB Camera-B4.09.24.1',
                        "card_type": "USB Audio",
                        "icon": "pseye.png",
                        "type": "audio"
                        },
    "Playstation Eye Camera": {"device_name": 'USB Camera-B4.09.24.1',
                               "icon": "pseye.png",
                               "type": "video"
                               },
    "USB Soundcard": {"card_name": 'USB PnP Sound Device',
                      "card_type": "USB Audio",
                      "icon": "soundcard.png",
                      "type": "audio"
                      }
}


class DeviceNotFound(FileNotFoundError):
    """Unknown Device"""


class AnalogInput(threading.Thread):
    def __init__(self, device=None, name=None):
        super().__init__(daemon=True)
        self.device = None
        self.name = name
        self.running = False
        self.set_device(device)

    def set_device(self, device):
        self.device = device

    def set_device_index(self, device_num):
        raise NotImplementedError

    @staticmethod
    def list_devices():
        raise NotImplementedError

    @staticmethod
    def find_device(device):
        raise NotImplementedError

    def run(self):
        self.running = True

    def stop(self):
        self.running = False

    def __str__(self):
        return self.name or self.__repr__()

    def __repr__(self):
        return f"{self.__class__.__name__}({self.device})"


class AnalogVideo(AnalogInput):
    def __init__(self, device=None, name=None, player="auto"):
        super().__init__(device, name)
        self.stream = None
        self._player = player

    def set_device(self, device):
        device = device or "video0"
        devices = self.find_device(device)
        device_name, score = devices[0]
        if score < 0.75:
            raise DeviceNotFound(f"Unknown device: {device}")
        dev = self.list_devices()[device_name][0]
        self.device = dev

    def set_device_index(self, device_num):
        self.set_device(f"video{device_num}")

    @staticmethod
    def list_devices():
        cmd = "v4l2-ctl --list-devices"
        v4l2 = subprocess.check_output(cmd.split()).decode("utf-8")
        devices = {}
        name = None
        d = []
        for line in v4l2.split("\n"):
            line = line.strip()
            if ":" in line:
                if name:
                    devices[name] = d
                name = line[:-1]
                d = []
            elif line.startswith("/dev/"):
                d.append(line.strip())
        if name:
            devices[name] = d
        return devices

    @staticmethod
    def find_device(device):
        matches = {}
        for name, devs in AnalogVideo.list_devices().items():
            score = fuzzy_match(device, name, strategy=MatchStrategy.PARTIAL_TOKEN_SORT_RATIO)
            d, s2 = match_one(f"/dev/{device}", devs)
            matches[name] = max(score, s2)
        return sorted(matches.items(), key=lambda k: k[1], reverse=True)

    @property
    def play_cmd(self):
        if self._player == "auto":
            if find_executable("mpv"):
                self._player = "mpv"
            elif find_executable("vlc"):
                self._player = "vlc"
            elif find_executable("mplayer"):
                self._player = "mplayer"

        player = find_executable(self._player) or self._player
        if self._player == "vlc" or self._player == "cvlc":
            return f'{player} v4l2://:v4l-vdev="{self.device}" --fullscreen --video-on-top'
        elif self._player == "mpv":
            return f'{player} av://v4l2:{self.device} --profile=low-latency --untimed --fs'
        elif self._player == "mplayer":
            return f'{player} tv:// -tv driver=v4l2:width=640:height=480:device={self.device} -fps 30'
        return player

    def run(self):
        self.stop()
        if not self.play_cmd:
            raise RuntimeError("Can not display video")
        LOG.debug(f"Opening UVC Video: {self.play_cmd}")
        self.running = True
        self.stream = subprocess.Popen(self.play_cmd, shell=True, stdout=subprocess.PIPE)
        self.running = False

    def stop(self):
        if self.stream:
            try:
                self.stream.terminate()
                self.stream.communicate()
            except Exception as e:
                if self.stream:
                    self.stream.kill()
            finally:
                self.stream = None
        self.running = False


class AnalogAudio(AnalogInput):
    def __init__(self, device=None, name=None):
        super().__init__(device, name)
        self.card = None
        self.stream = None
        self.audio_player = None
        self.running = False
        self.set_device(device)

    def set_device(self, device):
        if device is None:
            self.set_device_index(0, 0)
        else:
            card = self.find_device(device)[0]
            if card["score"] < 0.75:
                raise DeviceNotFound(f"Unknown device: {device}")
            self.set_device_index(card['card_num'], card['device_num'])

    def set_device_index(self, card_num, device_num):
        self.card = f"hw:{card_num},{device_num}"

    @staticmethod
    def list_devices():
        cards = []
        arecord = subprocess.check_output(["arecord", "-l"]).decode("utf-8")
        for line in arecord.split("\n"):
            line = line.strip()
            if not line.startswith("card "):
                continue
            card_num, card_name, card_type = line.split(": ")
            card_num = int(card_num.replace("card ", ""))
            card_name, device_num = card_name.split(", device ")
            device_num = int(device_num)
            cards.append((card_num, device_num, card_name, card_type))

        return cards

    @staticmethod
    def find_device(device):
        matches = []
        for card_num, device_num, card_name, card_type in AnalogAudio.list_devices():
            score = fuzzy_match(device, card_name, strategy=MatchStrategy.PARTIAL_TOKEN_SORT_RATIO)

            # TODO consider removing this, might be bad in some edge cases
            score = score * 0.9
            if "usb" in card_type.lower():
                score += 0.1
            elif "analog" in card_type.lower():
                score -= 0.1
            else:
                score += fuzzy_match(device, card_type) * 0.1

            matches.append({
                "score": score,
                "card_num": card_num,
                "device_num": device_num,
                "card_name": card_name,
                "card_type": card_type
            })
        return sorted(matches, key=lambda k: k["score"], reverse=True)

    def run(self):
        self.stop()
        self.running = True

        arecord = find_executable("arecord")
        if arecord:
            player = f"{arecord} -D {self.card} -f S16_LE"
            LOG.debug(f"Opening audio stream: {player}")
            self.stream = subprocess.Popen(player, shell=True,
                                           stdout=subprocess.PIPE)
            self.start_audio_playback()
        else:
            LOG.exception("Could not open audio input, arecord not found")
        self.running = False

    def start_audio_playback(self):
        if self.stream:
            play_cmd = find_executable("aplay")
            if not play_cmd:
                LOG.exception("Can not playback audio, aplay not found")
            else:
                self.audio_player = subprocess.Popen(play_cmd, stdin=self.stream.stdout, shell=True)

    def stop_audio_playback(self):
        if self.audio_player:
            try:
                self.audio_player.terminate()
                self.audio_player.communicate()
            except Exception as e:
                self.audio_player.kill()
            finally:
                self.audio_player = None

    def stop(self):
        self.stop_audio_playback()
        if self.stream:
            try:
                self.stream.terminate()
                self.stream.communicate()
            except Exception as e:
                if self.stream:
                    self.stream.kill()
            finally:
                self.stream = None
        self.running = False

    def __repr__(self):
        return f"{self.__class__.__name__}({self.card})"


class AnalogVideoAudio:
    def __init__(self, audio_device=None, video_device=None, name=None, video_player="auto"):
        self.video = AnalogVideo(video_device, player=video_player, name=name)
        self.audio = AnalogAudio(audio_device, name=name)
        self.name = name

    def start(self):
        self.audio.start()
        self.video.start()

    def stop(self):
        self.video.stop()
        self.audio.stop()

    def __str__(self):
        return self.name or self.__repr__()

    def __repr__(self):
        return f"{self.__class__.__name__}({self.audio.card}+{self.video.device})"


def load_device(name, data):
    audio = data.get("audio_device")
    video = data.get("video_device")
    try:
        if audio and video:
            return AnalogVideoAudio(audio, video, name=name)
        elif audio:
            return AnalogAudio(audio, name=name)
        elif video:
            return AnalogVideo(video, name=name)
    except Exception as e:
        LOG.exception(f"Failed to load device: {name}")


def load_from_config(devices=None):
    if not devices:
        try:
            config = read_mycroft_config()
            config = config.get("Audio") or {}
            for backend, data in config.get("backends", {}).items():
                if not data.get("active"):
                    continue
                if data.get("type", "") == "ovos_common_play":
                    devices = data.get("analog_inputs") or {}
                    break
        except:
            devices = {}

    if not devices:
        LOG.warning("No analog devices configured")
    for name, data in devices.items():
        device = load_device(name, data)
        if device:
            yield device


def scan_audio_devices():
    for _, _, name, cardtype in AnalogAudio.list_devices():
        for alias, data in FINGERPRINTS.items():
            if data.get("card_name", "[None]") in name and \
                    data.get("card_type", "[None]") in cardtype:
                yield AnalogAudio(name, alias)
                break
        else:
            yield AnalogAudio(name, name)


def scan_devices():
    audio = list(scan_audio_devices())

    for name in AnalogVideo.list_devices():
        for alias, data in FINGERPRINTS.items():
            if data.get("type", "") != "video":
                continue
            if data.get("device_name", "[None]") in name:
                yield AnalogVideo(name, alias)
                break
        else:
            alias = name.split(" (")[0]
            for d in audio:
                if d.name.endswith(f"[{alias}]"):
                    yield AnalogVideoAudio(d.name, name, alias)
                    audio.remove(d)
                    break
            else:
                yield AnalogVideo(name, alias)
    for d in audio:
        yield d


if __name__ == "__main__":
    print("\n## scan analog input devices")
    for dev in scan_devices():
        print(repr(dev), dev.name)

    print("\n## read from mycroft.conf")
    # "Audio": {
    #     "backends": {
    #       "local": {
    #         "type": "ovos_common_play",
    #         "youtube_backend": "youtube-dl",
    #         "active": true,
    #         "analog_inputs": {
    #           "Cassette Player": {
    #             "audio_device": "USB PnP Sound Device",
    #             "icon": "cassette.png"
    #           },
    #           "RCA": {
    #             "audio_device": "USB2.0 PC CAMERA",
    #             "video_device": "USB2.0 PC CAMERA",
    #             "icon": "rca.png"
    #           }
    #         }
    #       },
    #       "simple": {
    #         "type": "ovos_audio_simple",
    #         "active": true
    #       }
    #     },
    #     "default-backend": "local"
    #   }
    for dev in load_from_config():
        print(repr(dev), dev.name)

    # ## scan analog input devices
    # AnalogVideo(/dev/video10) bcm2835-codec-decode
    # AnalogVideo(/dev/video13) bcm2835-isp
    # AnalogVideo(/dev/video2) Playstation Eye Camera
    # AnalogVideoAudio(hw:3,0+/dev/video0) USB2.0 PC CAMERA
    # AnalogAudio(hw:1,0) USB Soundcard
    # AnalogAudio(hw:2,0) Playstation Eye
    #
    # ## read from mycroft.conf
    # AnalogAudio(hw:1,0) Cassette Player
    # AnalogVideoAudio(hw:3,0+/dev/video0) RCA
