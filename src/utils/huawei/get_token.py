import asyncio

import httpx


async def get_token_async(ak: str, sk: str, region: str, project_name: str):
    url = f"https://iam.{region}.myhuaweicloud.com/v3/auth/tokens"

    payload = {
        "auth": {
            "identity": {
                "methods": ["aksk"],
                "aksk": {
                    "access": {
                        "key": ak
                    },
                    "secret": {
                        "key": sk
                    }
                }
            },
            "scope": {
                "project": {
                    "name": project_name
                }
            }
        }
    }

    headers = {
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload, headers=headers)

    print("status_code:", resp.status_code)
    print("response body:", resp.text)

    token = resp.headers.get("X-Subject-Token")
    print("X-Subject-Token:", token)

    return token

async def main():
    ak = "YOUR_AK"
    sk = "YOUR_SK"
    region = "cn-east-3"
    project_name = "你的项目名"

    token = await get_token_async(ak, sk, region, project_name)
    print("final token:", token)

token = asyncio.run(main())
print(token)