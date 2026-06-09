import json
import os

body_path = "src/utils/body.json"
audio_path = "src/utils/audio_response.json"

with open(body_path, "r", encoding="utf-8") as f:
    body_data = json.load(f)

with open(audio_path, "r", encoding="utf-8") as f:
    audio_data = json.load(f)

crops = body_data["crop_config"]
audio_segs = audio_data["object_list"][0]["detail_info"]

print(f"Number of crops in body.json: {len(crops)}")
print(f"Number of audio segments: {len(audio_segs)}")
print("-" * 125)
print(f"{'Index':<5} | {'Start':<10} | {'End':<10} | {'Extend_to':<10} | {'Extend_to - Start':<20} | {'Audio Segment Dur':<20} | {'Pause':<10} | {'Text'}")
print("-" * 125)

for idx in range(max(len(crops), len(audio_segs))):
    crop_str = ""
    start, end, ext_to, diff = 0.0, 0.0, 0.0, 0.0
    if idx < len(crops):
        c = crops[idx]
        start = c.get("start", 0.0)
        end = c.get("end", 0.0)
        ext_to = c.get("extend_to", end)
        diff = ext_to - start
        crop_info = f"{start:<10.3f} | {end:<10.3f} | {ext_to:<10.3f} | {diff:<20.3f}"
    else:
        crop_info = f"{'N/A':<10} | {'N/A':<10} | {'N/A':<10} | {'N/A':<20}"
        
    if idx < len(audio_segs):
        seg = audio_segs[idx]
        seg_dur = seg.get("segment_duration", 0.0)
        pause = seg.get("pause", 0.0)
        text = seg.get("caption_text", "")
        aud_info = f"{seg_dur:<20.3f} | {pause:<10.3f} | {text}"
    else:
        aud_info = f"{'N/A':<20} | {'N/A':<10} | {'N/A'}"
        
    print(f"{idx:<5} | {crop_info} | {aud_info}")
