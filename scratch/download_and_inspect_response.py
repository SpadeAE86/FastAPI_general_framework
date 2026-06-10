import asyncio
import os
import sys
import json
import urllib.request

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

async def main():
    url = "https://freeuuu.obs.cn-east-3.myhuaweicloud.com/aigc/aigc_test/volcovoice_1781058617354/volcovoice_volcovoice_1781058617354_response.json"
    print(f"Downloading response json from {url}...")
    
    response = urllib.request.urlopen(url)
    data = json.loads(response.read().decode('utf-8'))
    
    print("\n=== RESPONSE JSON TOP-LEVEL METADATA ===")
    print(f"Code: {data.get('code')}")
    print(f"Message: {data.get('message')}")
    
    # Detail Info
    print("\n=== DETAIL INFO SEGMENTS ===")
    detail_info = data["object_list"][0]["detail_info"]
    accum_dur = 0.0
    for idx, seg in enumerate(detail_info):
        print(f"[{idx}] text: {seg['caption_text']}")
        print(f"    segment_duration: {seg['segment_duration']}, pause: {seg['pause']}")
        print(f"    computed interval: {accum_dur:.3f} to {accum_dur + seg['segment_duration']:.3f} (plus pause to {accum_dur + seg['segment_duration'] + seg['pause']:.3f})")
        accum_dur += seg['segment_duration'] + seg['pause']

    # If raw response JSON contains more debugging info (e.g. from volcovoice_service debug_obj):
    # Note: the URL we downloaded is volcovoice_volcovoice_1781058617354_response.json, let's see if it has frontend_words
    if "frontend_words" in data:
        print("\n=== FRONTEND WORDS ===")
        for w in data["frontend_words"][:10]:
            print(w)
        print("...")
        for w in data["frontend_words"][-10:]:
            print(w)

if __name__ == "__main__":
    asyncio.run(main())
