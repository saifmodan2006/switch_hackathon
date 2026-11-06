import asyncio
from app.core.config import settings


async def put_private(key, data, content_type):
    config = settings()
    if not config.minio_endpoint:
        return ''  # DB remains the authenticated local-development store.
    def put():
        import boto3
        from botocore.exceptions import ClientError
        client = boto3.client('s3', endpoint_url=config.minio_endpoint,
            aws_access_key_id=config.minio_access_key, aws_secret_access_key=config.minio_secret_key)
        try:
            client.head_bucket(Bucket=config.minio_bucket)
        except ClientError as exc:
            if exc.response['ResponseMetadata']['HTTPStatusCode'] != 404:
                raise
            client.create_bucket(Bucket=config.minio_bucket)
        client.put_object(Bucket=config.minio_bucket, Key=key, Body=data, ContentType=content_type)
    await asyncio.to_thread(put)
    return key


async def delete_private(key):
    config = settings()
    if not key or not config.minio_endpoint:
        return
    def remove():
        import boto3
        client = boto3.client('s3', endpoint_url=config.minio_endpoint,
            aws_access_key_id=config.minio_access_key, aws_secret_access_key=config.minio_secret_key)
        client.delete_object(Bucket=config.minio_bucket, Key=key)
    await asyncio.to_thread(remove)
