import os
import subprocess

def full_analyze(video):
    r = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_packets", "-show_entries", "packet=pts_time,size,flags",
        "-of", "csv=p=0", video
    ], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    lines = r.stdout.strip().split("\n")

    total_skips = 0
    boundary_skips = 0
    prev_t = None
    gaps = []
    
    # We assume boundaries are roughly at 4.0, 8.0, 12.0
    boundaries = [4.0, 8.0, 12.0]

    for line in lines:
        parts = line.split(",")
        if len(parts) < 3:
            continue
        try:
            t, sz = float(parts[0]), int(parts[1])
        except ValueError:
            continue
        if sz < 200 and "K" not in parts[2]:
            total_skips += 1
            if any(abs(t - b) < 0.25 for b in boundaries):
                boundary_skips += 1
        if prev_t is not None:
            d = t - prev_t
            if abs(d - (1.0 / 30.0)) > 0.005:
                gaps.append((prev_t, t, d))
        prev_t = t

    return {
        "total_skips": total_skips,
        "boundary_skips": boundary_skips,
        "gaps_count": len(gaps),
    }

def main():
    test_files = {
        "final_nv_orig.mp4": "src/test/mp4_test/final_nv_orig.mp4",
        "final_nv_fixA.mp4": "src/test/mp4_test/final_nv_fixA.mp4",
        "final_nv_fixB.mp4": "src/test/mp4_test/final_nv_fixB.mp4",
        "final_nv_fixC.mp4": "src/test/mp4_test/final_nv_fixC.mp4",
        "final_mp4.mp4": "src/test/mp4_test/final_mp4.mp4"
    }

    print(f"{'Filename':<20} | {'Total Skip Frames':<18} | {'Boundary Skips':<15} | {'PTS Gaps':<10}")
    print("-" * 75)
    for name, path in test_files.items():
        if os.path.exists(path):
            res = full_analyze(path)
            if res:
                print(f"{name:<20} | {res['total_skips']:18d} | {res['boundary_skips']:15d} | {res['gaps_count']:10d}")
            else:
                print(f"{name:<20} | Failed to analyze")
        else:
            print(f"{name:<20} | Not Found")

if __name__ == "__main__":
    main()
