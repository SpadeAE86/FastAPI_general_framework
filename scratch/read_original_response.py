import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.obs_utils import obs_client, BUCKET_NAME

def main():
    path = "aigc/aigc_test/volcovoice_1780971203719/volcovoice_volcovoice_1780971203719_response.json"
    local_path = "./scratch/volcovoice_1780971203719_response.json"
    print(f"Downloading directly from OBS: {path} to {local_path}...")
    try:
        resp = obs_client.getObject(bucketName=BUCKET_NAME, objectKey=path, downloadPath=local_path)
        if resp.status < 300:
            print("Download successful!")
            with open(local_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            detail_info = data.get("object_list", [{}])[0].get("detail_info", [])
            print(f"Total duration in JSON: {data.get('object_list', [{}])[0].get('duration')}")
            
            print("\nOriginal response details:")
            print(f"{'Index':<5} | {'Duration':<10} | {'Pause':<10} | {'Sum':<10} | {'Text'}")
            print("-" * 85)
            
            total_sum = 0.0
            for idx, item in enumerate(detail_info):
                dur = item.get("segment_duration", 0.0)
                pause = item.get("pause", 0.0)
                seg_sum = dur + pause
                total_sum += seg_sum
                print(f"{idx:<5} | {dur:<10.3f} | {pause:<10.3f} | {seg_sum:<10.3f} | {item.get('caption_text')}")
            print(f"\nSum of (dur + pause): {total_sum:.3f}")
        else:
            print(f"Failed to get object from OBS: status={resp.status}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
