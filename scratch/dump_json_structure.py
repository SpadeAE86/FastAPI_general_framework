import urllib.request
import json

url = "https://freeuuu.obs.cn-east-3.myhuaweicloud.com/aigc/aigc_test/volcovoice_1781058617354/volcovoice_volcovoice_1781058617354_response.json"
response = urllib.request.urlopen(url)
data = json.loads(response.read().decode('utf-8'))

print("Root keys:", data.keys())
if "object_list" in data:
    obj = data["object_list"][0]
    print("Object keys:", obj.keys())
    if "detail_info" in obj:
        print("Detail info count:", len(obj["detail_info"]))
        print("First detail info item:", obj["detail_info"][0])
    
# Let's check other keys in the root
for k in data.keys():
    if k != "object_list":
        print(f"{k}: {data[k]}")
