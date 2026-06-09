import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from service.volcovoice_service import process_volcovoice_task
from models.pydantic_models.request.volcovoice_request import Volcovoice_VO

TEST_CASES = [
    "智己LS6配了11L双开门冰箱，同级领先的大容量，前后排都能拿取，冷饮随手可得！",
    "敏感肌的姐妹看过来，今天拍小青蛙就送同款小样2支，再加两片修护面膜，直接省了百来块。我跟你们说啊，这个活动就今天24点前有效，库存只剩最后87份，手慢真的无。别犹豫了，现在点下方小黄车直接拍，这波过了真的没有了。",
    "这是一句很短的话。",
]

async def run_test(text: str, case_idx: int):
    print(f"\n{'='*60}")
    print(f"Case {case_idx}: {text[:30]}{'...' if len(text) > 30 else ''}")
    print(f"{'='*60}")

    request = Volcovoice_VO(
        biz_id=0,
        user_id=0,
        txt_str=[text],
        voice_character="柔美女友",
        audio_speed_level=1.0,
        volume=80,
    )

    response = await process_volcovoice_task(request)
    obj = response.object_list[0]
    full_duration = obj.duration
    details = obj.detail_info

    print(f"\nfull_voice duration: {full_duration}s")
    print(f"Number of segments: {len(details)}")
    print()

    sum_video_duration = 0.0
    sum_segment_duration = 0.0
    for i, d in enumerate(details):
        is_last = (i == len(details) - 1)
        sum_video_duration += d.video_duration
        sum_segment_duration += d.segment_duration
        tag = " ← last" if is_last else ""
        print(f"  Segment {i:2d}: video_dur={d.video_duration:.3f}s  segment_dur={d.segment_duration:.3f}s  pause={d.pause:.3f}s  '{d.caption_text}'{tag}")

    print()
    print(f"  sum(video_duration)   = {sum_video_duration:.3f}s")
    print(f"  sum(segment_duration) = {sum_segment_duration:.3f}s")
    print(f"  full_voice duration   = {full_duration:.3f}s")

    diff = abs(sum_video_duration - full_duration)
    print()
    if diff < 0.005:
        print(f"  ✅ PASS: |sum(video_duration) - full_duration| = {diff:.4f}s  (within 5ms tolerance)")
    else:
        print(f"  ❌ FAIL: |sum(video_duration) - full_duration| = {diff:.4f}s  (exceeds 5ms tolerance)")

    return diff < 0.005

async def main():
    print("Testing video_duration field accuracy...")
    results = []
    for i, text in enumerate(TEST_CASES):
        try:
            ok = await run_test(text, i)
            results.append(ok)
        except Exception as e:
            import traceback
            traceback.print_exc()
            results.append(False)

    print(f"\n{'='*60}")
    passed = sum(results)
    total = len(results)
    print(f"SUMMARY: {passed}/{total} passed")
    if passed == total:
        print("✅ All tests passed! video_duration is correct.")
    else:
        print("❌ Some tests failed!")

if __name__ == "__main__":
    asyncio.run(main())
