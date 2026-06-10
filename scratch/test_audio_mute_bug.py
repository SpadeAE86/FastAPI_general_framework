import sys
import os
from unittest.mock import MagicMock

# Mock redis modules to prevent connecting to actual Redis
mock_redis = MagicMock()
sys.modules['redis'] = mock_redis
sys.modules['redis.exceptions'] = mock_redis

# Create mock client factory
mock_client = MagicMock()
mock_client.ping.return_value = True

class MockRedisClientFactory:
    @classmethod
    def get_client(cls):
        return mock_client

sys.modules['utils.redis_client'] = MagicMock(RedisClientFactory=MockRedisClientFactory)

# Mock health_monitor module to prevent initialization errors
sys.modules['core.health_monitor'] = MagicMock()
sys.modules['core.health_monitor.service'] = MagicMock()
sys.modules['core.health_monitor.heartbeat_checker'] = MagicMock()
sys.modules['core.health_monitor.monitor'] = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.request.crop_config import CropConfig
from models.pydantic_models.request.audio_config import AudioConfig
import core.video_processing.normalize_video as nv

# Mock functions to prevent actual file and shell executions
class MockVideoInfo:
    def get_info(self):
        # width, height, duration, rot, pix_format, codec
        return 1920, 1080, 45.0, 0, "yuv420p", "h264"

def mock_check_audio_stream_simple(path):
    return True

last_command = None
def mock_run_ffmpeg_command(cmd, video_name=None):
    global last_command
    last_command = cmd
    print("\n--- Generated FFmpeg Command ---")
    print(" ".join(cmd))
    print("--------------------------------\n")

nv.check_audio_stream_simple = mock_check_audio_stream_simple
nv.run_ffmpeg_command = mock_run_ffmpeg_command

# Load the request body
import json
with open("src/utils/body.json", "r", encoding="utf-8") as f:
    body_data = json.load(f)

req = MixedVideoRequest(**body_data)

print("Running normalize_video_filter_complex for segment index 0...")
try:
    nv.normalize_video_filter_complex(
        video="dummy_video.mp4",
        video_info=MockVideoInfo(),
        end_time=req.crop_config[0].end,
        width=1080,
        height=1920,
        fps=30,
        cap_config=req.cap_config,
        start_time=req.crop_config[0].start,
        mute_origin=req.mute_config[0],
        rotation=req.crop_config[0].rotation,
        translate_x=req.crop_config[0].translate_x,
        translate_y=req.crop_config[0].translate_y,
        scale=req.crop_config[0].scale,
        mirror=req.crop_config[0].mirror,
        speed=req.crop_config[0].speed,
        extra_filter="",
        project_id="test_proj",
        processed_so_far=0.0,
        pix_fmt="yuv420p",
        cache_hit=False,
        fade_in_duration=0.0,
        fade_out_duration=0.0,
        audio_config=req.audio_config,
        audio_path_list=req.obs_audio_path_list,
        vindex=0,
        freeze_tail_duration=req.crop_config[0].extend_to - req.crop_config[0].end,
    )
    
    # Check if last_command contains amix=inputs=1
    cmd_str = " ".join(last_command)
    if "amix=inputs=1" in cmd_str:
        print("FAIL: Found 'amix=inputs=1' in ffmpeg command!")
        sys.exit(1)
    elif "anull" in cmd_str:
        print("SUCCESS: Found 'anull' in ffmpeg command to bypass amix!")
    else:
        print("WARNING: Neither amix=inputs=1 nor anull was found. Check generated command.")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
