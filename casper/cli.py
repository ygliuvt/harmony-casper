"""A Harmony CLI wrapper around casper"""

import argparse
import logging
import sys
from pathlib import Path

from casper.convert_to_csv import convert_to_csv
from casper.convert_to_parquet import convert_to_parquet
from casper.file_ops import (
    valid_input_file,
    valid_workable_file,
)


def run_casper(input_file: str, output_format: str = 'csv'):
    """Parse arguments and run casper on specified input file."""
    if not valid_input_file(input_file):
        raise ValueError("Input filename not valid")

    if not valid_workable_file(input_file):
        raise ValueError("Input file not valid")
    
    base_name = Path(input_file).stem
    
    if output_format == 'parquet':
        # For parquet, create output directory (no zip)
        output_dir = f"{base_name}_parquet"
        convert_to_parquet(input_file, output_dir, create_zip=False)
    else:
        # For CSV, create zip file
        zip_file_name = f"{base_name}.zip"
        convert_to_csv(input_file, zip_file_name)


def main() -> None:
    """Entry point for the casper command line tool."""
    logging.basicConfig(
        stream=sys.stdout,
        format="[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    
    parser = argparse.ArgumentParser(description="Convert NetCDF files to CSV or Parquet format")
    parser.add_argument("input_file", help="Input NetCDF file to convert")
    parser.add_argument(
        "--format",
        choices=["csv", "parquet"],
        default="csv",
        help="Output format (default: csv)"
    )
    args = parser.parse_args()
    
    run_casper(args.input_file, args.format)


if __name__ == "__main__":
    main()
