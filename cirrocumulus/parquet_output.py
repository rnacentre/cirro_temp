import os
import logging

import numpy as np
import pyarrow as pa
import scipy.sparse
import pyarrow.parquet as pq

from cirrocumulus.util import dumps


logger = logging.getLogger("cirro")


def write_pq(d, output_dir, name, filesystem, write_statistics=True, row_group_size=None):
    filesystem.makedirs(output_dir, exist_ok=True)
    pq.write_table(
        pa.Table.from_pydict(d),
        os.path.join(output_dir, name + ".parquet"),
        write_statistics=write_statistics,
        row_group_size=row_group_size,
        filesystem=filesystem,
    )


def save_dataset_pq(dataset, schema, output_directory, filesystem, whitelist):
    X_dir = os.path.join(output_directory, "X")
    obs_dir = os.path.join(output_directory, "obs")
    obsm_dir = os.path.join(output_directory, "obsm")
    filesystem.makedirs(X_dir, exist_ok=True)
    filesystem.makedirs(obs_dir, exist_ok=True)
    filesystem.makedirs(obsm_dir, exist_ok=True)

    with filesystem.open(
        os.path.join(output_directory, "index.json.gz"), "wt", compression="gzip"
    ) as f:
        f.write(dumps(schema, double_precision=2, orient="values"))
        if whitelist["x"]:
            save_adata_X(dataset, X_dir, filesystem, whitelist=whitelist["x_keys"])
            for layer in dataset.layers.keys():
                layer_dir = os.path.join(output_directory, "layers", layer)
                filesystem.makedirs(layer_dir, exist_ok=True)
                save_adata_X(dataset, layer_dir, filesystem, layer, whitelist=whitelist["x_keys"])
        if whitelist["obs"]:
            save_data_obs(dataset, obs_dir, filesystem, whitelist=whitelist["obs_keys"])
        if whitelist["obsm"]:
            save_data_obsm(dataset, obsm_dir, filesystem, whitelist=whitelist["obsm_keys"])


def save_adata_X(adata, X_dir, filesystem, layer=None, whitelist=None):
    adata_X = adata.X if layer is None else adata.layers[layer]
    names = adata.var.index
    is_sparse = scipy.sparse.issparse(adata_X)
    output_dir = X_dir
    for j in range(adata_X.shape[1]):
        filename = names[j]
        if whitelist is None or filename in whitelist:
            X = adata_X[:, j]
            if is_sparse:
                X = X.toarray().flatten()

            if is_sparse:
                indices = np.where(X != 0)[0]
                values = X[indices]
                write_pq(dict(index=indices, value=values), output_dir, filename, filesystem)
            else:
                write_pq(dict(value=X), output_dir, filename, filesystem)
            if j > 0 and (j + 1) % 1000 == 0:
                logger.info("Wrote adata X {}/{}".format(j + 1, adata_X.shape[1]))


def save_data_obsm(adata, obsm_dir, filesystem, whitelist):
    logger.info("writing adata obsm")

    for name in adata.obsm.keys():
        if whitelist is None or name in whitelist:
            m = adata.obsm[name]
            dim = m.shape[1]
            d = {}
            for i in range(dim):
                d[name + "_" + str(i + 1)] = m[:, i].astype("float32")
            write_pq(d, obsm_dir, name, filesystem)


def save_data_obs(adata, obs_dir, filesystem, whitelist=None):
    logger.info("writing adata obs")
    for name in adata.obs:
        if whitelist is None or name in whitelist:
            value = adata.obs[name]
            write_pq(dict(value=value), obs_dir, name, filesystem)
    write_pq(dict(value=adata.obs.index.values), obs_dir, "index", filesystem)
