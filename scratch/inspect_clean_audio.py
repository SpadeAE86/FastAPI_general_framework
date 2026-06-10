import json

def main():
    with open("src/utils/audio_response.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    for i, d in enumerate(data['object_list'][0]['detail_info']):
        print(f"Seg {i:2d}: seg_dur={d.get('segment_duration')} video_dur={d.get('video_duration')} pause={d.get('pause')} text=\"{d.get('caption_text')}\"")
    print('Reported full duration:', data['object_list'][0]['duration'])

if __name__ == "__main__":
    main()
