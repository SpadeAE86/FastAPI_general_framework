import subprocess
import json
import sys

def analyze_video(filepath):
    print(f"Analyzing {filepath}")
    # Get all stream info
    cmd_streams = ['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', filepath]
    res_streams = subprocess.run(cmd_streams, capture_output=True, text=True)
    streams_data = json.loads(res_streams.stdout)
    
    for s in streams_data.get('streams', []):
        codec_type = s.get('codec_type')
        nb_frames = s.get('nb_frames', 'N/A')
        duration = s.get('duration', 'N/A')
        print(f"Stream: {codec_type}, nb_frames: {nb_frames}, duration: {duration}")

    # Check for packets at the end
    cmd_packets = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'packet=pts_time,dts_time,size,flags',
        '-of', 'json', '-read_intervals', '18.0%+', filepath
    ]
    res_packets = subprocess.run(cmd_packets, capture_output=True, text=True)
    pkts_data = json.loads(res_packets.stdout)
    pkts = pkts_data.get('packets', [])
    
    print(f"Last video packets count: {len(pkts)}")
    if pkts:
        print(f"Last video packet PTS: {pkts[-1]['pts_time']}")

    # Check audio if exists
    cmd_audio = [
        'ffprobe', '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'packet=pts_time,dts_time,size',
        '-of', 'json', '-read_intervals', '18.0%+', filepath
    ]
    res_audio = subprocess.run(cmd_audio, capture_output=True, text=True)
    if res_audio.stdout.strip():
        audio_pkts_data = json.loads(res_audio.stdout)
        audio_pkts = audio_pkts_data.get('packets', [])
        print(f"Last audio packets count: {len(audio_pkts)}")
        if audio_pkts:
            print(f"Last audio packet PTS: {audio_pkts[-1]['pts_time']}")
        
        if pkts and audio_pkts:
            v_end = float(pkts[-1]['pts_time'])
            a_end = float(audio_pkts[-1]['pts_time'])
            print(f"A/V End Gap: {abs(v_end - a_end):.6f}")

analyze_video(r"C:\Users\25065\Downloads\final-1773311292887.mp4")
print("-" * 20)
analyze_video(r"C:\Users\25065\Downloads\final-1773311280764.mp4")
