"""
压测火山 TTS 字数上限
每个字数级别跑 3 次，统计成功率
"""
import sys
import os
import asyncio
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from utils.volcano_utils import volcano_generate_voice

# 真实风格的口播文本，按字数截断/扩展
BASE_TEXT = (
    "早上出门赶地铁吹了一路冷风，到公司脸绷得又红又痒，还好我工位抽屉一直放着小青蛙。"
    "挤一点涂开润润的一点都不粘，涂完没一会儿泛红就消下去了，成分也放心，没有酒精香精，"
    "敏感肌用着完全不刺激，一整天脸都润润的不会干。你们平时通勤、待在空调房的，"
    "真的可以备一支，这种日常场景用着太方便了。我连着用了三个月，肤感真的有在变好，"
    "皮肤慢慢就没那么爱泛红了，朋友看到都问我最近用了什么，推荐给她用了也说好。"
    "价格也不贵，就是那种放在抽屉里随手就涂的小东西，但效果真的超出预期。"
    "如果你也是敏感肌，或者换季容易干痒起皮，真的可以试试这个，我觉得是目前用过最舒服的。"
)

TARGETS = [
    ("100字", 100),
    ("120字", 120),
    ("150字", 150),
    ("200字", 200),
    ("250字", 250),
    ("300字", 300),
]

RUNS_PER_TARGET = 3

async def single_run(text: str, run_idx: int, label: str) -> tuple[bool, float, str]:
    output_path = f"./scratch/tts_test_{label}_{run_idx}.wav"
    t0 = time.time()
    try:
        await volcano_generate_voice(
            voice_type="zh_female_roumeinvyou_emo_v2_mars_bigtts",
            text=text,
            filename=output_path,
        )
        elapsed = time.time() - t0
        return True, elapsed, ""
    except Exception as e:
        elapsed = time.time() - t0
        return False, elapsed, str(e)[:120]

async def test_target(label: str, char_count: int):
    # 截断或重复填充到目标字数
    text = BASE_TEXT
    if len(text) < char_count:
        # 重复拼接直到够长再截断
        while len(text) < char_count:
            text += BASE_TEXT
    text = text[:char_count]

    print(f"\n{'='*55}")
    print(f"  测试: {label}  (实际 {len(text)} 字)")
    print(f"  文本: {text[:40]}...{text[-10:]}")
    print(f"{'='*55}")

    results = []
    for i in range(RUNS_PER_TARGET):
        ok, elapsed, err = await single_run(text, i, label)
        status = "OK" if ok else "FAIL"
        print(f"  Run {i+1}/{RUNS_PER_TARGET}: {status}  {elapsed:.1f}s{'  err: ' + err if err else ''}")
        results.append(ok)

    passed = sum(results)
    rate = passed / RUNS_PER_TARGET * 100
    print(f"  => 成功率: {passed}/{RUNS_PER_TARGET}  ({rate:.0f}%)")
    return passed, RUNS_PER_TARGET

async def main():
    print("火山 TTS 字数上限压测")
    print(f"每个档位跑 {RUNS_PER_TARGET} 次\n")

    summary = []
    for label, char_count in TARGETS:
        passed, total = await test_target(label, char_count)
        summary.append((label, char_count, passed, total))

    print(f"\n{'='*55}")
    print("汇总:")
    print(f"{'档位':<10} {'字数':>6} {'成功率':>10}")
    print(f"{'-'*30}")
    for label, char_count, passed, total in summary:
        rate = passed / total * 100
        flag = "OK" if passed == total else ("WARNING" if passed > 0 else "FAIL")
        print(f"{label:<10} {char_count:>6}字  {passed}/{total} ({rate:.0f}%)  {flag}")

if __name__ == "__main__":
    asyncio.run(main())
