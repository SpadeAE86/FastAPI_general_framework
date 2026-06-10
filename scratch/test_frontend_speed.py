import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from models.pydantic_models.request.frontend_timeline_request import FrontendAudioInfo
from utils.frontend_exporter import _build_voiceover

# Test default values
default_info = FrontendAudioInfo()
print("Default voice_character:", default_info.voice_character)
print("Default audio_speed_level:", default_info.audio_speed_level)

# Test _build_voiceover output with speed=1.5
info_custom = FrontendAudioInfo(voice_character="甜心小美", audio_speed_level=1.5)
voiceover_data = _build_voiceover(info_custom, "http://dummy/audio.wav")
print("\nCustom VoiceOverData output:")
print(voiceover_data)

assert default_info.voice_character == "Vivi"
assert voiceover_data["speed"] == 1.5
print("\nSUCCESS: Frontend speed and voice defaults are correct!")
