

# Overview

**CASPER** – CSV Automation Service for Processing & Easy Retrieval

CASPER is a Python package that converts NetCDF (.nc, .h5) files to one or more CSV or Parquet files based on the dimensional schema in the NetCDF file.

### What does it do?

Using xarray, CASPER obtains the dimensions identified in the NetCDF file and groups variables by the dimensional schema, then outputs each dimensional schema in a separate CSV or Parquet file.

# Getting started, with uv

1. Follow the instructions for installing `uv` [here](https://docs.astral.sh/uv/getting-started/installation/).
2. Install `casper`, with its dependencies, by running the following from the repository directory:

```shell
uv sync
```

## Usage

For example:

```shell
uv run casper TEMPO_NO2_L2_V04_S009G07.nc
```
For example (_note that these are pseudo-real, not actual, TEMPO file names_):

```shell
casper TEMPO_NO2_L2_V04_S009G07.nc
```

**Output:**

Zip file `TEMPO_NO2_L2_V04_S009G07.zip` including csv files:
-   `TEMPO_NO2_L2_V04_S009G07-0.csv`, → dimension schema 1 (ie, dimensions ('mirror_step', 'xtrack', 'corner'))
-   `TEMPO_NO2_L2_V04_S009G07-1.csv`, → dimension schema 2 (ie, dimensions('mirror_step', 'xtrack', 'swt_level'))

### Output Format Options

By default, CASPER generates CSV files in a zip archive. You can optionally specify Parquet format:

```shell
casper TEMPO_NO2_L2_V04_S009G07.nc --format parquet
```

**Output (Parquet):**

Individual parquet files in a directory called `TEMPO_NO2_L2_V04_S009G07_parquet/`:
-   `TEMPO_NO2_L2_V04_S009G07-0_reformatted.parquet` → dimension schema 1 (ie, dimensions ('mirror_step', 'xtrack', 'corner'))
-   `TEMPO_NO2_L2_V04_S009G07-1_reformatted.parquet` → dimension schema 2 (ie, dimensions('mirror_step', 'xtrack', 'swt_level'))
-   `Readme.md` and `Readme.json` files with metadata


### Key Features
- Reads NetCDF files and groups the data by shared dimensions and creates a CSV or Parquet file for each dimension group.
- Supports both CSV (zipped) and Parquet (individual files) output formats
- Memory-optimized chunked processing for large datasets (processes data in 1000-row chunks to minimize memory usage)
- Command-line interface and Python API for integration with NASA Harmony service orchestrator
- Verbose logging for debugging

## Installation

### From Source (Development)

For local development or the latest features:

```shell
git clone <Repository URL>
cd casper
uv sync
```

## Usage

### Basic Usage

```shell
# Generate CSV files (default)
uv run casper filename

# Generate Parquet files
uv run casper filename --format parquet
```

## Running Tests

CASPER uses pytest for testing. To run the test suite:

```shell
# Run all tests
uv run pytest tests/

# Run tests with verbose output
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/unit/test_service_adapter.py -v

# Run tests with coverage report
uv run pytest tests/ --cov=casper
```

The test suite includes:
- Unit tests for file conversion (CSV and Parquet)
- Service adapter tests for Harmony integration
- CLI and file operations tests

## Contributing

Issues and pull requests welcome on [GitHub](https://github.com/nasa/harmony-casper/).

## License & Attribution

CASPER is released under the [Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0).
