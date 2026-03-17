# Copyright 2024 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration. All Rights Reserved.
#
# This software calls the following third-party software, which is subject to the terms and
# conditions of its licensor, as applicable.  Users must license their own copies;
# the links are provided for convenience only.
#
# Harmony-service-lib-py
# https://www.apache.org/licenses/LICENSE-2.0
# https://github.com/nasa/harmony-service-lib-py?tab=License-1-ov-file
#
# pystac
# https://github.com/stac-utils/pystac/blob/main/LICENSE
# https://www.apache.org/licenses/LICENSE-2.0
#
# Python Standard Library (version 3.10)
# https://docs.python.org/3/license.html#psf-license
#
# The Batchee: Granule batcher service to support concatenation platform is licensed under the
# Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4

from harmony_service_lib.adapter import BaseHarmonyAdapter
from harmony_service_lib.util import generate_output_filename, stage
from pystac import Catalog, Item
from pystac.item import Asset

from casper.convert_to_csv import convert_to_csv
from casper.convert_to_parquet import convert_to_parquet
from casper.harmony.download_worker import download_file
from casper.harmony.util import (
    _get_item_url,
    _get_output_date_range,
)


class CasperAdapter(BaseHarmonyAdapter):
    """
    A harmony-service-lib wrapper around the casper module.
    This wrapper does not support Harmony calls that do not have STAC catalogs
    as support for this behavior is being depreciated in harmony-service-lib
    """

    def __init__(self, message, catalog=None, config=None):
        """
        Constructs the adapter

        Parameters
        ----------
        message : harmony.Message
            The Harmony input which needs acting upon
        catalog : pystac.Catalog
            A STAC catalog containing the files on which to act
        config : harmony.util.Config
            The configuration values for this runtime environment.
        """
        super().__init__(message, catalog=catalog, config=config)

    def invoke(self):
        """
        Primary entrypoint into the service wrapper. Overrides BaseHarmonyAdapter.invoke
        """
        if not self.catalog:
            # Message-only support is being depreciated in Harmony, so we should expect to
            # only see requests with catalogs when invoked with a newer Harmony instance
            # https://github.com/nasa/harmony-service-lib-py/blob/21bcfbda17caf626fb14d2ac4f8673be9726b549/harmony/adapter.py#L71
            raise RuntimeError("Invoking Casper without a STAC catalog is not supported")

        return self.message, self.process_file(self.catalog)

    def process_file(self, catalog: Catalog) -> list[Catalog]:
        """Converts a list of STAC catalogs into a list of lists of STAC catalogs."""
        self.logger.info("process_catalog() started.")
        try:
            result = catalog.clone()
            result.id = str(uuid4())
            result.clear_children()

            # Get all the items from the catalog, including from child or linked catalogs
            items = list(self.get_all_catalog_items(catalog))

            # Just return if catalog contains no items
            if len(items) == 0:
                return result

            datetimes = _get_output_date_range(items)

            # # --- Get granule filepath (url) ---
            netcdf_url = _get_item_url(items[0])
            if netcdf_url is None:
                raise ValueError("No URL found for item")

            with TemporaryDirectory() as temp_dir:
                # Download file
                input_file = download_file(
                    netcdf_url, temp_dir, self.message.accessToken, self.config
                )

                # Base filename is the input filename without the file extension
                base_file_name = Path(input_file).stem

                # Create the subdirectory
                self.logger.info("Running Casper.")

                output_mime = self.message.format.mime
                output_format = 'csv' if 'csv' in output_mime else 'parquet'

                # --- Run Casper ---
                if output_format == 'parquet':
                    self.logger.info("Converting to Parquet format.")
                    # Create output directory for parquet files (no zip)
                    output_dir = Path(temp_dir) / base_file_name
                    convert_to_parquet(
                        input_file,
                        str(output_dir),
                        logger=self.logger,
                        create_zip=False,
                    )
                    # Stage all parquet files from the directory
                    staged_urls = self._stage_directory(output_dir, "application/parquet")
                else:
                    self.logger.info("Converting to CSV format.")
                    # Use Harmony generated filename for zip
                    zip_file = generate_output_filename(base_file_name, ext="zip", is_reformatted=True)
                    zip_file = Path(temp_dir) / zip_file
                    convert_to_csv(
                        input_file,
                        zip_file,
                        logger=self.logger,
                    )
                    staged_urls = [self._stage(zip_file, zip_file.name, "application/zip")]
            # -- Output to STAC catalog --
            result.clear_items()
            properties = {
                "start_datetime": datetimes["start_datetime"],
                "end_datetime": datetimes["end_datetime"],
            }
            item = Item(
                str(uuid4()),
                None,
                None,
                None,
                properties,
            )

            # Add assets for each staged file
            if output_format == 'parquet':
                # Multiple parquet files as separate assets
                for idx, staged_url in enumerate(staged_urls):
                    file_name = Path(staged_url).name
                    asset = Asset(
                        staged_url,
                        title=file_name,
                        media_type="application/parquet",
                        roles=["data"],
                    )
                    item.add_asset(f"data_{idx}", asset)
            else:
                # Single zip file
                staged_url = staged_urls[0]
                asset = Asset(
                    staged_url,
                    title=Path(staged_url).name,
                    media_type="application/zip",
                    roles=["data"],
                )
                item.add_asset("data", asset)
            
            result.add_item(item)

            self.logger.info("STAC catalog creation complete.")

            return result

        except Exception as service_exception:
            self.logger.error(service_exception, exc_info=1)
            raise service_exception

    def _stage(self, local_filename: str, remote_filename: str, mime: str) -> str:
        """
        Stages a local file to either to S3 (utilizing harmony.util.stage) or to
        the local filesystem by performing a file copy. Staging location is
        determined by message.stagingLocation or the --harmony-data-location
        CLI argument override

        Parameters
        ----------
        local_filename : string
            A path and filename to the local file that should be staged
        remote_filename : string
            The basename to give to the remote file
        mime : string
            The mime type to apply to the staged file for use when it is served, e.g. "application/x-netcdf4"

        Returns
        -------
        url : string
            A URL to the staged file
        """
        url_components = urlsplit(self.message.stagingLocation)
        scheme = url_components.scheme

        if scheme == "file":
            dest_path = Path(url_components.path).joinpath(remote_filename)
            self.logger.info("Staging to local filesystem: '%s'", str(dest_path))

            copyfile(local_filename, dest_path)
            return dest_path.as_uri()

        return stage(
            local_filename,
            remote_filename,
            mime,
            logger=self.logger,
            location=self.message.stagingLocation,
            cfg=self.config,
        )

    def _stage_directory(self, local_dir: Path, mime: str) -> list[str]:
        """
        Stages all files in a directory to either S3 or the local filesystem.
        
        Parameters
        ----------
        local_dir : Path
            The directory containing files to stage
        mime : string
            The mime type to apply to the staged files
        
        Returns
        -------
        list[str]
            A list of URLs to the staged files
        """
        staged_urls = []
        
        # Get all files in the directory (excluding subdirectories)
        files = [f for f in local_dir.iterdir() if f.is_file()]
        
        for file_path in sorted(files):
            staged_url = self._stage(str(file_path), file_path.name, mime)
            staged_urls.append(staged_url)
            
        return staged_urls
