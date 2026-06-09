import json

# Load updated body.json and audio_response.json
with open("src/utils/body.json", "r", encoding="utf-8") as f:
    body_data = json.load(f)

with open("src/utils/audio_response.json", "r", encoding="utf-8") as f:
    audio_data = json.load(f)

crops = body_data["crop_config"]
audio_segs = audio_data["object_list"][0]["detail_info"]

print("=== TIMELINE ALIGNMENT SIMULATION (CURRENT CONFIG: extend_to = segment_duration) ===")
print(f"{'Index':<5} | {'Video Start':<12} | {'Video End':<12} | {'Voice Start':<12} | {'Voice End':<12} | {'Delay (Voice - Video)':<22} | {'Text'}")
print("-" * 115)

video_time = 0.0
voice_time = 0.0

for idx in range(12):
    c = crops[idx]
    start = c.get("start", 0.0)
    end = c.get("end", 0.0)
    ext_to = c.get("extend_to", end)
    video_dur = ext_to - start  # Current video duration for this clip
    
    seg = audio_segs[idx]
    voice_dur = seg.get("segment_duration", 0.0)
    pause = seg.get("pause", 0.0)
    
    # Video timeline
    v_start = video_time
    v_end = video_time + video_dur
    video_time = v_end
    
    # Voice timeline (voiceover plays continuously with pauses)
    # The speech starts at voice_time
    vo_start = voice_time
    vo_end = voice_time + voice_dur
    # Next segment starts after speech + pause
    voice_time = vo_end + pause
    
    delay = vo_start - v_start
    print(f"{idx:<5} | {v_start:<12.3f} | {v_end:<12.3f} | {vo_start:<12.3f} | {vo_end:<12.3f} | {delay:<+22.3f} | {seg.get('caption_text')}")

print("\n" + "="*80)
print("=== TIMELINE ALIGNMENT SIMULATION (PROPOSED CONFIG: extend_to = segment_duration + pause) ===")
print("="*80)
print(f"{'Index':<5} | {'Video Start':<12} | {'Video End':<12} | {'Voice Start':<12} | {'Voice End':<12} | {'Delay (Voice - Video)':<22} | {'Text'}")
print("-" * 115)

video_time = 0.0
voice_time = 0.0

for idx in range(12):
    seg = audio_segs[idx]
    voice_dur = seg.get("segment_duration", 0.0)
    pause = seg.get("pause", 0.0)
    
    # Proposed: extend_to = voice_dur + pause
    video_dur = voice_dur + pause
    
    v_start = video_time
    v_end = video_time + video_dur
    video_time = v_end
    
    vo_start = voice_time
    vo_end = voice_time + voice_dur
    voice_time = vo_end + pause
    
    delay = vo_start - v_start
    print(f"{idx:<5} | {v_start:<12.3f} | {v_end:<12.3f} | {vo_start:<12.3f} | {vo_end:<12.3f} | {delay:<+22.3f} | {seg.get('caption_text')}")
