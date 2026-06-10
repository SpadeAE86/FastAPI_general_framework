import os
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
    work_dir = "./work/mix_7176"
    seg0_mp4 = os.path.join(work_dir, "segment_0_000.mp4")
    norm0_mp4 = os.path.join(work_dir, "normalized_0.0_10.4_0_706421858ca5c617f71080ad52db.mp4")
    
    seg0_wav = "./work/mix_7176/seg0.wav"
    norm0_wav = "./work/mix_7176/norm0.wav"
    
    extract_wav(seg0_mp4, seg0_wav)
    extract_wav(norm0_mp4, norm0_wav)
    
    data_norm, rate = read_wav(norm0_wav)
    data_seg, _ = read_wav(seg0_wav)
    
    # Segment 0 is 10.4s. Let's compare the first 10.4s
    length = min(len(data_norm), len(data_seg), int(10.4 * rate))
    
    sig_norm_L = data_norm[:length, 0]
    sig_seg_L = data_seg[:length, 0]
    
    corr_L = np.corrcoef(sig_norm_L, sig_seg_L)[0, 1]
    print(f"Correlation L (first 10.4s): {corr_L:.6f}")
    
    # Check if there is any overlap
    non_zero_seg = np.where(np.abs(sig_seg_L) > 100)[0]
    print(f"Non-zero original samples: {len(non_zero_seg)}")
    if len(non_zero_seg) > 0:
        idx = non_zero_seg[len(non_zero_seg)//2]
        print(f"At index {idx}: original={sig_seg_L[idx]}, mixed={sig_norm_L[idx]}")
