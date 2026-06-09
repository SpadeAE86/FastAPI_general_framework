import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.obs_utils import obs_client, BUCKET_NAME

def main():
    path = "aigc/aigc_test/volcovoice_1780986195916/volcovoice_volcovoice_1780986195916_response.json"
    local_path = "./scratch/volcovoice_1780986195916_response.json"
    print(f"Downloading directly from OBS: {path} to {local_path}...")
    try:
        resp = obs_client.getObject(bucketName=BUCKET_NAME, objectKey=path, downloadPath=local_path)
        if resp.status < 300:
            print("Download successful!")
            with open(local_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Let's check what is inside the response JSON
            # In volcovoice_service.py, we save the raw JSON response
            # Let's inspect the keys or first segment words
            print(data.keys())
            
            # If it is a v3 response, let's see its structure
            # It usually has event_count, raw_events, etc.
            # Let's check "segments" list if present
            if "segments" in data:
                print("\nSegments in JSON:")
                for idx, seg in enumerate(data["segments"][:3]):
                    print(f"Segment {idx}:")
                    print(f"  caption_text: {seg.get('caption_text')}")
                    print(f"  start_ms: {seg.get('start_ms')}")
                    print(f"  end_ms: {seg.get('end_ms')}")
                    print(f"  pause_ms: {seg.get('pause_ms')}")
                    print(f"  duration_ms: {seg.get('duration_ms')}")
            else:
                # Let's print raw keys and preview
                print(str(data)[:1000])
        else:
            print(f"Failed to get object from OBS: status={resp.status}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
