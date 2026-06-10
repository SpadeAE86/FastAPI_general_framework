import subprocess
import os
import numpy as np
import wave

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

def run_cmd(cmd, name):
    print(f"\n--- Running {name} ---")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Failed: {res.stderr}")
        return
    
    # Extract audio to wav
    out_mp4 = cmd[-1]
    out_wav = out_mp4.replace(".mp4", ".wav")
    if os.path.exists(out_wav):
        os.remove(out_wav)
    cmd_ext = ["ffmpeg", "-y", "-i", out_mp4, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", out_wav]
    subprocess.run(cmd_ext, capture_output=True)
    
    rms, corr = get_rms_and_correlation(out_wav, "./work/mix_7176/seg_check.wav", int(5.0 * 44100))
    print(f"RMS (first 5s): {rms:.2f}, Correlation with original: {corr:.6f}")

if __name__ == "__main__":
    seg_mp4 = r"./work/mix_7176/segment_0_000.mp4"
    voice_path = r"cache/9b/ee/19be254a7b21608baa66975d55e9.wav"
    
    # Command 1 (Reproducible Bug)
    cmd1 = [
        "ffmpeg", "-y", "-i", seg_mp4, "-i", voice_path,
        "-filter_complex", "[0:v]trim=0:5,setpts=PTS-STARTPTS[v];[0:a]atrim=0:5,asetpts=PTS-STARTPTS,volume=1,apad=whole_dur=5[a0];[1:a]atrim=0:5,asetpts=PTS-STARTPTS,volume=3[a1];[a0][a1]amix=inputs=2:duration=longest:normalize=0[m]",
        "-map", "[v]", "-map", "[m]", "-c:v libx264", "-preset", "ultrafast", "-c:a", "aac", "./work/mix_7176/test_repro1.mp4"
    ]
    # Note: we need to join -c:v libx264 as separate arguments
    cmd1_clean = []
    for arg in cmd1:
        if " " in arg and not arg.startswith("[") and not arg.startswith("./"):
            cmd1_clean.extend(arg.split(" "))
        else:
            cmd1_clean.append(arg)
            
    # Command 2 (No Bug / Correct)
    cmd2 = [
        "ffmpeg", "-y", "-t", "5", "-i", seg_mp4, "-i", voice_path,
        "-filter_complex", "[0:a]volume=3[main];[1:a]volume=2[tts];[main][tts]amix=inputs=2:duration=longest:weights='1 1':normalize=0[m]",
        "-map", "0:v", "-map", "[m]", "-c:v", "copy", "./work/mix_7176/test_repro2.mp4"
    ]
    
    run_cmd(cmd1_clean, "Command 1 (Trim and pad)")
    run_cmd(cmd2, "Command 2 (Volume and mix)")
