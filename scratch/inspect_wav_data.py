import os
import subprocess
import numpy as np
import wave

def get_rms_chunks(wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data = data.reshape(-1, params.nchannels)
        rate = params.framerate
        
        print(f"\nAnalyzing: {os.path.basename(wav_path)}")
        print(f"Total duration: {len(data)/rate:.2f}s")
        # Print RMS in 2-second chunks
        chunk_size = 2 * rate
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size, 0]
            if len(chunk) == 0: continue
            rms = np.sqrt(np.mean(chunk**2))
            print(f"  {i/rate:.1f}s - {min(len(data), i+chunk_size)/rate:.1f}s RMS: {rms:.2f}")

if __name__ == "__main__":
    work_dir = "./work/mix_7176"
    mp4_path = os.path.join(work_dir, "normalized_0.0_10.4_0_706421858ca5c617f71080ad52db.mp4")
    wav_path = os.path.join(work_dir, "new_norm0_inspect.wav")
    
    if os.path.exists(wav_path):
        os.remove(wav_path)
        
    cmd = ["ffmpeg", "-y", "-i", mp4_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", wav_path]
    subprocess.run(cmd, capture_output=True)
    
    get_rms_chunks(wav_path)
    get_rms_chunks("./work/mix_7176/seg0.wav")
