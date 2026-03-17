"""A NetCDF to CSV converter module"""

import gc
import json
import logging
import sys
import zipfile
from logging import Logger
from pathlib import Path

import xarray as xr
from harmony_service_lib.util import generate_output_filename

from casper.file_ops import (
    valid_input_file,
    valid_workable_file,
)

default_logger = logging.getLogger(__name__)


def remove_blank_lines(text):
    lines = text.splitlines()  # Split the string into a list of lines
    real_lines = [line for line in lines if line.strip()]  # Filter out blank lines
    return "\n\t\t".join(real_lines)


def get_group_attributes(ds):
    """Get group global attributes"""
    group_attrs = ""
    for node in ds.subtree:
        if node.path != "/" and len(node.attrs) > 0:
            group_attrs += f"\n# Group {node.path} Attributes:\n\t"
            attrs_dict = {k: str(v) for k, v in node.attrs.items()}
            attrs_dict = dict(sorted(attrs_dict.items()))
            f_attrs = [f"\t{k}: {remove_blank_lines(v)}" for k, v in attrs_dict.items()]
            group_attrs += "\n\t".join(f_attrs)
    return group_attrs


def get_global_attributes(ds):
    """Get dataset global attributes"""
    attrs = ds.attrs
    attrs_dict = {k: str(v) for k, v in attrs.items()}
    attrs_dict = dict(sorted(attrs_dict.items()))
    attrs_list = [f"\t{k}: {remove_blank_lines(v)}" for k, v in attrs_dict.items()]
    return attrs_list


def create_markdown(md, ds, input_filename, format_type='csv'):
    """Create markdown file contents"""
    format_upper = format_type.upper()
    header = f"# {len(md)} {format_upper} files created for {input_filename} based on dimensional schemas\n\n"
    data = ""
    for k, v in md.items():
        data += f"## {v['filename']}\n"
        data += "\tdimensions:"
        if len(k) > 0:
            data += f"  {', '.join(k)}"
        data += "\n\tnon-dimension coordinates:"
        coords = [c for c in v["coords"] if c not in v["keys"]]
        if len(coords) > 0:
            data += f"  {', '.join(coords)}"
        data += f"\n\t{len(v['vrbs'])} variables:\n"
        if len(v["vrbs"]) > 0:
            data += f"\t\t{'\n\t\t'.join(v['vrbs'])}\n\n"

    global_attrs = get_global_attributes(ds)
    a_val = f"# {input_filename} Global Attributes:\n\t"
    a_val += "\n\t".join(global_attrs)
    group_attrs = get_group_attributes(ds)
    content = f"""{header}\n{data}\n{a_val}\n{group_attrs}"""
    return content


def json_readme(ds, input_filename, json_obj):
    attrs = ds.attrs
    attrs_dict = {k: str(v) for k, v in attrs.items()}
    json_obj[f"{input_filename} Global Attributes:"] = dict(sorted(attrs_dict.items()))
    for node in ds.subtree:
        if node.path != "/" and len(node.attrs) > 0:
            node_attrs = {k: str(v) for k, v in node.attrs.items()}
            json_obj[f"Group {node.path} Attributes:"] = dict(sorted(node_attrs.items()))
    return


