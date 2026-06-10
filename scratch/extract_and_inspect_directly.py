import os
import subprocess
import numpy as np
import wave

def extract_wav(mp4_path, wav_path):
    if os.path.exists(wav_path):
        os.remove(wav_path)
    cmd = ["ffmpeg", "-y", "-i", mp4_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", wav_path]
    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("FFmpeg return code:", res.returncode)
    if res.returncode != 0:
        print("FFmpeg error:", res.stderr)

def read_wav(wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data = data.reshape(-1, params.nchannels)
        return data, params.framerate

if __name__ == "__main__":
    work_dir = "./work/mix_7176"
    mp4_path = os.path.join(work_dir, "normalized_0.0_10.4_0_706421858ca5c617f71080ad52db.mp4")
    wav_path = os.path.join(work_dir, "norm_final_test.wav")
    seg0_wav = "./work/mix_7176/seg0.wav"
    
    extract_wav(mp4_path, wav_path)
    
    data_norm, rate = read_wav(wav_path)
    data_seg, _ = read_wav(seg0_wav)
    
    length = min(len(data_norm), len(data_seg), int(10.4 * rate))
    sig_norm_L = data_norm[:length, 0]
    sig_seg_L = data_seg[:length, 0]
    
    corr_L = np.corrcoef(sig_norm_L, sig_seg_L)[0, 1]
    print(f"Correlation L (first 10.4s): {corr_L:.6f}")
    
    # Check RMS of mixed L
    rms = np.sqrt(np.mean(sig_norm_L**2))
    print(f"Mixed RMS L: {rms:.2f}")
