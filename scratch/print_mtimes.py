import os
import glob
import datetime

files = glob.glob("work/mix_7176/*")
for f in sorted(files):
    mtime = os.path.getmtime(f)
    dt = datetime.datetime.fromtimestamp(mtime)
    print(f"{f:70} : {dt} ({os.path.getsize(f)} bytes)")
