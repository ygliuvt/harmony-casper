import logging
from os import listdir
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from casper.convert_to_csv import (
    convert_to_csv,
)
from casper.convert_to_parquet import (
    convert_to_parquet,
)

from .. import data_for_tests_dir

module_logger = logging.getLogger(__name__)


def test_coversion():
    fname = str(
        data_for_tests_dir
        / "unit-test-data"
        / "TEMPO_HCHO_L3_V04_20250912T210435Z_S012_subsetted.nc4"
    )
    test_data_dir = str(data_for_tests_dir / "unit-test-data/")

    with TemporaryDirectory() as temp_dir:
        zip_file_name = fname.split("/")[-1].split(".")[0]

        # Convert test file to CSVs
        zip_file = f"{temp_dir}/{zip_file_name}.zip"
        num_csv_files = convert_to_csv(
            fname,
            zip_file,
            logger=module_logger,
        )
        assert num_csv_files == 2
        # Extract converted files and compare to test files in unit-test-data
        with ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
        op_files = sorted(
            [f.split("/")[-1] for f in listdir(f"{temp_dir}") if "Readme" in f or "csv" in f]
        )
        test_files = sorted(
            [f.split("/")[-1] for f in listdir(f"{test_data_dir}") if "Readme" in f or "csv" in f]
        )
        assert op_files == test_files
        for f in test_files:
            f = Path(f"{temp_dir}") / f"{f}"
            f2 = Path(f"{test_data_dir}") / f"{f}"
            assert f.read_bytes() == f2.read_bytes()


def test_parquet_conversion():
    """Test that convert_to_parquet successfully converts NetCDF to Parquet files"""
    fname = str(
        data_for_tests_dir
        / "unit-test-data"
        / "TEMPO_HCHO_L3_V04_20250912T210435Z_S012_subsetted.nc4"
    )

    with TemporaryDirectory() as temp_dir:
        zip_file_name = fname.split("/")[-1].split(".")[0]

        # Convert test file to Parquet files
        zip_file = f"{temp_dir}/{zip_file_name}.zip"
        num_parquet_files = convert_to_parquet(
            fname,
            zip_file,
            logger=module_logger,
        )
        
        # Verify that parquet files were created
        assert num_parquet_files > 0
        assert Path(zip_file).exists()
        
        # Extract and verify zip contents
        with ZipFile(zip_file, "r") as zip_ref:
            file_list = zip_ref.namelist()
            zip_ref.extractall(temp_dir)
        
        # Check that zip contains parquet files and readme files
        parquet_files = [f for f in file_list if f.endswith('.parquet')]
        readme_files = [f for f in file_list if 'Readme' in f]
        
        assert len(parquet_files) == num_parquet_files
        assert len(readme_files) >= 1  # At least one readme file (md or json)
        
        # Verify that extracted parquet files exist and are not empty
        for parquet_file in parquet_files:
            file_path = Path(temp_dir) / parquet_file
            assert file_path.exists()
            assert file_path.stat().st_size > 0


def test_parquet_conversion_no_zip():
    """Test that convert_to_parquet with create_zip=False creates individual files"""
    fname = str(
        data_for_tests_dir
        / "unit-test-data"
        / "TEMPO_HCHO_L3_V04_20250912T210435Z_S012_subsetted.nc4"
    )

    with TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "output"
        
        # Convert test file to Parquet files without zipping
        num_parquet_files = convert_to_parquet(
            fname,
            str(output_dir),
            logger=module_logger,
            create_zip=False,
        )
        
        # Verify that output directory was created
        assert output_dir.exists()
        assert output_dir.is_dir()
        
        # Verify that parquet files were created
        assert num_parquet_files > 0
        
        # Get list of files in output directory
        files = list(output_dir.iterdir())
        parquet_files = [f for f in files if f.suffix == '.parquet']
        readme_files = [f for f in files if 'Readme' in f.name]
        
        # Check that directory contains parquet files and readme files
        assert len(parquet_files) == num_parquet_files
        assert len(readme_files) >= 1  # At least one readme file (md or json)
        
        # Verify that parquet files exist and are not empty
        for parquet_file in parquet_files:
            assert parquet_file.exists()
            assert parquet_file.stat().st_size > 0
        
        # Verify readme files exist
        assert any(f.name == 'Readme.md' for f in readme_files)
        assert any(f.name == 'Readme.json' for f in readme_files)
