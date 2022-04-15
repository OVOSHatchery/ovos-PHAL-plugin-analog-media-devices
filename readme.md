# ovos-PHAL-plugin - Analog Input Devices

WIP

```python
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
```