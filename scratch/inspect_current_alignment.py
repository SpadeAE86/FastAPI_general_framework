import json
import os

def main():
    utils_dir = "c:/Job/AI/mix/AIGC_video_mix_remake/src/utils"
    audio_path = os.path.join(utils_dir, "audio_response.json")
    body_path = os.path.join(utils_dir, "body.json")
    
    with open(audio_path, 'r', encoding='utf-8') as f:
        audio_data = json.load(f)
    with open(body_path, 'r', encoding='utf-8') as f:
        body_data = json.load(f)
        
    print("=== AUDIO SEGMENTS FROM audio_response.json ===")
    audio_segs = audio_data["object_list"][0]["detail_info"]
    accum_audio_time = 0.0
    for idx, seg in enumerate(audio_segs):
        dur = seg["segment_duration"]
        pause = seg["pause"]
        text = seg["caption_text"]
        v_dur = seg["video_duration"]
        print(f"[{idx}] caption: {text}")
        print(f"    segment_duration: {dur}, pause: {pause}, video_duration (expected): {v_dur}")
        print(f"    cumulative end of audio: {accum_audio_time + dur + pause:.3f}")
        accum_audio_time += dur + pause

    print("\n=== CAPTIONS FROM body.json ===")
    body_caps = body_data["cap_config"]["caption_list"]
    for idx, cap in enumerate(body_caps):
        print(f"[{idx}] cap: {cap['cap']}")
        print(f"    start: {cap['start']}, end: {cap['end']}, duration: {cap['end'] - cap['start']:.3f}")

    print("\n=== CROPS FROM body.json ===")
    body_crops = body_data["crop_config"]
    accum_crop_time = 0.0
    for idx, crop in enumerate(body_crops):
        dur = crop["end"] - crop["start"]
        extend_to = crop["extend_to"]
        speed = crop["speed"]
        print(f"[{idx}] start: {crop['start']}, end: {crop['end']}, duration: {dur:.3f}, extend_to: {extend_to}, speed: {speed}")
        print(f"    cumulative end of crops (using extend_to): {accum_crop_time + extend_to:.3f}")
        accum_crop_time += extend_to

if __name__ == '__main__':
    main()
