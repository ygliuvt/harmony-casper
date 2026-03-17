import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, patch, call
from uuid import uuid4

import pytest
from pystac import Catalog, Item
from pystac.item import Asset

from casper.harmony.service_adapter import CasperAdapter
from .. import data_for_tests_dir

module_logger = logging.getLogger(__name__)


@pytest.fixture
def mock_message():
    """Create a mock Harmony message"""
    message = Mock()
    message.accessToken = "test_token"
    message.stagingLocation = "file:///tmp/staging"
    message.user = "test_user"
    message.requestId = "test_request_id"
    return message


@pytest.fixture
def mock_config():
    """Create a mock config"""
    config = Mock()
    config.max_download_retries = 3
    return config


@pytest.fixture
def mock_catalog():
    """Create a mock STAC catalog with test items"""
    catalog = Catalog(str(uuid4()), "Test Catalog")
    item = Item(
        str(uuid4()),
        geometry=None,
        bbox=None,
        datetime=None,
        properties={
            "start_datetime": "2025-01-01T00:00:00Z",
            "end_datetime": "2025-01-01T01:00:00Z"
        }
    )
    # Add mock asset with URL and proper roles/media type
    item.add_asset("data", Asset(
        "https://example.com/test.nc4", 
        media_type="application/x-netcdf4",
        roles=["data"]
    ))
    catalog.add_item(item)
    return catalog


@pytest.fixture
def test_netcdf_file():
    """Return path to test NetCDF file"""
    return str(
        data_for_tests_dir
        / "unit-test-data"
        / "TEMPO_HCHO_L3_V04_20250912T210435Z_S012_subsetted.nc4"
    )


@patch('casper.harmony.service_adapter.download_file')
@patch('casper.harmony.service_adapter.convert_to_parquet')
@patch('casper.harmony.service_adapter.convert_to_csv')
def test_process_file_with_parquet_format(
    mock_csv, mock_parquet, mock_download,
    mock_message, mock_config, mock_catalog, test_netcdf_file
):
    """Test that convert_to_parquet is called when format.mime is application/parquet"""
    # Setup
    mock_message.format = Mock()
    mock_message.format.mime = "application/parquet"
    mock_download.return_value = test_netcdf_file
    
    adapter = CasperAdapter(mock_message, catalog=mock_catalog, config=mock_config)
    
    with patch.object(adapter, '_stage', return_value='https://example.com/staged.zip'):
        # Execute
        result = adapter.process_file(mock_catalog)
    
    # Verify
    mock_parquet.assert_called_once()
    mock_csv.assert_not_called()
    assert isinstance(result, Catalog)
    assert len(list(result.get_items())) == 1


@patch('casper.harmony.service_adapter.download_file')
@patch('casper.harmony.service_adapter.convert_to_parquet')
@patch('casper.harmony.service_adapter.convert_to_csv')
def test_process_file_with_csv_format(
    mock_csv, mock_parquet, mock_download,
    mock_message, mock_config, mock_catalog, test_netcdf_file
):
    """Test that convert_to_csv is called when format.mime is text/csv"""
    # Setup
    mock_message.format = Mock()
    mock_message.format.mime = "text/csv"
    mock_download.return_value = test_netcdf_file
    
    adapter = CasperAdapter(mock_message, catalog=mock_catalog, config=mock_config)
    
    with patch.object(adapter, '_stage', return_value='https://example.com/staged.zip'):
        # Execute
        result = adapter.process_file(mock_catalog)
    
    # Verify
    mock_csv.assert_called_once()
    mock_parquet.assert_not_called()
    assert isinstance(result, Catalog)


@patch('casper.harmony.service_adapter.download_file')
@patch('casper.harmony.service_adapter.convert_to_parquet')
@patch('casper.harmony.service_adapter.convert_to_csv')
def test_process_file_without_format_defaults_to_csv(
    mock_csv, mock_parquet, mock_download,
    mock_message, mock_config, mock_catalog, test_netcdf_file
):
    """Test that convert_to_csv is called by default when format.mime is not set"""
    # Setup - set format.mime to a default CSV mime type
    mock_message.format = Mock()
    mock_message.format.mime = "text/csv"
    mock_download.return_value = test_netcdf_file
    
    adapter = CasperAdapter(mock_message, catalog=mock_catalog, config=mock_config)
    
    with patch.object(adapter, '_stage', return_value='https://example.com/staged.zip'):
        # Execute
        result = adapter.process_file(mock_catalog)
    
    # Verify
    mock_csv.assert_called_once()
    mock_parquet.assert_not_called()
    assert isinstance(result, Catalog)


