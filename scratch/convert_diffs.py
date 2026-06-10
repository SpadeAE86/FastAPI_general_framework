import os

def convert_file(path):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-16') as f:
        content = f.read()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

convert_file("scratch/body_diff.txt")
convert_file("scratch/audio_diff.txt")
print("Converted successfully!")
