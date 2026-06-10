import os
import glob
import subprocess
import numpy as np
import wave

def extract_wav(mp4_path, wav_path):
    if os.path.exists(wav_path):
        os.remove(wav_path)
    cmd = ["ffmpeg", "-y", "-i", mp4_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", wav_path]
    subprocess.run(cmd, capture_output=True)

def read_wav(wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data = data.reshape(-1, params.nchannels)
        return data, params.framerate

if __name__ == "__main__":
    final_files = glob.glob("./final/mix_7176/final-*.mp4")
    if not final_files:
        print("No final files found!")
        exit(1)
    
    # Get the latest one
    latest_final = max(final_files, key=os.path.getmtime)
    print(f"Latest final file: {latest_final}")
    
    final_wav = "./work/mix_7176/latest_final_audio.wav"
    seg0_wav = "./work/mix_7176/seg0_check.wav"
    seg0_mp4 = "./work/mix_7176/segment_0_000.mp4"
    
    extract_wav(latest_final, final_wav)
    extract_wav(seg0_mp4, seg0_wav)
    
    data_norm, rate = read_wav(final_wav)
    data_seg, _ = read_wav(seg0_wav)
    
    # Compare first 10.4s
    length = min(len(data_norm), len(data_seg), int(10.4 * rate))
    sig_norm_L = data_norm[:length, 0]
    sig_seg_L = data_seg[:length, 0]
    
    corr_L = np.corrcoef(sig_norm_L, sig_seg_L)[0, 1]
    print(f"Correlation L (first 10.4s): {corr_L:.6f}")
    
    rms_norm = np.sqrt(np.mean(sig_norm_L**2))
    rms_seg = np.sqrt(np.mean(sig_seg_L**2))
    print(f"RMS Normalized (first 10.4s): {rms_norm:.2f}")
    print(f"RMS Original Segment (first 10.4s): {rms_seg:.2f}")