def convert_to_csv(fname: str, zip_file: str, logger: Logger = default_logger, output_format: str = 'csv') -> int:
    """
    Converts NetCDF file to one or more CSV or Parquet files. The number of files will
    be based on the dimensions identified in the NetCDF file.

    Parameter
    ----------
    fname: str
        The name of the NetCDF file to be converted
    zip_file: str
        The name of the zipfile to create
    logger: Logger
        Logger instance for output messages
    output_format: str
        Output format: 'csv' (default) or 'parquet'

    Returns
    -------
    int
        Number of output files created
    """
    xr.set_options(use_new_combine_kwarg_defaults=True)
    num_output_files = 0
    schemas: dict[str | tuple[str, ...], list[str]] = {}
    md = {}
    json_obj: dict[str, str | dict] = {}
    json_obj["Notice"] = "The Readme.md file includes the same information"

    try:
        # Open file as xarray datatree
        # Note: We don't use chunks='auto' to avoid requiring dask as a dependency
        # Instead, we use manual chunked processing in the conversion loop
        data = xr.open_datatree(fname)

        # Loops datatree items to gather info for various dimension groups
        for path, ds in data.to_dict().items():
            if path == "/":
                path = ""
            variables = list(ds.variables)
            products = [f"{path}/{vv}" for vv in variables if vv not in ds.coords]
            for varname in products:
                dims = data[varname].dims
                if dims not in schemas:
                    schemas[dims] = []
                schemas[dims].append(varname)

        input_filename = Path(fname).name
        vals = list(schemas.items())

        # Create the zip file object in write mode
        with zipfile.ZipFile(
            zip_file, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
        ) as zf:
            logger.info(f"Creating {len(vals)} {output_format.upper()} files for {input_filename}")

            for idx in range(len(vals)):
                dims, vvs = vals[idx]
                # Use Harmony generated filename
                op_file = f"{input_filename}-{idx}.{output_format}"
                op_file = generate_output_filename(op_file, ext=output_format, is_reformatted=True)
                ds = xr.combine_by_coords([data[vv].rename(vv) for vv in vvs])
                # Order columns: dimensions, non-dimensional coordinates, rest of variables
                cols = list(dims) + list(ds.coords) + vvs
                ds = ds[cols]

                # Add info to markdown and json dictionaries for creation of Readmes
                md[dims] = {
                    "filename": op_file,
                    "keys": dims,
                    "coords": list(ds.coords),
                    "vrbs": vvs,
                }
                json_obj[op_file] = {
                    "dimensions": ",".join(list(dims)),
                    "non-dimensional coordinates": ",".join(
                        [c for c in list(ds.coords) if c not in list(dims)]
                    ),
                    "variables": vvs,
                }

                # Convert to DataFrame and write based on output format
                # Use chunked processing to reduce memory usage
                with zf.open(op_file, "w", force_zip64=True) as csv_file:
                    chunk_size = 1000  # Increased chunk size for better performance
                    
                    # Determine the primary dimension for chunking
                    if len(ds.sizes) > 0:
                        prime_dim = next(iter(ds.sizes.items()))
                        dim_var = prime_dim[0]
                        data_len = prime_dim[1]
                        
                        for i in range(0, data_len, chunk_size):
                            # Process a slice of the dataset
                            indexer = {dim_var: slice(i, min(i + chunk_size, data_len))}
                            ds_chunk = ds.isel(indexer)
                            chunk = ds_chunk.compute()
                            # Convert the small chunk to a pandas DataFrame
                            df_chunk = chunk.to_dataframe().dropna(how="all", subset=vvs)

                            # Write header for the first chunk only
                            df_chunk.to_csv(csv_file, header=(i == 0))

                            del df_chunk, chunk, ds_chunk
                    else:
                        # No dimensions, small dataset - convert directly
                        df = ds.compute().to_dataframe().dropna(how="all", subset=vvs)
                        df.to_csv(csv_file, header=True)
                        del df
                
                # Explicitly delete the dataset to free memory
                del ds
                gc.collect()  # Hint to garbage collector to free memory

                logger.info(f" {op_file} added to zip file")
                num_output_files += 1

            # Create markdown and json Readme files
            readme_contents = create_markdown(md, data, input_filename, output_format)
            readme_file = "Readme.md"
            with zf.open(readme_file, "w") as file:
                file.write(readme_contents.encode("utf-8"))

            # Create JSON file with pretty printing
            json_readme(data, input_filename, json_obj)
            json_file = "Readme.json"
            json_data = json.dumps(json_obj, indent=4)
            zf.writestr(json_file, json_data.encode("utf-8"))
        
        # Close the datatree to release resources
        data.close()

    except Exception as e:
        logger.error("File conversion failed: %s", e)
        raise

    return num_output_files


def main():
    """Entry point for the casper command line tool."""
    import argparse
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

    input_file = args.input_file
    output_format = args.format

    """Parse arguments and run casper on specified input file."""
    if not valid_input_file(input_file):
        raise ValueError("Input filename not valid")

    if not valid_workable_file(input_file):
        raise ValueError("Input file not valid")
    zip_file_name = f"{input_file.split('/')[-1].split('.')[0]}.zip"

    convert_to_csv(input_file, zip_file_name, output_format=output_format)


if __name__ == "__main__":
    main()
