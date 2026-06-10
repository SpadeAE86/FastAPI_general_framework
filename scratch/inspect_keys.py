import urllib.request
import json

def main():
    url = "https://freeuuu.obs.cn-east-3.myhuaweicloud.com/aigc/aigc_test/volcovoice_1781058617354/volcovoice_volcovoice_1781058617354_response.json"
    print("Downloading debug JSON...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        content = response.read().decode('utf-8')
        data = json.loads(content)
        
    print("Keys in JSON:", list(data.keys()))
    print("Length of content:", len(content))
    # Print the first 500 characters of the JSON content
    print("Prefix of JSON:")
    print(content[:1000])

if __name__ == "__main__":
    main()
