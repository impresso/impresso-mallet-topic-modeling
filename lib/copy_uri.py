#!/usr/bin/env python3
"""Copy files between local paths and smart_open-supported URIs."""

import argparse
import logging
import shutil
from pathlib import Path

from smart_open import open as smart_open  # type: ignore

from s3_overwrite import (
    add_force_s3_overwrite_argument,
    assert_can_write_uri,
    is_s3_uri,
    s3_uri_exists,
)
from impresso_cookbook import get_transport_params, setup_logging  # type: ignore

log = logging.getLogger(__name__)


def uri_exists(path: str) -> bool:
    if is_s3_uri(path):
        return s3_uri_exists(path)
    return Path(path).exists()


def copy_uri(
    src: str,
    dst: str,
    *,
    force_s3_overwrite: bool,
    skip_existing: bool,
) -> None:
    if skip_existing and uri_exists(dst):
        log.info("Destination exists, skipping copy: %s", dst)
        return
    assert_can_write_uri(dst, force_s3_overwrite=force_s3_overwrite)
    with smart_open(src, "rb", transport_params=get_transport_params(src)) as in_handle:
        with smart_open(dst, "wb", transport_params=get_transport_params(dst)) as out_handle:
            shutil.copyfileobj(in_handle, out_handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy local/S3 URI pairs.")
    parser.add_argument("pairs", nargs="+", help="Source/destination URI pairs")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: %(default)s)",
    )
    parser.add_argument(
        "--log-file", dest="log_file", help="Write log to FILE", metavar="FILE"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip a source/destination pair when the destination already exists.",
    )
    add_force_s3_overwrite_argument(parser)
    args = parser.parse_args()
    setup_logging(args.log_level, args.log_file, logger=log)

    if len(args.pairs) % 2:
        parser.error("copy_uri requires source/destination pairs")

    for index in range(1, len(args.pairs), 2):
        if not args.skip_existing or not uri_exists(args.pairs[index]):
            assert_can_write_uri(
                args.pairs[index], force_s3_overwrite=args.force_s3_overwrite
            )

    for index in range(0, len(args.pairs), 2):
        copy_uri(
            args.pairs[index],
            args.pairs[index + 1],
            force_s3_overwrite=args.force_s3_overwrite,
            skip_existing=args.skip_existing,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
