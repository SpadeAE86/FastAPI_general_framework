import os
import shutil
import requests

import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from utils.file_utils import read_yaml, save_yaml

app_title = "video_mix"

local_audio_tts_providers = ['chatTTS', 'GPTSoVITS', 'CosyVoice']
local_audio_recognition_providers = ['fasterwhisper', 'sensevoice']
local_audio_recognition_fasterwhisper_module_names = ['large-v3', 'large-v2', 'large-v1', 'distil-large-v3',
                                                      'distil-large-v2', 'medium', 'base', 'small', 'tiny']
local_audio_recognition_fasterwhisper_device_types = ['cuda', 'cpu', 'auto']
local_audio_recognition_fasterwhisper_compute_types = ['int8', 'int8_float16', 'float16']

vpc = "/obs"  #vpc储存卷挂载路径
RESOURCE_DIR = "./resource"
FINAL_DIR = "./final"
FONT_DIR = "./font"
OUTPUT_DIR = "./work"

driver_types = {
    "chrome": 'chrome',
    "firefox": 'firefox'}

filter_options = ["temperature", "tint", "hue", "saturation", "brightness", "contrast", "sharpness", "gamma", "boxblur",
                  "gblur", "dblur"]

audio_speech_rate = {
    "kenny" : 4.651496641981914,
    "aifei" : 5.165382903618127,
    "aiqian" : 4.294418512571484,
    "maoxiaomei" : 4.947731915548115,
    "siyue" : 5.101272657175458,
    "xiaoxian" : 4.759277536672374,
    "zhimao" : 4.639149256865643,
    "zhixiaomei" : 4.509686234988655,
    "zhixiaoxia" : 4.537818839709418,
    "zhifeng_emo": 4.019146284436771,
    "zhibing_emo": 4.887035715216325,
    "zhimiao_emo": 4.737786722269002,
    "zhimi_emo": 4.583573593523443,
    "zhiyan_emo": 4.577448153779756,
    "zhibei_emo": 4.357534410051467,
    "zhitian_emo": 4.351227712210594
}

male_voice = ["Kenny(温暖男声)", "艾飞(激昂解说男声)"]
female_voice = ["艾倩(资讯女声)", "猫小美(活力女声)", "思悦(温柔女声)", "小仙(亲切女声)", "知猫(普通话女声)", "知小妹(直播数字人)", "知小夏(对话数字人)"]

emotion_option = ["neutral","happy","angry","sad","surprise"]
emotion_voice = {
    "知锋_多情感": "zhifeng_emo",
    "知冰_多情感": "zhibing_emo",
    "知妙_多情感": "zhimiao_emo",
    "知米_多情感": "zhimi_emo",
    "知燕_多情感": "zhiyan_emo",
    "知贝_多情感": "zhibei_emo",
    "知甜_多情感": "zhitian_emo"
}


douyin_site = "https://creator.douyin.com/creator-micro/content/upload"
shipinhao_site = "https://channels.weixin.qq.com/platform/post/create"
kuaishou_site = "https://cp.kuaishou.com/article/publish/video"
xiaohongshu_site = "https://creator.xiaohongshu.com/publish/publish?source=official"
bilibili_site = "https://member.bilibili.com/platform/upload/video/frame"

# 定义请求体的字符串限制 todo: 需要额外封装进某个专门储存字典的文件内
audio_speed = ["normal", "fast", "faster", "fastest", "slow", "slower", "slowest"]
alivoice_options = {
    "知小白(普通话女声)": "zhixiaobai",
    "知小夏(对话数字人)": "zhixiaoxia",
    "知小妹(直播数字人)": "zhixiaomei",
    "知柜(普通话女声)": "zhigui",
    "知硕(普通话男声)": "zhishuo",
    "艾夏(普通话女声)": "aixia",
    "小云(标准女声)": "xiaoyun",
    "小刚(标准男声)": "xiaogang",
    "若兮(温柔女声)": "ruoxi",
    "思琪(温柔女声)": "siqi",
    "思佳(标准女声)": "sijia",
    "思诚(标准男声)": "sicheng",
    "艾琪(温柔女声)": "aiqi",
    "艾佳(标准女声)": "aijia",
    "艾诚(标准男声)": "aicheng",
    "艾达(标准男声)": "aida",
    "宁儿(标准女声)": "ninger",
    "瑞琳(标准女声)": "ruilin",
    "思悦(温柔女声)": "siyue",
    "艾雅(严厉女声)": "aiya",
    "艾美(甜美女声)": "aimei",
    "艾雨(自然女声)": "aiyu",
    "艾悦(温柔女声)": "aiyue",
    "艾静(严厉女声)": "aijing",
    "小美(甜美女声)": "xiaomei",
    "艾娜(浙普女声)": "aina",
    "依娜(浙普女声)": "yina",
    "思婧(严厉女声)": "sijing",
    "思彤(儿童音)": "sitong",
    "小北(萝莉女声)": "xiaobei",
    "艾彤(儿童音)": "aitong",
    "艾薇(萝莉女声)": "aiwei",
    "艾宝(萝莉女声)": "aibao",
    "知猫(普通话女声)": "zhimao",
    "艾倩(资讯女声)": "aiqian",
    "艾伦(悬疑解说男声)": "ailun",
    "艾飞(激昂解说男声)": "aifei",
    "小仙(亲切女声)": "xiaoxian",
    "猫小美(活力女声)": "maoxiaomei",
    "Kenny(温暖男声)": "kenny",
    "知锋_多情感": "zhifeng_emo",
    "知冰_多情感": "zhibing_emo",
    "知妙_多情感": "zhimiao_emo",
    "知米_多情感": "zhimi_emo",
    "知燕_多情感": "zhiyan_emo",
    "知贝_多情感": "zhibei_emo",
    "知甜_多情感": "zhitian_emo",
    "male": "random_male",
    "female": "random_female"
}

