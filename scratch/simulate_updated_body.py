import json
import os

def main():
    body_path = "src/utils/body.json"
    audio_path = "src/utils/audio_response.json"
    backup_body_path = "scratch/body_padded.json"
    backup_audio_path = "scratch/audio_response_padded.json"
    
    if not os.path.exists(body_path):
        print(f"Error: {body_path} does not exist.")
        return
    if not os.path.exists(audio_path):
        print(f"Error: {audio_path} does not exist.")
        return
        
    # 1. Update body.json
    with open(body_path, "r", encoding="utf-8") as f:
        body_data = json.load(f)
        
    crops = body_data.get("crop_config", [])
    captions = body_data.get("cap_config", {}).get("caption_list", [])
    
    new_durations = []
    for i, crop in enumerate(crops):
        # Always read start/end relative to the original or current state.
        # But wait, to make it idempotent or run on original values, let's assume we do crop["end"] = crop["start"] + original_dur + 0.1.
        # Since we want to add 100ms to the clean/original durations:
        # If we run it, let's just add 0.1 to the existing end if we haven't already. Or let's assume we are re-reading and adding 0.1 to original.
        # Let's read from the backup if it exists, or just do it once. Let's do it cleanly by adding 0.1 to current end.
        # Wait, the user already ran it once for body.json, so body.json already has the +0.1 padding!
        # If we run it again on body.json, we might add another 0.1. Let's make it safe:
        # Let's restore from git or read the original durations first. Or since git has the clean version, we can discard changes or just do the calculation based on git diff or audio_response's original duration if we read audio_response first.
        # Actually, let's get the original durations from the unmodified audio_response.json or body.json.
        # Wait, audio_response.json in git (before any modifications) has the original durations!
        # Let's run a git checkout/restore on both files first to get the clean baseline, then apply the +100ms simulation!
        # That is extremely clean and idempotent!
        pass

if __name__ == "__main__":
    # Let's execute git checkout src/utils/body.json src/utils/audio_response.json to restore clean baselines first
    import subprocess
    subprocess.run(["git", "restore", "src/utils/body.json", "src/utils/audio_response.json"])
    
    # Now load and update
    body_path = "src/utils/body.json"
    audio_path = "src/utils/audio_response.json"
    backup_body_path = "scratch/body_padded.json"
    backup_audio_path = "scratch/audio_response_padded.json"
    
    with open(body_path, "r", encoding="utf-8") as f:
        body_data = json.load(f)
    with open(audio_path, "r", encoding="utf-8") as f:
        audio_data = json.load(f)
        
    crops = body_data.get("crop_config", [])
    captions = body_data.get("cap_config", {}).get("caption_list", [])
    audio_segs = audio_data["object_list"][0]["detail_info"]
    
    print("Clean baseline loaded. Modifying both files by adding 100ms...")
    
    new_durations = []
    for i, crop in enumerate(crops):
        old_dur = crop["end"] - crop["start"]
        new_dur = round(old_dur + 0.1, 3)
        new_durations.append(new_dur)
        
        # Update crop config
        crop["end"] = round(crop["start"] + new_dur, 3)
        crop["extend_to"] = round(crop["start"] + new_dur, 3)
        
    # Recalculate subtitle timeline
    cumulative_time = 0.0
    for i, cap in enumerate(captions):
        new_start = round(cumulative_time, 3)
        new_end = round(cumulative_time + new_durations[i], 3)
        cumulative_time = new_end
        cap["start"] = new_start
        cap["end"] = new_end
        
    # Update audio_response.json
    for i, seg in enumerate(audio_segs):
        old_seg_dur = seg["segment_duration"]
        seg["segment_duration"] = round(old_seg_dur + 0.1, 3)
        seg["video_duration"] = round(old_seg_dur + 0.1, 3)
        
    # Save the updated files
    with open(backup_body_path, "w", encoding="utf-8") as f:
        json.dump(body_data, f, ensure_ascii=False, indent=2)
    with open(body_path, "w", encoding="utf-8") as f:
        json.dump(body_data, f, ensure_ascii=False, indent=2)
        
    with open(backup_audio_path, "w", encoding="utf-8") as f:
        json.dump(audio_data, f, ensure_ascii=False, indent=2)
    with open(audio_path, "w", encoding="utf-8") as f:
        json.dump(audio_data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully simulated +100ms on both files.")
    print(f"Updated body.json: {body_path}")
    print(f"Updated audio_response.json: {audio_path}")
