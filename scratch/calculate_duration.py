import json

def main():
    with open("src/utils/body.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    crops = data.get("crop_config", [])
    transitions = data.get("transition_config", [])
    
    print("="*60)
    print("CALCULATING DURATION FROM BODY.JSON")
    print("="*60)
    
    total_crop_dur = 0.0
    total_extend_dur = 0.0
    len_list = []
    
    for idx, c in enumerate(crops):
        start = c.get("start", 0.0)
        end = c.get("end", 0.0)
        extend_to = c.get("extend_to")
        
        crop_dur = end - start
        effective_end = extend_to if (extend_to is not None and extend_to > end) else end
        extend_dur = effective_end - start
        
        len_list.append(extend_dur)
        total_crop_dur += crop_dur
        total_extend_dur += extend_dur
        
        print(f"Clip {idx:02d}: start={start:.3f}, end={end:.3f}, extend_to={extend_to}, crop_dur={crop_dur:.3f}, extend_dur={extend_dur:.3f}")
        
    print("-" * 60)
    print(f"Total crop duration: {total_crop_dur:.3f}s")
    print(f"Total extend duration: {total_extend_dur:.3f}s")
    
    transition_sum = sum(t.get("duration", 0.0) for t in transitions)
    print(f"Total transition overlap: {transition_sum:.3f}s")
    
    final_end = sum(len_list) - transition_sum
    print(f"Expected final duration (sum(len_list) - sum(transitions)): {final_end:.3f}s")
    print("="*60)

if __name__ == "__main__":
    main()
