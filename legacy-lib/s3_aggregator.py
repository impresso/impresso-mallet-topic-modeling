#!/usr/bin/env python3
"""
Read jsonl.bz2 files from s3 and collect specified keys and their values.

Usage:
    python3 s3_aggregator.py --s3-prefix s3://your-bucket/your-prefix --keys key1,key2 --output s3://your-output-bucket/output-prefix

Example:
    python3 s3_aggregator.py --s3-prefix s3://your-bucket/your-prefix --keys id,tokens --output s3://your-output-bucket/output.jsonl
"""

import argparse
import json
import logging
from typing import Dict, Any, Optional, Sequence

from smart_open import open as smart_open
import sys
import re
from impresso_mallet_lda.s3_to_local_stamps import get_s3_client
import tempfile
import bz2

class SmartFileHandler(logging.FileHandler):
    def _open(self) -> any:
        """Open the log file using smart_open and return a file-like object."""
        return smart_open(self.baseFilename, self.mode, encoding="utf-8")


from typing import Generator

def yield_s3_objects(bucket: str, prefix: str) -> Generator[str, None, None]:
    """Yield all objects in an S3 bucket with a given prefix.

    Args:
        bucket (str): S3 bucket name.
        prefix (str): Prefix to filter objects.

    Yields:
        str: The key of each object.
    """
    s3 = get_s3_client()
    continuation_token = None
    count = 0
    while True:
        # List objects in the specified S3 bucket with the given prefix
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            ContinuationToken=continuation_token
        ) if continuation_token else s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        
        # Yield the 'Key' of each object from the response
        for content in response.get("Contents", []):
            count += 1
            yield content["Key"]
        
        # Check if there are more objects to retrieve
        if response.get("IsTruncated"):  # If the response is truncated, there are more objects to retrieve
            continuation_token = response.get("NextContinuationToken")
        else:
            break
    logging.info(f"Found {count} objects with prefix {prefix}")


def list_s3_files_with_prefix(bucket: str, prefix: str) -> Sequence[str]:
    """List all files in an S3 bucket with a given prefix.

    Args:
        bucket (str): S3 bucket name.
        prefix (str): Prefix to filter files.

    Returns:
        Sequence[str]: List of file keys.
    """
    files = [file for file in yield_s3_objects(bucket, prefix) if file.endswith("jsonl.bz2")]
    logging.warning(f"Found {len(files)} files with prefix {prefix}")
    return files


def process_jsonl_file(data: Dict[str, Any], keys: Sequence[str]) -> Optional[Dict[str, Any]]:
    """Process a single JSON object and extract specified keys.

    Args:
        data (Dict[str, Any]): A dictionary representing a single JSON object.
        keys (Sequence[str]): Keys to extract from the JSON object.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the extracted keys and values, or None if the input is invalid.
    """
    try:
        return {key: data[key] for key in keys if key in data}
    except KeyError as e:
        logging.warning(f"Missing key in data: {e}. Skipping this entry.")
        return None


def upload_to_s3(local_path: str, s3_path: str, s3_client) -> None:
    """Upload a local file to an S3 path.

    Args:
        local_path (str): Path to the local file.
        s3_path (str): S3 path to upload the file to.
        s3_client: Boto3 S3 client.
    """
    bucket, key = re.match(r"s3://([^/]+)/(.+)", s3_path).groups()
    s3_client.upload_file(local_path, bucket, key)
    logging.info(f"Uploaded {local_path} to {s3_path}")

def process_s3_files(bucket: str, prefix: str, keys: Sequence[str], output_path: str) -> None:
    """Process JSONL.bz2 files in an S3 bucket, extract specified keys, and write to an output file (local or S3).

    Args:
        bucket (str): S3 bucket name.
        prefix (str): Prefix to filter files.
        keys (Sequence[str]): Keys to extract from each JSON object.
        output_path (str): Path to the output file (local or S3).
    """
    s3 = get_s3_client()
    transport_params = {"client": s3}
    total_lines = 0
    processed_count = 0

    suffix = output_path.split('.')[-1]
    with tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8", suffix=f".{suffix}") as tmpfile:
        tmpfile_path = tmpfile.name
        with smart_open(tmpfile_path, "w", encoding="utf-8") as tmpfile:
            for file_key in yield_s3_objects(bucket, prefix):
                if not file_key.endswith("jsonl.bz2"):
                    continue
                logging.info(f"Processing file: {file_key}")
                with smart_open(
                    f"s3://{bucket}/{file_key}",
                    "rb",
                    transport_params=transport_params,
                ) as infile:
                    for line in infile:
                        total_lines += 1
                        try:
                            data = json.loads(line)
                            processed_data = process_jsonl_file(data, keys)
                            if processed_data:
                                tmpfile.write(json.dumps(processed_data, ensure_ascii=False) + "\n")
                                processed_count += 1
                        except json.JSONDecodeError:
                            logging.error(f"Could not decode JSON from line: {line.strip()}")
                        except Exception as e:
                            logging.error(f"An error occurred: {e}")

    if output_path.startswith("s3://"):
        upload_to_s3(tmpfile_path, output_path, s3)
    else:
        import shutil
        shutil.move(tmpfile_path, output_path)
        logging.info(f"Moved {tmpfile_path} to {output_path}")

    logging.info(f"Total lines read: {total_lines}")
    logging.info(f"Total items processed and written: {processed_count}")


def parse_arguments(args: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        args (Optional[Sequence[str]]): Command-line arguments.

    Returns:
        argparse.Namespace: Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        description="Collect specified keys from JSONL.bz2 files in S3.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        help="Path to store the output JSONL file (local or S3). Example: s3://your-bucket/output-prefix/output.jsonl",
    )

    parser.add_argument(
        "-k",
        "--keys",
        type=str,
        nargs="+",
        required=True,
        help="List of keys to extract from each JSON object",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    parser.add_argument("--log-file", type=str, help="Log file path")
    parser.add_argument(
        "--s3-prefix",
        type=str,
        required=True,
        help="S3 path prefix (s3://BUCKET/PREFIX) to read JSONL.bz2 files",
    )
    return parser.parse_args(args)


def main(args: Optional[Sequence[str]] = None) -> None:
    """Main function to run the data extraction process.

    Args:
        args (Optional[Sequence[str]]): Command-line arguments.
    """

    if args is None:
        args = sys.argv[1:]
    options = parse_arguments(args)

    handlers = [logging.StreamHandler()]
    if options.log_file:
        handlers.append(SmartFileHandler(options.log_file, mode="w"))
    logging.basicConfig(
        level=options.log_level,
        format="%(asctime)-15s %(filename)s:%(lineno)d %(levelname)s: %(message)s",
        handlers=handlers,
        force=True,
    )

    logging.info(f"Processing S3 prefix: {options.s3_prefix}")
    match = re.match(r"s3://([^/]+)/(.+)", options.s3_prefix)
    if not match:
        logging.error("Invalid S3 prefix format. Expected s3://BUCKET/PREFIX")
        sys.exit(1)
    bucket, prefix = match.groups()

    output_match = re.match(r"s3://([^/]+)/(.+)", options.output)
    if not output_match and options.output.startswith("s3://"):
        logging.error("Invalid S3 output format. Expected s3://BUCKET/PREFIX")
        sys.exit(1)

    keys = options.keys

    process_s3_files(bucket, prefix, keys, options.output)

    logging.info(f"Processing complete. Results saved to {options.output}")


if __name__ == "__main__":
    main()
