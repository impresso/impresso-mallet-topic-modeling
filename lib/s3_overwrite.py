"""Helpers for protecting S3 outputs from accidental overwrite."""

from __future__ import annotations

import argparse
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return None

try:
    from impresso_cookbook import get_s3_client  # type: ignore
except ImportError:
    def get_s3_client():
        import boto3
        return boto3.client("s3")

load_dotenv()  # Load credentials at module level


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise argparse.ArgumentTypeError(
        f"expected TRUE/FALSE for --force-s3-overwrite, got {value!r}"
    )


def add_force_s3_overwrite_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--force-s3-overwrite",
        type=parse_bool,
        default=False,
        metavar="TRUE/FALSE",
        help="Allow overwriting existing s3:// outputs. Defaults to FALSE.",
    )


def is_s3_uri(path: str | None) -> bool:
    return bool(path and path.startswith("s3://"))


def s3_uri_exists(path: str) -> bool:
    from botocore.exceptions import ClientError  # type: ignore

    parsed = urlparse(path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    client = get_s3_client()
    try:
        client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        error = exc.response.get("Error", {})
        if error.get("Code") in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise
    return True


def assert_can_write_uri(path: str | None, *, force_s3_overwrite: bool) -> None:
    if not is_s3_uri(path):
        return
    if force_s3_overwrite:
        return
    if s3_uri_exists(path):
        raise FileExistsError(
            f"{path} already exists; rerun with --force-s3-overwrite TRUE to replace it"
        )
