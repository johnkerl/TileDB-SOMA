import anndata
import tiledb
import tiledbsc

import pytest
import tempfile
import os
from pathlib import Path

HERE = Path(__file__).parent

@pytest.fixture
def h5ad_file(request):
    # pbmc-small is faster for automated unit-test / CI runs.
    #input_path = HERE.parent / "anndata/pbmc3k_processed.h5ad"
    input_path = HERE.parent / "anndata/pbmc-small.h5ad"
    return input_path

@pytest.fixture
def adata(h5ad_file):
    return anndata.read_h5ad(h5ad_file)

def test_import_anndata(adata):

    # Set up anndata input path and tiledb-group output path
    tempdir = tempfile.TemporaryDirectory()
    output_path = tempdir.name

    orig = adata

    # Ingest
    soma = tiledbsc.SOMA(output_path, verbose=True)
    soma.from_anndata(orig)

    # Structure:
    #   X/data
    #   X/raw
    #   obs
    #   var
    #   obsm/X_pca
    #   obsm/X_tsne
    #   obsm/X_umap
    #   obsm/X_draw_graph_fr
    #   varm/PCs
    #   obsp/distances
    #   obsp/connectivities

    # Check X/data (dense)
    with tiledb.open(os.path.join(output_path, 'X', 'data')) as A:
        df = A[:]
        keys = list(df.keys())
        assert keys == ['value', 'obs_id', 'var_id']
        assert A.ndim == 2

    # Check X/raw (sparse)
    with tiledb.open(os.path.join(output_path, 'X', 'raw')) as A:
        df = A.df[:]
        assert df.columns.to_list() == ['obs_id', 'var_id', 'value']
        # verify sparsity of raw data
        assert df.shape[0] == orig.raw.X.nnz

    # Check obs
    with tiledb.open(os.path.join(output_path, 'obs')) as A:
        df = A.df[:]
        assert df.columns.to_list() == orig.obs_keys()

    # Check var
    with tiledb.open(os.path.join(output_path, 'var')) as A:
        df = A.df[:]
        assert df.columns.to_list() == orig.var_keys()

    # Check some annotation matrices
    # Note: pbmc3k_processed doesn't have varp.
    for key in orig.obsm_keys():
        with tiledb.open(os.path.join(output_path, 'obsm', key)) as A:
            df = A.df[:]
            assert df.shape[0] == orig.obsm[key].shape[0]

    for key in orig.varm_keys():
        with tiledb.open(os.path.join(output_path, 'varm', key)) as A:
            df = A.df[:]
            assert df.shape[0] == orig.varm[key].shape[0]

    for key in list(orig.obsp.keys()):
        with tiledb.open(os.path.join(output_path, 'obsp', key)) as A:
            df = A.df[:]
            assert df.columns.to_list() == ["obs_id_i", "obs_id_j", "value"]
            assert df.shape[0] == orig.obsp[key].nnz

    tempdir.cleanup()