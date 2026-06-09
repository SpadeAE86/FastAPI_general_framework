import sys
import os
import asyncio
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from service.volcovoice_service import process_volcovoice_task
from models.pydantic_models.request.volcovoice_request import Volcovoice_VO

async def main():
    print("Starting volcovoice task for user sentence...")
    
    text = "智己LS6配了11L双开门冰箱，同级领先的大容量，前后排都能拿取，冷饮随手可得！"
    request = Volcovoice_VO(
        biz_id=12345,
        user_id=100,
        txt_str=[text],
        voice_character="柔美女友",
        audio_speed_level=1.0,
        volume=80,
    )
    
    try:
        response = await process_volcovoice_task(request)
        print("\n=== RESPONSE ===")
        print(f"biz_id: {response.biz_id}")
        print(f"volume: {response.volume}")
        print(f"speech_rate: {response.speech_rate}")
        print(f"voice_character: {response.voice_character}")
        
        obj = response.object_list[0]
        print(f"\nFull voice URL: {obj.full_voice}")
        print(f"Full duration: {obj.duration}")
        
        print("\nSegments detail_info:")
        sum_segment_durations = 0.0
        for idx, detail in enumerate(obj.detail_info):
            sum_segment_durations += detail.segment_duration
            print(f"Segment {idx}:")
            print(f"  - text: '{detail.caption_text}'")
            print(f"  - segment_duration: {detail.segment_duration}s")
            print(f"  - pause: {detail.pause}s")
            
        print("\n=== MATHEMATICAL ANALYSIS ===")
        print(f"Sum of segment_duration: {sum_segment_durations}s")
        print(f"Full duration: {obj.duration}s")
        print(f"Raw Difference (Sum - Full): {sum_segment_durations - obj.duration:.3f}s")
        
        # Read the debug json to inspect start_ms and end_ms
        debug_json_url = response.debug_json_url
        print(f"Debug JSON URL: {debug_json_url}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
