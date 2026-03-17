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


def create_markdown(md, ds, input_filename):
    """Create markdown file contents"""
    header = f"# {len(md)} Parquet files created for {input_filename} based on dimensional schemas\n\n"
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


def convert_to_parquet(fname: str, output_path: str, logger: Logger = default_logger, create_zip: bool = True) -> int:
    """
    Converts NetCDF file to one or more Parquet files. The number of files will
    be based on the dimensions identified in the NetCDF file.

    Parameter
    ----------
    fname: str
        The name of the NetCDF file to be converted to Parquet file(s)
    output_path: str
        The path where output files will be written (zip file if create_zip=True, directory if False)
    logger: Logger
        Logger instance for output messages
    create_zip: bool
        Whether to create a zip file (default: True) or output individual files to a directory

    Returns
    -------
    int
        Number of Parquet files created
    """
    xr.set_options(use_new_combine_kwarg_defaults=True)
    num_parquet_files = 0
    schemas: dict[str | tuple[str, ...], list[str]] = {}
    md = {}
    json_obj: dict[str, str | dict] = {}
    json_obj["Notice"] = "The Readme.md file includes the same information"

    try:
        # Open file as xarray datatree
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

        if create_zip:
            # Create the zip file object in write mode
            with zipfile.ZipFile(
                output_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
            ) as zf:
                logger.info(f"Creating {len(vals)} Parquet files for {input_filename}")
                num_parquet_files = _write_parquet_files(
                    vals, data, input_filename, logger, zf=zf
                )
        else:
            # Create output directory if it doesn't exist
            output_dir = Path(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Creating {len(vals)} Parquet files for {input_filename}")
            num_parquet_files = _write_parquet_files(
                vals, data, input_filename, logger, output_dir=output_dir
            )

    except Exception as e:
        logger.error("File conversion failed: %s", e)
        raise

    return num_parquet_files


def _write_parquet_files(
    vals, data, input_filename, logger, zf=None, output_dir=None
) -> int:
    """Helper function to write parquet files either to a zip or directory"""
    import tempfile
    import os
    
    num_parquet_files = 0
    md = {}
    json_obj: dict[str, str | dict] = {}
    json_obj["Notice"] = "The Readme.md file includes the same information"

    for idx in range(len(vals)):
        dims, vvs = vals[idx]
        # Use Harmony generated filename
        op_file = f"{input_filename}-{idx}.parquet"
        op_file = generate_output_filename(op_file, ext="parquet", is_reformatted=True)
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

        # Convert to DataFrame and write to parquet
        df = ds.compute().to_dataframe().dropna(how="all", subset=vvs)

        if zf is not None:
            # Write parquet file to a temporary location, then add to zip
            with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                df.to_parquet(tmp.name, engine="pyarrow", compression="snappy")
                tmp.flush()
                zf.write(tmp.name, op_file)
                os.unlink(tmp.name)
            logger.info(f" {op_file} added to zip file")
        else:
            # Write parquet file directly to output directory
            output_file = output_dir / op_file
            df.to_parquet(output_file, engine="pyarrow", compression="snappy")
            logger.info(f" {op_file} created")

        del df
        num_parquet_files += 1

    # Create markdown and json Readme files
    readme_contents = create_markdown(md, data, input_filename)
    readme_file = "Readme.md"
    json_readme(data, input_filename, json_obj)
    json_file = "Readme.json"
    json_data = json.dumps(json_obj, indent=4)

    if zf is not None:
        # Add to zip file
        with zf.open(readme_file, "w") as file:
            file.write(readme_contents.encode("utf-8"))
        zf.writestr(json_file, json_data.encode("utf-8"))
    else:
        # Write to output directory
        (output_dir / readme_file).write_text(readme_contents)
        (output_dir / json_file).write_text(json_data)

    return num_parquet_files


def main():
    """Entry point for the casper command line tool."""
    logging.basicConfig(
        stream=sys.stdout,
        format="[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    if len(sys.argv) < 2:
        print("Must specify an input file")
        exit()

    input_file = sys.argv[1]

    """Parse arguments and run casper on specified input file."""
    if not valid_input_file(input_file):
        raise ValueError("Input filename not valid")

    if not valid_workable_file(input_file):
        raise ValueError("Input file not valid")
    zip_file_name = f"{input_file.split('/')[-1].split('.')[0]}.zip"

    convert_to_parquet(input_file, zip_file_name)


if __name__ == "__main__":
    main()
