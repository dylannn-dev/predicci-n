import os
from io import BytesIO
import boto3
import pandas as pd
from botocore.config import Config

class S3Manager:
    """
    Envuelve las operaciones básicas (subida, descarga, listado) y añade helpers
    para convertir los objetos directamente en DataFrame.
    """
    def __init__(self, bucket_or_ap_arn: str, region: str = "us-east-1"):
        cfg = Config(
            s3={"addressing_style": "virtual", "use_arn_region": True}  # Soporta Access Point ARN
        )
        self.bucket = bucket_or_ap_arn
        self.client = boto3.client("s3", region_name=region, config=cfg)

    # ───── CRUD binario ──────────────────────────────────────────────────────────
    def upload_fileobj(self, file_obj, key: str) -> str:
        """Sube un file-like object y devuelve la key."""
        self.client.upload_fileobj(file_obj, self.bucket, key, ExtraArgs={"ACL": "private"})
        return key

    def upload(self, local_path: str, key: str) -> str:
        self.client.upload_file(local_path, self.bucket, key, ExtraArgs={"ACL": "private"})
        return key

    def download(self, key: str, local_path: str):
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self.client.download_file(self.bucket, key, local_path)

    def list_keys(self, prefix: str = "") -> list[str]:
        try:
            out = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            return [o["Key"] for o in out.get("Contents", [])]
        except Exception as e:
            # Imprime el detalle del error en consola para diagnosticar
            print(f"[ERROR list_keys] Bucket={self.bucket}, Prefix={prefix}, Error={e}")
            raise

    # ───── Helpers DataFrame ─────────────────────────────────────────────────────
    def load_dataframe(self, key: str):
        """
        Devuelve el objeto de S3 directamente como DataFrame.
        No interfiere con los métodos ya existentes.
        """
        import pandas as pd
        from io import BytesIO

        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        data = obj["Body"].read()
        ext = key.split(".")[-1].lower()

        if ext in ("xlsx", "xls"):
            return pd.read_excel(BytesIO(data))
        return pd.read_csv(BytesIO(data), encoding="utf-8")