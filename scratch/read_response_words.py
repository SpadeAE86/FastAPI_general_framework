import json

with open("src/utils/audio_response.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Let's check the debug_json_url or raw events
# Wait, let's see what is inside the response JSON
# Is there a list of frontend_words or similar?
print(data.keys())
if "object_list" in data:
    obj = data["object_list"][0]
    print(obj.keys())
    if "detail_info" in obj:
        print("detail_info has", len(obj["detail_info"]), "items")
        for idx, item in enumerate(obj["detail_info"][:3]):
            print(f"\nSegment {idx}:")
            print(f"  caption_text: {item.get('caption_text')}")
            print(f"  segment_duration: {item.get('segment_duration')}")
            print(f"  pause: {item.get('pause')}")
            print(f"  segment_url: {item.get('segment_url')}")
