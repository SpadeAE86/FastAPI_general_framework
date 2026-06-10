import subprocess
import os
import wave
import numpy as np

def probe_file(path):
    print(f"\n--- Probing {path} ---")
    cmd = ["ffprobe", "-v", "error", "-show_streams", "-show_format", path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    # Print only stream types and durations
    for line in res.stdout.split("\n"):
        if "codec_name=" in line or "codec_type=" in line or "duration=" in line or "r_frame_rate=" in line:
            print("  " + line)

def get_rms_and_correlation(wav_path, seg_wav_path, max_len=None):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data = data.reshape(-1, params.nchannels)
        sig_norm = data[:, 0]
        
    with wave.open(seg_wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data_seg = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data_seg = data_seg.reshape(-1, params.nchannels)
        sig_seg = data_seg[:, 0]
        
    length = min(len(sig_norm), len(sig_seg))
    if max_len:
        length = min(length, max_len)
    corr = np.corrcoef(sig_norm[:length], sig_seg[:length])[0, 1]
    rms = np.sqrt(np.mean(sig_norm[:length]**2))
    return rms, corr

def analyze_mp4(mp4_path, name):
    wav_path = mp4_path.replace(".mp4", "_inspect.wav")
    if os.path.exists(wav_path):
        os.remove(wav_path)
    cmd = ["ffmpeg", "-y", "-i", mp4_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", wav_path]
    subprocess.run(cmd, capture_output=True)
    
    rms, corr = get_rms_and_correlation(wav_path, "./work/mix_7176/seg_check.wav", int(10.4 * 44100))
    print(f"\n{name} (first 10.4s): RMS={rms:.2f}, Correlation={corr:.6f}")

if __name__ == "__main__":
    test_mp4 = "./work/mix_7176/test_sub_loop_loop_shortest_true.mp4"
    service_mp4 = "./work/mix_7176/normalized_0.0_10.4_0_706421858ca5c617f71080ad52db.mp4"
    
    probe_file(test_mp4)
    probe_file(service_mp4)
    
    analyze_mp4(test_mp4, "Test loop_shortest_true.mp4")
    analyze_mp4(service_mp4, "Service normalized_0.0_10.4_0_...mp4")
