from qcloud_cos import CosConfig, CosS3Client


def vod_upload_to_cos(apply_resp: dict, local_file_path: str):
    """
    使用 ApplyUpload 返回的临时凭证上传文件到 COS
    """

    temp = apply_resp["TempCertificate"]

    config = CosConfig(
        Region=apply_resp["StorageRegion"],
        SecretId=temp["SecretId"],
        SecretKey=temp["SecretKey"],
        Token=temp["Token"],
        Scheme="https"
    )

    client = CosS3Client(config)

    bucket = apply_resp["StorageBucket"]

    # ⚠️ MediaStoragePath 是以 / 开头的，需要去掉
    key = apply_resp["MediaStoragePath"].lstrip("/")


    print(f"[COS] upload to bucket={bucket}, key={key}")

    result = client.upload_file(
        Bucket=bucket,
        Key=key,
        LocalFilePath=local_file_path,
        EnableMD5=False
    )

    print(f"[COS] upload success: {result}")

