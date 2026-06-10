import json
import os

def main():
    body_path = "src/utils/body.json"
    audio_path = "src/utils/audio_response.json"
    backup_body_path = "scratch/body_padded.json"
    backup_audio_path = "scratch/audio_response_padded.json"
    
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
    
    gpu_drop = 0.166 # 5 frames at 30fps = 166.6ms
    
    print("Clean baseline loaded.")
    print(f"Total crops: {len(crops)}, Total audio segments: {len(audio_segs)}")
    
    # Calculate new timelines
    print("\n--- Applying GPU Drop + Pause Compensated Timeline ---")
    print(f"{'Index':<5} | {'Seg Dur':<8} | {'Pause':<6} | {'Crop Start':<10} | {'Crop End':<10} | {'Extend To':<10} | {'Cap Start':<10} | {'Cap End':<10}")
    print("-" * 95)
    
    cumulative_time = 0.0
    for i in range(max(len(crops), len(audio_segs))):
        seg = audio_segs[i]
        seg_dur = seg["segment_duration"]
        pause = seg["pause"]
        
        # crop start is always 0.0 for source
        crop_start = 0.0
        # end is the segment_duration (speech)
        crop_end = round(seg_dur, 3)
        # extend_to is segment_duration + pause + gpu_drop
        crop_extend_to = round(seg_dur + pause + gpu_drop, 3)
        
        # Caption starts at current cumulative timeline and ends after speech
        cap_start = round(cumulative_time, 3)
        cap_end = round(cumulative_time + seg_dur, 3)
        
        # Cumulative timeline advances by speech + pause
        cumulative_time = round(cumulative_time + seg_dur + pause, 3)
        
        # Update body JSON crop
        if i < len(crops):
            crops[i]["start"] = crop_start
            crops[i]["end"] = crop_end
            crops[i]["extend_to"] = crop_extend_to
            
        # Update body JSON caption
        if i < len(captions):
            captions[i]["start"] = cap_start
            captions[i]["end"] = cap_end
            
        print(f"{i:<5} | {seg_dur:<8.3f} | {pause:<6.3f} | {crop_start:<10.3f} | {crop_end:<10.3f} | {crop_extend_to:<10.3f} | {cap_start:<10.3f} | {cap_end:<10.3f}")
        
    print(f"\nFinal expected video stream duration: {cumulative_time:.3f}s")
    print(f"Continuous voice BGM duration: {audio_data['object_list'][0]['duration']:.3f}s")
    
    # Save the updated files
    with open(backup_body_path, "w", encoding="utf-8") as f:
        json.dump(body_data, f, ensure_ascii=False, indent=2)
    with open(body_path, "w", encoding="utf-8") as f:
        json.dump(body_data, f, ensure_ascii=False, indent=2)
        
    print(f"\nSaved updated body.json and backups successfully.")

if __name__ == "__main__":
    main()
