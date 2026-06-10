import os
import datetime

def main():
    print("="*60)
    print("SEARCHING FOR RECENT FILES CREATED TODAY")
    print("="*60)
    
    paths = ["work", "final", "src/final", "src/work"]
    today = datetime.date.today()
    
    for p in paths:
        if os.path.exists(p):
            for root, dirs, files in os.walk(p):
                for name in files:
                    filepath = os.path.join(root, name)
                    try:
                        mtime = datetime.date.fromtimestamp(os.path.getmtime(filepath))
                        if mtime == today:
                            # Print file and size and modification time
                            dt = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                            print(f"{filepath:<70} | {dt.strftime('%H:%M:%S')} | {os.path.getsize(filepath):10d} bytes")
                    except Exception:
                        pass
    print("="*60)

if __name__ == "__main__":
    main()
