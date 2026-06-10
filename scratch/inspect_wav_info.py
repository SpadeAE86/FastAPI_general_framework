import wave
import glob
import os

if __name__ == "__main__":
    cache_wavs = glob.glob("cache/**/*.wav", recursive=True)
    print(f"Found {len(cache_wavs)} wav files in cache.")
    for path in cache_wavs[:15]:
        with wave.open(path, 'rb') as w:
            params = w.getparams()
            print(f"{os.path.basename(path)}: Channels={params.nchannels}, SampleWidth={params.sampwidth}, Rate={params.framerate}, Frames={params.nframes}")
