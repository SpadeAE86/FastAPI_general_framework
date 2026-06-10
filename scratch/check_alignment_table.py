import json
import os
import sys

def main():
    # Set console output to utf-8 to avoid encoding issues in Windows terminal
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    utils_dir = "c:/Job/AI/mix/AIGC_video_mix_remake/src/utils"
    audio_path = os.path.join(utils_dir, "audio_response.json")
    body_path = os.path.join(utils_dir, "body.json")
    
    with open(audio_path, 'r', encoding='utf-8') as f:
        audio_data = json.load(f)
    with open(body_path, 'r', encoding='utf-8') as f:
        body_data = json.load(f)
        
    audio_segs = audio_data["object_list"][0]["detail_info"]
    body_caps = body_data["cap_config"]["caption_list"]
    crops = body_data["crop_config"]
    
    print(f"{'Idx':<3} | {'Caption Text':<20} | {'Aud Dur':<7} | {'Aud Pause':<9} | {'Aud CumStart':<12} | {'Cap Start':<9} | {'Cap End':<8} | {'Cap Dur':<7} | {'Crop End':<8} | {'Start Diff':<10} | {'Dur Diff':<8}")
    print("-" * 120)
    
    aud_cum_start = 0.0
    for idx in range(max(len(audio_segs), len(body_caps))):
        text = ""
        aud_dur = 0.0
        pause = 0.0
        cap_start = 0.0
        cap_end = 0.0
        crop_end = 0.0
        
        if idx < len(audio_segs):
            seg = audio_segs[idx]
            text = seg["caption_text"]
            aud_dur = seg["segment_duration"]
            pause = seg["pause"]
            
        if idx < len(body_caps):
            cap = body_caps[idx]
            cap_start = cap["start"]
            cap_end = cap["end"]
            
        if idx < len(crops):
            crop_end = crops[idx]["end"]
            
        cap_dur = cap_end - cap_start
        start_diff = cap_start - aud_cum_start
        dur_diff = cap_dur - aud_dur
        
        print(f"{idx:<3} | {text[:20]:<20} | {aud_dur:<7.3f} | {pause:<9.3f} | {aud_cum_start:<12.3f} | {cap_start:<9.3f} | {cap_end:<8.3f} | {cap_dur:<7.3f} | {crop_end:<8.3f} | {start_diff:<+10.3f} | {dur_diff:<+8.3f}")
        
        # Advance cumulative audio start
        # Wait, does Volcano TTS continuous voice start for segment i+1 match aud_cum_start + aud_dur?
        # Let's check. In volcovoice_service, Segment 12 starts at 27.898s, which is sum of segment_duration of segments 0 to 11.
        # So yes, the audio cumulative start is exactly the sum of segment_durations of previous segments!
        aud_cum_start += aud_dur

if __name__ == '__main__':
    main()
