"""
Test Supabase database and S3 (Supabase Storage) connections.

Run from project root:
  python test_supabase_s3.py

Requires: psycopg, boto3 (pip install 'psycopg[binary]' boto3)
Env vars: DATABASE_URL or SUPABASE_DB_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
          AWS_STORAGE_BUCKET_NAME, AWS_S3_ENDPOINT_URL
"""
import os
import sys
from pathlib import Path

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent
_env_path = PROJECT_ROOT / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass


def test_supabase_db() -> bool:
    """Test Supabase PostgreSQL connection."""
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("  SKIP: DATABASE_URL or SUPABASE_DB_URL not set in .env")
        return False

    try:
        import psycopg
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
                if row and row[0] == 1:
                    print("  OK: Supabase DB connected (SELECT 1)")
                    return True
        print("  FAIL: Unexpected result from DB")
        return False
    except ImportError:
        print("  SKIP: psycopg not installed. pip install 'psycopg[binary]'")
        return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_s3_storage() -> bool:
    """Test Supabase S3-compatible storage connection."""
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME")
    endpoint = os.environ.get("AWS_S3_ENDPOINT_URL")
    region = os.environ.get("AWS_S3_REGION_NAME", "ap-south-1")

    missing = []
    if not access_key:
        missing.append("AWS_ACCESS_KEY_ID")
    if not secret_key:
        missing.append("AWS_SECRET_ACCESS_KEY")
    if not bucket:
        missing.append("AWS_STORAGE_BUCKET_NAME")
    if not endpoint:
        missing.append("AWS_S3_ENDPOINT_URL")

    if missing:
        print(f"  SKIP: Missing env vars: {', '.join(missing)}")
        return False

    try:
        import boto3
        from botocore.config import Config

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

        # Verify bucket access
        client.head_bucket(Bucket=bucket)
        print(f"  OK: S3 connected (bucket '{bucket}')")
        return True
    except ImportError:
        print("  SKIP: boto3 not installed. pip install boto3")
        return False
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def main():
    print("Supabase DB + S3 Connection Test")
    print("-" * 40)

    db_ok = test_supabase_db()
    s3_ok = test_s3_storage()

    print("-" * 40)
    if db_ok and s3_ok:
        print("All checks passed.")
        sys.exit(0)
    else:
        print("Some checks failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
