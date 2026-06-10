import subprocess
import json
import os

def probe_file(video_path):
    print(f"\nProbing file: {os.path.basename(video_path)}")
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
            print(f"  First PTS: {packets_v[0].get('pts_time')}, Last PTS: {packets_v[-1].get('pts_time')}")
                
    # Probe audio packets
    cmd_a = [
        "ffprobe", "-v", "error", "-show_packets", "-select_streams", "a",
        "-show_entries", "packet=pts_time,duration_time", "-of", "json", video_path
    ]
    res_a = subprocess.run(cmd_a, capture_output=True, text=True)
    if res_a.returncode == 0:
        data_a = json.loads(res_a.stdout)
        packets_a = data_a.get("packets", [])
        print(f"Total Audio Packets: {len(packets_a)}")
        if packets_a:
            print(f"  First PTS: {packets_a[0].get('pts_time')}, Last PTS: {packets_a[-1].get('pts_time')}")

if __name__ == "__main__":
    probe_file("./work/mix_7176/segment_0_000.mp4")
    probe_file("./work/mix_7176/segment_1_000.mp4")
