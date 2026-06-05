import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from utils.redis_client import RedisClientFactory
mock_redis = MagicMock()
RedisClientFactory.get_client = MagicMock(return_value=mock_redis)

from utils.general_utils import VideoInfo
from core.video_processing.normalize_video import normalize_video_filter_complex

class TestNormalizeVideoFFmpegCommand(unittest.TestCase):
    def setUp(self):
        # Create a mock VideoInfo
        self.video_info = VideoInfo(
            width=1920,
            height=1080,
            duration=15.0,
            rotation=0,
            pix_fmt="yuv420p",
            codec_name="h264"
        )
        self.mock_commands = []

    def mock_run_ffmpeg_command(self, command, video_name=""):
        self.mock_commands.append(command)

    @patch("core.video_processing.normalize_video.check_audio_stream_simple", return_value=True)
    @patch("core.video_processing.normalize_video.run_ffmpeg_command")
    @patch("core.video_processing.normalize_video.os.makedirs")
    @patch("core.video_processing.normalize_video.os.path.exists", return_value=True)
    @patch("core.video_processing.normalize_video.os.remove")
    @patch("core.video_processing.normalize_video.split_normalize")
    def test_normalize_command_variations(self, mock_split, mock_remove, mock_exists, mock_makedirs, mock_run, mock_check_audio):
        mock_run.side_effect = self.mock_run_ffmpeg_command
        mock_split.return_value = MagicMock()

        test_cases = [
            # Case 1: Mute origin, no external audio, no subtitle
            {
                "mute_origin": True,
                "audio_config": None,
                "audio_path_list": None,
                "speed": 1.0,
            },
            # Case 2: Do not mute origin, no external audio, no subtitle
            {
                "mute_origin": False,
                "audio_config": None,
                "audio_path_list": None,
                "speed": 1.0,
            },
            # Case 3: Mute origin, with multiple external audio bgms, no subtitle
            {
                "mute_origin": True,
                "audio_config": [
                    MagicMock(offset=0.0, start=0.0, end=5.0, volume=1.0, weight=1.0),
                    MagicMock(offset=2.0, start=0.0, end=5.0, volume=0.8, weight=1.0),
                ],
                "audio_path_list": ["bgm1.wav", "bgm2.wav"],
                "speed": 1.0,
            },
            # Case 4: Do not mute origin, with multiple external audio bgms, no subtitle
            {
                "mute_origin": False,
                "audio_config": [
                    MagicMock(offset=0.0, start=0.0, end=5.0, volume=1.0, weight=1.0),
                    MagicMock(offset=2.0, start=0.0, end=5.0, volume=0.8, weight=1.0),
                ],
                "audio_path_list": ["bgm1.wav", "bgm2.wav"],
                "speed": 1.0,
            },
            # Case 5: Speed up video and audio, mute_origin=False, with external audio
            {
                "mute_origin": False,
                "audio_config": [
                    MagicMock(offset=0.0, start=0.0, end=5.0, volume=1.0, weight=1.0),
                ],
                "audio_path_list": ["bgm1.wav"],
                "speed": 1.5,
            }
        ]

        for i, tc in enumerate(test_cases):
            self.mock_commands.clear()
            normalize_video_filter_complex(
                video="dummy_video.mp4",
                video_info=self.video_info,
                end_time=10.0,
                width=1920,
                height=1080,
                fps=30,
                cap_config=None,
                start_time=0.0,
                mute_origin=tc["mute_origin"],
                project_id=f"test_case_{i}",
                speed=tc["speed"],
                audio_config=tc["audio_config"],
                audio_path_list=tc["audio_path_list"],
                vindex=0,
                cap_helper=None,
            )

            self.assertEqual(len(self.mock_commands), 1)
            cmd = self.mock_commands[0]
            cmd_str = " ".join(cmd)
            
            # Print for inspection
            print(f"\n--- Test Case {i+1} Command ---")
            print(cmd_str)

            # 1. Assert no double brackets in the entire command
            self.assertNotIn("[[", cmd_str, f"Double brackets '[[' found in case {i+1}")
            self.assertNotIn("]]", cmd_str, f"Double brackets ']]' found in case {i+1}")

            # 2. Extract and check filter_complex syntax
            try:
                fc_index = cmd.index("-filter_complex")
                fc_val = cmd[fc_index + 1]
                print(f"Filter Complex: {fc_val}")
                # Ensure no empty filters (e.g. leading or trailing commas inside a filterchain)
                self.assertNotIn(",,", fc_val)
                self.assertNotIn(";;", fc_val)
                
                # Check that if trimmed_a is in the filter graph, it's defined and used correctly
                if "trimmed_a" in fc_val:
                    # It must be defined as [trimmed_a]
                    self.assertIn("[trimmed_a]", fc_val)
            except ValueError:
                self.fail("-filter_complex option not found in the command line")

            # 3. Check mapping parameters
            map_indices = [idx for idx, val in enumerate(cmd) if val == "-map"]
            self.assertEqual(len(map_indices), 2, f"Should have exactly 2 '-map' options, got {len(map_indices)}")
            
            video_map = cmd[map_indices[0] + 1]
            audio_map = cmd[map_indices[1] + 1]
            
            print(f"Video Map: {video_map} | Audio Map: {audio_map}")
            # Ensure mapped streams are properly formatted
            if video_map.startswith("["):
                self.assertTrue(video_map.endswith("]"))
                self.assertEqual(video_map.count("["), 1)
            if audio_map.startswith("["):
                self.assertTrue(audio_map.endswith("]"))
                self.assertEqual(audio_map.count("["), 1)

if __name__ == "__main__":
    unittest.main()
