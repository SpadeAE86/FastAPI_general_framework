import json

def main():
    # Read audio response
    with open("src/utils/audio_response.json", "r", encoding="utf-8") as f:
        audio_data = json.load(f)
    details = audio_data["object_list"][0]["detail_info"]

    # Read body.json
    with open("src/utils/body.json", "r", encoding="utf-8") as f:
        body_data = json.load(f)
    crops = body_data.get("crop_config", [])

    print("="*90)
    print("DETAILED GAP ANALYSIS: VIDEO CROP VS AUDIO + PAUSE FOR EACH SEGMENT")
    print("="*90)
    print(f"{'Index':<5} | {'Text':<12} | {'Audio+Pause':<12} | {'Video Crop':<11} | {'Extend To':<10} | {'Short by (Crop)':<16} | {'Short by (Extend)'}")
    print("-" * 90)

    for idx in range(min(len(details), len(crops))):
        item = details[idx]
        c = crops[idx]
        
        seg_dur = item.get("segment_duration", 0.0)
        pause = item.get("pause", 0.0)
        audio_plus_pause = seg_dur + pause
        
        start = c.get("start", 0.0)
        end = c.get("end", 0.0)
        extend_to = c.get("extend_to")
        
        crop_dur = end - start
        effective_end = extend_to if (extend_to is not None and extend_to > end) else end
        extend_dur = effective_end - start
        
        short_crop = max(0.0, audio_plus_pause - crop_dur)
        short_extend = max(0.0, audio_plus_pause - extend_dur)
        
        text_snippet = item.get("caption_text", "")[:8]
        print(f"#{idx:02d}  | {text_snippet:<12} | {audio_plus_pause:10.3f}s | {crop_dur:10.3f}s | {extend_dur:9.3f}s | {short_crop:13.3f}s | {short_extend:14.3f}s")
        
    print("="*90)

if __name__ == "__main__":
    main()
