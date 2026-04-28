#!/usr/bin/env python3
"""Copy files between local paths and smart_open-supported URIs."""

import argparse
import shutil

try:
    from smart_open import open as smart_open  # type: ignore
except ModuleNotFoundError:
    import bz2
    import builtins

    def smart_open(path: str, mode: str = "r", encoding: str | None = None):
        if path.startswith("s3://"):
            raise RuntimeError("smart_open is required for S3 paths")
        if path.endswith(".bz2"):
            return bz2.open(path, mode) if "b" in mode else bz2.open(path, mode + "t" if "t" not in mode else mode, encoding=encoding)
        return builtins.open(path, mode) if "b" in mode else builtins.open(path, mode, encoding=encoding)


def copy_uri(src: str, dst: str) -> None:
    with smart_open(src, "rb") as in_handle:
        with smart_open(dst, "wb") as out_handle:
            shutil.copyfileobj(in_handle, out_handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy local/S3 URI pairs.")
    parser.add_argument("pairs", nargs="+", help="Source/destination URI pairs")
    args = parser.parse_args()

    if len(args.pairs) % 2:
        parser.error("copy_uri requires source/destination pairs")

    for index in range(0, len(args.pairs), 2):
        copy_uri(args.pairs[index], args.pairs[index + 1])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
