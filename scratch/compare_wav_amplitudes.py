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
    seg, rate = read_wav("./work/mix_7176/seg0.wav")
    norm, _ = read_wav("./work/mix_7176/norm0.wav")
    
    # Find indices where seg is significantly non-zero
    seg_nonzero = np.where(np.abs(seg[:, 0]) > 500)[0]
    print(f"Seg non-zero samples: {len(seg_nonzero)}")
    if len(seg_nonzero) > 0:
        print("\nFirst 10 non-zero indices in Seg:")
        for idx in seg_nonzero[:10]:
            print(f"  idx {idx} (time {idx/rate:.3f}s): seg_val={seg[idx, 0]}, norm_val={norm[idx, 0]}")
            
    # Find indices where norm is significantly non-zero
    norm_nonzero = np.where(np.abs(norm[:, 0]) > 500)[0]
    print(f"\nNorm non-zero samples: {len(norm_nonzero)}")
    if len(norm_nonzero) > 0:
        print("\nFirst 10 non-zero indices in Norm:")
        for idx in norm_nonzero[:10]:
            print(f"  idx {idx} (time {idx/rate:.3f}s): seg_val={seg[idx, 0] if idx < len(seg) else 'N/A'}, norm_val={norm[idx, 0]}")
