import wave
import numpy as np

def read_wav(wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data = data.reshape(-1, params.nchannels)
        return data, params.framerate

if __name__ == "__main__":
    seg0_wav = "./work/mix_7176/seg0.wav"
    norm0_wav = "./work/mix_7176/norm0.wav"
    
    seg, rate = read_wav(seg0_wav)
    norm, _ = read_wav(norm0_wav)
    
    print(f"Seg shape: {seg.shape}, Norm shape: {norm.shape}")
    print("Seg first 10 samples L:", seg[:10, 0])
    print("Norm first 10 samples L:", norm[:10, 0])
    
    # Calculate correlation at different offsets
    length = int(5.0 * rate) # Compare 5 seconds
    seg_sig = seg[:length, 0]
    
    best_corr = -1
    best_offset = 0
    for offset in range(-rate, rate, 100): # Check +/- 1s with step 100 samples
        if offset < 0:
            norm_sig = norm[-offset : length - offset, 0]
            curr_seg = seg_sig[:len(norm_sig)]
        else:
            norm_sig = norm[:length - offset, 0]
            curr_seg = seg_sig[offset : offset + len(norm_sig)]
            
        corr = np.corrcoef(curr_seg, norm_sig)[0, 1]
        if corr > best_corr:
            best_corr = corr
            best_offset = offset
            
    print(f"Best correlation: {best_corr:.6f} at offset {best_offset} samples ({best_offset/rate:.4f}s)")
