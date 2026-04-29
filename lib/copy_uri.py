#!/usr/bin/env python3
"""Copy files between local paths and smart_open-supported URIs."""

import argparse
import shutil

from dotenv import load_dotenv
from smart_open import open as smart_open  # type: ignore

from s3_overwrite import add_force_s3_overwrite_argument, assert_can_write_uri
from impresso_cookbook import get_transport_params  # type: ignore

# Load S3 credentials from .env file at module level
load_dotenv()


def copy_uri(src: str, dst: str, *, force_s3_overwrite: bool) -> None:
    assert_can_write_uri(dst, force_s3_overwrite=force_s3_overwrite)
    with smart_open(src, "rb", transport_params=get_transport_params(src)) as in_handle:
        with smart_open(dst, "wb", transport_params=get_transport_params(dst)) as out_handle:
            shutil.copyfileobj(in_handle, out_handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy local/S3 URI pairs.")
    parser.add_argument("pairs", nargs="+", help="Source/destination URI pairs")
    add_force_s3_overwrite_argument(parser)
    args = parser.parse_args()

    if len(args.pairs) % 2:
        parser.error("copy_uri requires source/destination pairs")

    for index in range(1, len(args.pairs), 2):
        assert_can_write_uri(
            args.pairs[index], force_s3_overwrite=args.force_s3_overwrite
        )

    for index in range(0, len(args.pairs), 2):
        copy_uri(
            args.pairs[index],
            args.pairs[index + 1],
            force_s3_overwrite=args.force_s3_overwrite,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
