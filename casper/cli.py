"""A Harmony CLI wrapper around casper"""

import argparse
import logging
import sys

from casper.convert_to_csv import convert_to_csv
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
    zip_file_name = f"{input_file.split('/')[-1].split('.')[0]}.zip"
    convert_to_csv(input_file, zip_file_name, output_format=output_format)


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
