import subprocess
import json

def check_monotonicity(filepath):
    print(f"Checking {filepath}")
    cmd = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'packet=pts_time,dts_time',
        '-of', 'json', filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    pkts = data.get('packets', [])
    
    last_pts = -1
    last_dts = -1
    duplicates = 0
    non_monotonic = 0
    
    for p in pkts:
        pts = float(p.get('pts_time', 0))
        dts = float(p.get('dts_time', 0))
        
        if pts <= last_pts:
            if pts == last_pts:
                duplicates += 1
            else:
                non_monotonic += 1
                print(f"Non-monotonic PTS at {pts}s (prev {last_pts}s)")
        
        last_pts = pts
        last_dts = dts

    print(f"Duplicates: {duplicates}, Non-monotonic: {non_monotonic}")

check_monotonicity(r"C:\Users\25065\Downloads\final-1773311292887.mp4")
print("-" * 20)
check_monotonicity(r"C:\Users\25065\Downloads\final-1773311280764.mp4")
