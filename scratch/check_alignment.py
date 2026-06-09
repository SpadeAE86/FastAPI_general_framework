import json

# Subtitle configuration from body.json
body_caps = [
    {"start": 0.0, "end": 2.6599999, "text": "我是朝九晚五摸了两年鱼的策划岗", "crop_dur": 2.66},
    {"start": 2.6599999, "end": 5.2799999, "text": "之前总觉得每天混日子也还行", "crop_dur": 2.62},
    {"start": 5.2799999, "end": 7.8899999, "text": "直到上个月涨薪没轮到我才慌了", "crop_dur": 2.61},
    {"start": 7.8899999, "end": 14.0899999, "text": "一开始刷到AUTO_TEST_202606010548的时候我还半信半疑", "crop_dur": 6.20},
    {"start": 14.0899999, "end": 16.6799999, "text": "怕又是那种空喊口号没用的东西", "crop_dur": 2.59},
    {"start": 16.6799999, "end": 19.1699999, "text": "抱着试试的心态跟着走了半个月", "crop_dur": 2.49},
    {"start": 19.1699999, "end": 22.6299999, "text": "我现在每天下班能沉下心啃3小时专业书", "crop_dur": 3.46},
    {"start": 22.6299999, "end": 25.3499999, "text": "上周做的方案还被总监点名夸了", "crop_dur": 2.72},
    {"start": 25.3499999, "end": 27.4899999, "text": "真的不是那种割韭菜的东西", "crop_dur": 2.14},
    {"start": 27.4899999, "end": 29.8499999, "text": "我自己用下来实打实有变化", "crop_dur": 2.36},
    {"start": 29.8499999, "end": 32.5899999, "text": "你们要是也想摆脱浑浑噩噩的状态", "crop_dur": 2.74},
    {"start": 32.5899999, "end": 33.8799999, "text": "真的可以试试", "crop_dur": 1.29}
]

# Audio segments from the TTS response
audio_segs = [
    {"dur": 1.91, "pause": 0.57, "text": "我就是普通的上班族"},
    {"dur": 3.01, "pause": 0.59, "text": "之前总觉得每天浑浑噩噩没方向"},
    {"dur": 7.34, "pause": 0.206, "text": "刷到AUTO_TEST_二零二六零六零一零五四八的时候还犹豫了好久"},
    {"dur": 1.63, "pause": 0.79, "text": "怕都是没用的空话"},
    {"dur": 2.84, "pause": 0.5, "text": "抱着试试的心态跟着走了两周"},
    {"dur": 1.35, "pause": 0.7, "text": "真的不一样了"},
    {"dur": 3.15, "pause": 0.576, "text": "之前每天下班就瘫着刷手机"},
    {"dur": 3.03, "pause": 0.69, "text": "现在每天能留出一个小时学新东西"},
    {"dur": 3.75, "pause": 0.71, "text": "上周还拿下了之前想都不敢想的项目奖"},
    {"dur": 1.88, "pause": 0.69, "text": "我自己用下来真的不错"},
    {"dur": 2.08, "pause": 0.54, "text": "要是你也总觉得日子没奔头"},
    {"dur": 1.58, "pause": 0.0, "text": "真的可以试试看"}
]

print("=== COMPARISON OF SUBTITLES (body.json) vs AUDIO SEGMENTS (TTS Response) ===")
print(f"{'Index':<5} | {'Subtitle (body.json)':<45} | {'Audio Segment (TTS)':<45}")
print("-" * 105)
for i in range(12):
    sub = body_caps[i]["text"]
    aud = audio_segs[i]["text"]
    print(f"{i:<5} | {sub[:20]:<45} | {aud[:20]:<45}")

print("\n=== TIMELINE COMPARISON ===")
sub_time = 0.0
aud_time = 0.0
print(f"{'Index':<5} | {'Video Segment (start - end)':<30} | {'Audio Segment (start - end)':<30}")
print("-" * 75)
for i in range(12):
    sub_dur = body_caps[i]["crop_dur"]
    aud_dur = audio_segs[i]["dur"] + audio_segs[i]["pause"]
    
    sub_start = sub_time
    sub_end = sub_time + sub_dur
    sub_time = sub_end
    
    aud_start = aud_time
    aud_end = aud_time + aud_dur
    aud_time = aud_end
    
    print(f"{i:<5} | {sub_start:5.2f}s - {sub_end:5.2f}s (dur={sub_dur:5.2f}s) | {aud_start:5.2f}s - {aud_end:5.2f}s (dur={aud_dur:5.2f}s)")

print(f"\nTotal planned Video duration: {sub_time:.2f}s")
print(f"Total Audio duration: {aud_time:.2f}s")
