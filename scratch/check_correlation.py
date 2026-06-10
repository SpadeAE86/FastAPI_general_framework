import os
import numpy as np
import wave

def read_wav(wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data = data.reshape(-1, params.nchannels)
        return data, params.framerate

if __name__ == "__main__":
    norm_wav = "./work/mix_7176/norm_check.wav"
    seg_wav = "./work/mix_7176/seg_check.wav"
    
    data_norm, rate = read_wav(norm_wav)
    data_seg, _ = read_wav(seg_wav)
    
    # Trim both to 10 seconds (original segment duration)
    length = min(len(data_norm), len(data_seg), 10 * rate)
    
    sig_norm = data_norm[:length, 0]
    sig_seg = data_seg[:length, 0]
    
    # Calculate correlation coefficient
    corr = np.corrcoef(sig_norm, sig_seg)[0, 1]
    print(f"Correlation coefficient between original segment and normalized output (first 10 seconds): {corr:.6f}")
    
    # Let's check if the difference contains the original segment
    # Let's find some non-zero samples in original segment and see their value in normalized
    non_zero_indices = np.where(np.abs(sig_seg) > 1000)[0]
    print(f"Number of samples with amplitude > 1000 in original segment: {len(non_zero_indices)}")
    if len(non_zero_indices) > 0:
        idx = non_zero_indices[len(non_zero_indices)//2]
        print(f"Sample index: {idx}")
        print(f"Original segment value: {sig_seg[idx]}")
        print(f"Normalized output value: {sig_norm[idx]}")
