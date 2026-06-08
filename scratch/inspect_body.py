import json

with open("src/utils/body.json", "r", encoding="utf-8") as f:
    data = json.load(f)

crop_config = data["crop_config"]
len_list = []
timeline = []
current_time = 0.0

for idx, c in enumerate(crop_config):
    start = c.get("start", 0.0)
    end = c.get("end", 0.0)
    extend_to = c.get("extend_to")
    effective_end = extend_to if (extend_to is not None and extend_to > end) else end
    duration = max(effective_end - start, 0.0)
    len_list.append(duration)
    current_time += duration
    timeline.append(current_time)
    print(f"Clip {idx:2d}: duration={duration:5.2f}s, start={start:5.2f}s, end={end:5.2f}s, extend_to={extend_to}, cumulative={current_time:6.2f}s, path={data['obs_video_path_list'][idx]}")

print("\nTotal Video Duration:", sum(len_list))
