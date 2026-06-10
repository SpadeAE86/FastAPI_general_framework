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
    norm_mp4 = os.path.join(work_dir, "normalized_0.0_10.4_0_706421858ca5c617f71080ad52db.mp4")
    seg_mp4 = os.path.join(work_dir, "segment_0_000.mp4")
    
    norm_wav = "./work/mix_7176/norm_new.wav"
    seg_wav = "./work/mix_7176/seg_new.wav"
    
    print("Extracting new WAV files...")
    extract_wav(norm_mp4, norm_wav)
    extract_wav(seg_mp4, seg_wav)
    
    data_norm, rate = read_wav(norm_wav)
    data_seg, _ = read_wav(seg_wav)
    
    length = min(len(data_norm), len(data_seg), 10 * rate)
    sig_norm = data_norm[:length, 0]
    sig_seg = data_seg[:length, 0]
    
    corr = np.corrcoef(sig_norm, sig_seg)[0, 1]
    print(f"New Correlation: {corr:.6f}")
    
    # Check RMS
    rms_seg = np.sqrt(np.mean(sig_seg**2))
    rms_norm = np.sqrt(np.mean(sig_norm**2))
    print(f"Original Segment RMS: {rms_seg:.2f}")
    print(f"Normalized Mixed RMS: {rms_norm:.2f}")
    
    # Print some non-zero samples
    non_zero_indices = np.where(np.abs(sig_seg) > 1000)[0]
    if len(non_zero_indices) > 0:
        idx = non_zero_indices[len(non_zero_indices)//2]
        print(f"At sample {idx} ({(idx/rate):.3f}s):")
        print(f"  Original: {sig_seg[idx]}")
        print(f"  Mixed: {sig_norm[idx]}")
