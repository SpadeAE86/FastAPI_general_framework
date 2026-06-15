import os
import sys
import time
from pathlib import Path

# 强制设置平台为 tencent，环境为 test
os.environ["PLATFORM"] = "tencent"
os.environ["ENV"] = "test"

# 将项目根目录的 src 目录加入到 sys.path，保证可以正常导入模块
project_root = Path(__file__).resolve().parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 导入配置和 qcloud_cos
try:
    from config.config import my_config, ENV
    from qcloud_cos import CosConfig, CosS3Client
except ImportError as e:
    print(f"[-] 导入模块失败: {e}")
    sys.exit(1)

def test_cos_connectivity():
    print("=" * 60)
    print("          腾讯云 COS 对象存储连通性检查工具")
    print("=" * 60)
    
    # 提取 COS 配置
    storage_cfg = my_config.get("object_storage", {})
    bucket = storage_cfg.get("bucket", "freeuuu-1394787485")
    region = storage_cfg.get("region", "ap-nanjing")
    
    # 优先从环境变量加载凭证，若没有则从 config 里或者硬编码加载
    secret_id = os.getenv("TENCENT_SECRET_ID")
    secret_key = os.getenv("TENCENT_SECRET_KEY")
    
    if not secret_id or not secret_key:
        print("[!] 环境变量中未检测到 TENCENT_SECRET_ID/KEY，尝试从配置文件或本地配置中读取...")
        # 兼容性读取
        secret_id = my_config.get("tencent", {}).get("vod", {}).get("secret_id")
        secret_key = my_config.get("tencent", {}).get("vod", {}).get("secret_key")
        
    if not secret_id or not secret_key:
        print("[-] 错误: 找不到有效的腾讯云 SecretId 或 SecretKey，请检查 .env 文件！")
        return False
        
    print(f"当前平台配置: {my_config.get('platform')}")
    print(f"目标 Bucket:  {bucket}")
    print(f"目标 Region:  {region}")
    # 隐藏部分 SecretId 保证安全
    masked_id = secret_id[:6] + "*" * (len(secret_id) - 10) + secret_id[-4:] if len(secret_id) > 10 else secret_id
    print(f"凭证 SecretId: {masked_id}")
    print("-" * 60)
    
    print("-> 正在尝试初始化 COS 客户端并连接...")
    start_time = time.time()
    try:
        config = CosConfig(
            Region=region,
            SecretId=secret_id,
            SecretKey=secret_key,
            Scheme="https",
            Timeout=5  # 设置连接超时
        )
        client = CosS3Client(config)
        
        # 尝试查询 Bucket 中的文件列表（限制返回1个对象），以此验证读权限和连通性
        print("-> 正在发起 list_objects 请求...")
        response = client.list_objects(
            Bucket=bucket,
            MaxKeys=1
        )
        duration = time.time() - start_time
        print(f"   [OK] COS 连接与鉴权成功! (耗时: {duration:.2f}s)")
        
        # 打印部分返回内容以确认
        contents = response.get("Contents", [])
        print(f"   Bucket 状态: 包含 {len(contents)} 个或更多对象")
        if contents:
            print(f"   示例文件: Key='{contents[0].get('Key')}', Size={contents[0].get('Size')} 字节")
            
        print("=" * 60)
        print(" Redis    连通性: 未测试")
        print(" MySQL    连通性: 未测试")
        print(" RabbitMQ 连通性: 未测试")
        print(f" COS      连通性: [OK] 成功")
        print("=" * 60)
        return True
        
    except Exception as e:
        duration = time.time() - start_time
        print(f"   [FAILED] COS 连接或鉴权失败 (耗时: {duration:.2f}s)")
        print(f"   报错详情: {e}")
        print("=" * 60)
        print(" Redis    连通性: 未测试")
        print(" MySQL    连通性: 未测试")
        print(" RabbitMQ 连通性: 未测试")
        print(f" COS      连通性: [FAILED] 失败")
        print("=" * 60)
        print("\n提示: 请检查该存储桶名称和地域是否配置正确，以及 SecretId/SecretKey 权限是否包含 COS 操作权限。")
        return False

if __name__ == "__main__":
    test_cos_connectivity()
