import sys
import os

# Add src directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from core.video_processing.timeline_converter.timeline_converter import TimelineConverter

def test_map_offset_range():
    print("Running test_map_offset_range...")

    # Case 1: Normal case (audio starts within segment)
    converter = TimelineConverter(processed_so_far=32.0, clip_duration=2.23)
    res = converter.map_offset_range(global_offset=33.63, src_start=0.0, src_end=35.5)
    print(f"Case 1: Expected (1.63, 0.0, 35.5), got {res}")
    assert res is not None
    assert abs(res[0] - 1.63) < 1e-6
    assert abs(res[1] - 0.0) < 1e-6
    assert abs(res[2] - 35.5) < 1e-6

    # Case 2: Overlap case (audio starts before segment, ends within segment - global end time)
    converter = TimelineConverter(processed_so_far=34.23, clip_duration=1.73)
    res = converter.map_offset_range(global_offset=33.63, src_start=0.0, src_end=35.5)
    print(f"Case 2: Expected (0.0, 0.6, 35.5), got {res}")
    assert res is not None
    assert abs(res[0] - 0.0) < 1e-6
    assert abs(res[1] - 0.6) < 1e-6
    assert abs(res[2] - 35.5) < 1e-6

    # Case 3: Finished case (audio ends before segment starts)
    converter = TimelineConverter(processed_so_far=35.96, clip_duration=2.63)
    res = converter.map_offset_range(global_offset=33.63, src_start=0.0, src_end=35.5)
    print(f"Case 3: Expected None, got {res}")
    assert res is None

    # Case 4: Overlap case (global end time)
    converter = TimelineConverter(processed_so_far=10.0, clip_duration=10.0)
    res = converter.map_offset_range(global_offset=5.0, src_start=0.0, src_end=13.0)
    print(f"Case 4: Expected (0.0, 5.0, 13.0), got {res}")
    assert res is not None
    assert abs(res[0] - 0.0) < 1e-6
    assert abs(res[1] - 5.0) < 1e-6
    assert abs(res[2] - 13.0) < 1e-6

    # Case 5: Finished case (global end time)
    converter = TimelineConverter(processed_so_far=15.0, clip_duration=10.0)
    res = converter.map_offset_range(global_offset=5.0, src_start=0.0, src_end=13.0)
    print(f"Case 5: Expected None, got {res}")
    assert res is None

    # Case 6: Infinite end time (src_end = -1)
    converter = TimelineConverter(processed_so_far=10.0, clip_duration=10.0)
    res = converter.map_offset_range(global_offset=5.0, src_start=0.0, src_end=-1.0)
    print(f"Case 6: Expected (0.0, 5.0, -1.0), got {res}")
    assert res is not None
    assert abs(res[0] - 0.0) < 1e-6
    assert abs(res[1] - 5.0) < 1e-6
    assert abs(res[2] - -1.0) < 1e-6

    print("All tests passed successfully!")

if __name__ == "__main__":
    test_map_offset_range()
