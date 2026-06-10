import json
import os

def main():
    body_path = "src/utils/body.json"
    audio_path = "src/utils/audio_response.json"
    backup_body_path = "scratch/body_padded.json"
    
    if not os.path.exists(body_path) or not os.path.exists(audio_path):
        print("Error: body.json or audio_response.json does not exist.")
        return
        
    with open(body_path, "r", encoding="utf-8") as f:
        body_data = json.load(f)
    with open(audio_path, "r", encoding="utf-8") as f:
        audio_data = json.load(f)
        
    crops = body_data.get("crop_config", [])
    captions = body_data.get("cap_config", {}).get("caption_list", [])
    audio_segs = audio_data["object_list"][0]["detail_info"]
    
    gpu_drop = 0.166 # 5 frames at 30fps
    
    print("Clean baseline loaded.")
    print(f"Total crops: {len(crops)}, Total captions: {len(captions)}, Total audio segments: {len(audio_segs)}")
    
    print("\n--- Applying Perfect Sync Timeline ---")
    print(f"{'Index':<5} | {'Speech':<8} | {'Pause':<6} | {'Video End':<10} | {'Extend To':<10} | {'Cap Start':<10} | {'Cap End':<10}")
    print("-" * 85)
    
    cumulative_time = 0.0
    for i in range(min(len(crops), len(audio_segs))):
        seg = audio_segs[i]
        
        # Original clean durations
        speech_dur = seg["segment_duration"]
        video_dur = seg["video_duration"]
        pause = seg["pause"]
        
        # crop end is video_dur (speech + pause)
        crop_end = round(video_dur, 3)
        # crop extend_to is video_dur + gpu_drop
        crop_extend_to = round(video_dur + gpu_drop, 3)
        
        # Caption start is cumulative time, caption end is start + speech_dur
        cap_start = round(cumulative_time, 3)
        cap_end = round(cumulative_time + speech_dur, 3)
        
        # Cumulative time advances by video_dur (speech + pause)
        cumulative_time = round(cumulative_time + video_dur, 3)
        
        # Update crop config
        crops[i]["start"] = 0.0
        crops[i]["end"] = crop_end
        crops[i]["extend_to"] = crop_extend_to
        
        # Update caption config
        if i < len(captions):
            captions[i]["start"] = cap_start
            captions[i]["end"] = cap_end
            
        print(f"{i:<5} | {speech_dur:<8.3f} | {pause:<6.3f} | {crop_end:<10.3f} | {crop_extend_to:<10.3f} | {cap_start:<10.3f} | {cap_end:<10.3f}")
        
    print(f"\nFinal expected video stream duration: {cumulative_time:.3f}s")
    print(f"Continuous voice BGM duration: {audio_data['object_list'][0]['duration']:.3f}s")
    
    # Save the updated body.json
    with open(backup_body_path, "w", encoding="utf-8") as f:
        json.dump(body_data, f, ensure_ascii=False, indent=2)
    with open(body_path, "w", encoding="utf-8") as f:
        json.dump(body_data, f, ensure_ascii=False, indent=2)
        
    print(f"\nSuccessfully updated body.json to achieve perfect sync.")

if __name__ == "__main__":
    main()
