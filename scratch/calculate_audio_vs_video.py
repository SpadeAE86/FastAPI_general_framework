import json

def main():
    with open("src/utils/audio_response.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    details = data["object_list"][0]["detail_info"]
    full_voice_dur = data["object_list"][0]["duration"]
    
    print("="*80)
    print(f"ANALYZING AUDIO RESPONSE VS VIDEO SEGMENTS (full_voice duration: {full_voice_dur:.3f}s)")
    print("="*80)
    
    total_audio_segment_dur = 0.0
    total_pause_dur = 0.0
    total_video_dur = 0.0
    
    print(f"{'Index':<6} | {'Text':<15} | {'Audio Seg':<10} | {'Pause':<8} | {'Audio+Pause':<12} | {'Video Dur':<10}")
    print("-" * 80)
    
    for idx, item in enumerate(details):
        seg_dur = item.get("segment_duration", 0.0)
        pause = item.get("pause", 0.0)
        video_dur = item.get("video_duration", 0.0)
        
        audio_plus_pause = seg_dur + pause
        
        total_audio_segment_dur += seg_dur
        total_pause_dur += pause
        total_video_dur += video_dur
        
        text_snippet = item.get("caption_text", "")[:10]
        print(f"{idx:02d}    | {text_snippet:<15} | {seg_dur:8.3f}s | {pause:7.3f}s | {audio_plus_pause:10.3f}s | {video_dur:8.3f}s")
        
    print("-" * 80)
    print(f"Sum of audio segments: {total_audio_segment_dur:.3f}s")
    print(f"Sum of pauses:         {total_pause_dur:.3f}s")
    print(f"Sum of (audio+pause):  {(total_audio_segment_dur + total_pause_dur):.3f}s")
    print(f"Sum of video durations: {total_video_dur:.3f}s")
    print("="*80)

if __name__ == "__main__":
    main()