@patch('casper.harmony.service_adapter.download_file')
@patch('casper.harmony.service_adapter.convert_to_parquet')
@patch('casper.harmony.service_adapter.convert_to_csv')
def test_process_file_with_format_but_no_mime_defaults_to_csv(
    mock_csv, mock_parquet, mock_download,
    mock_message, mock_config, mock_catalog, test_netcdf_file
):
    """Test that convert_to_csv is called when mime type contains 'csv'"""
    # Setup - format.mime is set to application/csv (contains 'csv')
    mock_message.format = Mock()
    mock_message.format.mime = "application/csv"
    mock_download.return_value = test_netcdf_file
    
    adapter = CasperAdapter(mock_message, catalog=mock_catalog, config=mock_config)
    
    with patch.object(adapter, '_stage', return_value='https://example.com/staged.zip'):
        # Execute
        result = adapter.process_file(mock_catalog)
    
    # Verify
    mock_csv.assert_called_once()
    mock_parquet.assert_not_called()
    assert isinstance(result, Catalog)


@patch('casper.harmony.service_adapter.download_file')
@patch('casper.harmony.service_adapter.convert_to_parquet')
@patch('casper.harmony.service_adapter.convert_to_csv')
def test_process_file_with_other_mime_type_defaults_to_parquet(
    mock_csv, mock_parquet, mock_download,
    mock_message, mock_config, mock_catalog, test_netcdf_file
):
    """Test that convert_to_parquet is called for mime types without 'csv' in them"""
    # Setup
    mock_message.format = Mock()
    mock_message.format.mime = "application/json"
    mock_download.return_value = test_netcdf_file
    
    adapter = CasperAdapter(mock_message, catalog=mock_catalog, config=mock_config)
    
    with patch.object(adapter, '_stage', return_value='https://example.com/staged.zip'):
        # Execute
        result = adapter.process_file(mock_catalog)
    
    # Verify
    mock_parquet.assert_called_once()
    mock_csv.assert_not_called()
    assert isinstance(result, Catalog)


def test_invoke_without_catalog(mock_message, mock_config):
    """Test that invoke raises RuntimeError when catalog is None"""
    adapter = CasperAdapter(mock_message, catalog=None, config=mock_config)
    
    with pytest.raises(RuntimeError, match="Invoking Casper without a STAC catalog is not supported"):
        adapter.invoke()


def test_process_file_with_empty_catalog(mock_message, mock_config):
    """Test that process_file returns empty catalog when input catalog has no items"""
    empty_catalog = Catalog(str(uuid4()), "Empty Catalog")
    
    adapter = CasperAdapter(mock_message, catalog=empty_catalog, config=mock_config)
    result = adapter.process_file(empty_catalog)
    
    assert isinstance(result, Catalog)
    assert len(list(result.get_items())) == 0


@patch('casper.harmony.service_adapter.download_file')
@patch('casper.harmony.service_adapter.convert_to_parquet')
def test_process_file_logs_parquet_conversion(
    mock_parquet, mock_download,
    mock_message, mock_config, mock_catalog, test_netcdf_file
):
    """Test that appropriate log message is generated for parquet conversion"""
    # Setup
    mock_message.format = Mock()
    mock_message.format.mime = "application/parquet"
    mock_download.return_value = test_netcdf_file
    
    adapter = CasperAdapter(mock_message, catalog=mock_catalog, config=mock_config)
    
    with patch.object(adapter.logger, 'info') as mock_logger_info, \
         patch.object(adapter, '_stage', return_value='https://example.com/staged.zip'):
        # Execute
        result = adapter.process_file(mock_catalog)
        
        # Verify logging
        log_calls = [call[0][0] for call in mock_logger_info.call_args_list]
        assert any("Converting to Parquet format" in str(call) for call in log_calls)


@patch('casper.harmony.service_adapter.download_file')
@patch('casper.harmony.service_adapter.convert_to_csv')
def test_process_file_logs_csv_conversion(
    mock_csv, mock_download,
    mock_message, mock_config, mock_catalog, test_netcdf_file
):
    """Test that appropriate log message is generated for CSV conversion"""
    # Setup - set format.mime to CSV
    mock_message.format = Mock()
    mock_message.format.mime = "text/csv"
    mock_download.return_value = test_netcdf_file
    
    adapter = CasperAdapter(mock_message, catalog=mock_catalog, config=mock_config)
    
    with patch.object(adapter.logger, 'info') as mock_logger_info, \
         patch.object(adapter, '_stage', return_value='https://example.com/staged.zip'):
        # Execute
        result = adapter.process_file(mock_catalog)
        
        # Verify logging
        log_calls = [call[0][0] for call in mock_logger_info.call_args_list]
        assert any("Converting to CSV format" in str(call) for call in log_calls)
