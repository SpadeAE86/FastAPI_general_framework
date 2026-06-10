import subprocess
import json

def main():
    video_path = r"C:\Users\25065\Downloads\final-1781060457662.mp4"
    
    # Probe video packets
    cmd_v = [
        "ffprobe", "-v", "error", "-show_packets", "-select_streams", "v",
        "-show_entries", "packet=pts_time,duration_time", "-of", "json", video_path
    ]
    res_v = subprocess.run(cmd_v, capture_output=True, text=True)
    if res_v.returncode == 0:
        data_v = json.loads(res_v.stdout)
        packets_v = data_v.get("packets", [])
        print(f"Total Video Packets: {len(packets_v)}")
        if packets_v:
            print("First 3 Video Packets:")
            for p in packets_v[:3]:
                print(f"  pts_time: {p.get('pts_time')}, duration_time: {p.get('duration_time')}")
            print("Last 3 Video Packets:")
            for p in packets_v[-3:]:
                print(f"  pts_time: {p.get('pts_time')}, duration_time: {p.get('duration_time')}")
                
    # Probe audio packets
    cmd_a = [
        "ffprobe", "-v", "error", "-show_packets", "-select_streams", "a",
        "-show_entries", "packet=pts_time,duration_time", "-of", "json", video_path
    ]
    res_a = subprocess.run(cmd_a, capture_output=True, text=True)
    if res_a.returncode == 0:
        data_a = json.loads(res_a.stdout)
        packets_a = data_a.get("packets", [])
        print(f"\nTotal Audio Packets: {len(packets_a)}")
        if packets_a:
            print("First 3 Audio Packets:")
            for p in packets_a[:3]:
                print(f"  pts_time: {p.get('pts_time')}, duration_time: {p.get('duration_time')}")
            print("Last 3 Audio Packets:")
            for p in packets_a[-3:]:
                print(f"  pts_time: {p.get('pts_time')}, duration_time: {p.get('duration_time')}")

if __name__ == "__main__":
    main()
