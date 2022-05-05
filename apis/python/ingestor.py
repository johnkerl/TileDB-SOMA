#!/usr/bin/env python

# ================================================================
# A simple driver for ingestion of anndata to a TileDB group.
#
# * Invoke this with one argument /path/to/some/somename.h5ad:
#   o Output will be ./tiledb-data/somename
#
# * Invoke this with two arguments to specify input anndata HDF5 file
#   and output TileDB group.
#
# Nominal immediate-term support is to local disk, although output to tiledb:/...
# URIs will be supported.
#
# Note this removes and recreates the destination TileDB group on each invocation.
# ================================================================

import tiledbsc
import sys, os, shutil
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Ingest soma data from anndata/h5ad into TileDB group structure"
    )
    parser.add_argument("-q", "--quiet", help="decrease output verbosity", action="store_true")
    parser.add_argument(
        "paths",
        type=str,
        help="One for specified input with default output path, or two to specify input and output paths",
        nargs='+'
    )
    args = parser.parse_args()

    if len(args.paths) == 1:
        input_path  = args.paths[0]
        # Example 'anndata/pbmc3k_processed.h5ad' -> 'tiledb-data/pbmc3k_processed'
        output_path = 'tiledb-data/' + os.path.splitext(os.path.basename(input_path))[0]
    elif len(args.paths) == 2:
        input_path  = args.paths[0]
        output_path = args.paths[1]
    else:
        parser.print_help(file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(input_path):
        # Print this neatly and exit neatly, to avoid a multi-line stack trace otherwise.
        print(f"Input path not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # This is for local-disk use only -- for S3-backed tiledb://... URIs we should
    # use tiledb.vfs to remove any priors, and/or make use of a tiledb `overwrite` flag.
    if not os.path.exists('tiledb-data'):
        os.mkdir('tiledb-data')
    if os.path.exists(output_path):
        shutil.rmtree(output_path) # Overwrite

    verbose = not args.quiet

    soma = tiledbsc.SOMA(output_path, verbose=verbose)
    soma.from_h5ad(input_path)

    if not verbose:
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()