digital_human_platform = [
    "华为云",
    "阿里云",
    "火山引擎",
    "即梦",
    "通译万象"
]

# 获取当前脚本的绝对路径
script_path = os.path.abspath(__file__)

# print("当前脚本的绝对路径是:", script_path)

# 脚本所在的目录
script_dir = os.path.dirname(script_path)

config_example_file_name = "config.example.yml"
config_file_name = "config.yml"

config_example_file = os.path.join(script_dir, config_example_file_name)
config_file = os.path.join(script_dir, config_file_name)

if load_dotenv:
    for env_file in (
        os.path.join(os.path.dirname(os.path.dirname(script_dir)), ".env"),
        os.path.join(script_dir, ".env"),
    ):
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)


def load_config():
    # 加载配置文件
    if not os.path.exists(config_file):
        shutil.copy(config_example_file, config_file)
    if os.path.exists(config_file):
        return read_yaml(config_file)
    return None


def test_config(todo_config, *args):
    temp_config = todo_config
    for arg in args:
        if arg not in temp_config:
            temp_config[arg] = {}
        temp_config = temp_config[arg]


def save_config():
    # 保存配置文件
    if os.path.exists(config_file):
        save_yaml(config_file, my_config)

    

my_config = load_config()
volcano_config = my_config.setdefault("audio", {}).setdefault("Volcano", {})
volcano_config["app_id"] = os.environ.get("VOLCANO_APP_ID", volcano_config.get("app_id"))
volcano_config["access_token"] = os.environ.get("VOLCANO_ACCESS_TOKEN", volcano_config.get("access_token"))
volcano_config["cluster"] = os.environ.get("VOLCANO_CLUSTER", volcano_config.get("cluster", "volcano_tts"))
volcano_config["host"] = os.environ.get("VOLCANO_HOST", volcano_config.get("host", "wss://openspeech.bytedance.com/api/v1/tts/ws_binary"))
ENV = my_config['env']
MY_CONFIG = my_config # For colleague's code compatibility

# --- 项目根目录 ---
from pathlib import Path
def get_project_root() -> Path:
    current_path = Path(__file__).resolve()
    while current_path.parent != current_path:
        if (current_path / 'src').exists():
            return current_path
        current_path = current_path.parent
    raise FileNotFoundError

PROJECT_ROOT: Path = get_project_root()

# --- logs 目录 ---
LOGS_DIR: Path = PROJECT_ROOT / 'logs'

# --- src 目录 ---
SRC_DIR: Path = PROJECT_ROOT / 'src'

# --- static 目录 ---
STATIC_DIR: Path = PROJECT_ROOT / 'static'

# --- temp 目录 ---
TEMP_DIR: Path = PROJECT_ROOT / 'temp'
os.makedirs(TEMP_DIR, exist_ok=True)

# --- ffmpeg 目录 ---
FFMPEG_DIR: Path = STATIC_DIR / 'ffmpeg'
os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ["PATH"]

# --- fonts 目录 ---
FONTS_DIR: Path = STATIC_DIR / 'fonts'
os.environ["PATH"] = str(FONTS_DIR) + os.pathsep + os.environ["PATH"]

CONFIG_FILE: Path = Path(config_file)

# 解决循环引用：在所有常量初始化完成后，最后暴露 log 供全局 * import
from utils.log_utils import logger as log
