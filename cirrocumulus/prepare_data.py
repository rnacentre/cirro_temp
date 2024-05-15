import os
import logging
import argparse

import h5py
import numpy as np
import pandas as pd
import anndata
import scipy.sparse
from pandas import CategoricalDtype

from cirrocumulus.anndata_dataset import read_adata
from cirrocumulus.anndata_util import dataset_schema, get_scanpy_marker_keys
from cirrocumulus.io_util import SPATIAL_HELP, filter_markers, get_markers, unique_id
from cirrocumulus.util import get_fs, open_file, to_json


logger = logging.getLogger("cirro")

CLUSTER_FIELDS = ["anno", "cell_type", "celltype", "leiden", "louvain", "seurat_cluster", "cluster"]


def add_obs_to_h5ad(h5ad_path: str, obs: pd.DataFrame):
    with h5py.File(h5ad_path, "r+") as f:
        existing_obs = anndata.experimental.read_elem(f["obs"])
        for c in obs.columns:
            if c in existing_obs.columns:
                del existing_obs[c]
        existing_obs = existing_obs.join(obs)
        anndata.experimental.write_elem(f, "obs", existing_obs)


def whitelist_todict(whitelist):
    save_x = True
    save_obs = True
    save_obsm = True
    x_keys = []
    obs_keys = []
    obsm_keys = []
    if whitelist is not None:
        whitelist = set(whitelist)
        save_x = "X" in whitelist
        save_obs = "obs" in whitelist
        save_obsm = "obsm" in whitelist
        [whitelist.remove(field) for field in ["X", "obs", "obsm"] if field in whitelist]
        for key in whitelist:
            dot_index = key.index(".")
            prefix = key[:dot_index].lower()
            suffix = key[dot_index + 1 :]
            if prefix == "x":
                x_keys.append(suffix)
            elif prefix == "obs":
                obs_keys.append(suffix)
            elif prefix == "obsm":
                obsm_keys.append(suffix)
        save_x = save_x or len(x_keys) > 0
        save_obs = save_obs or len(obs_keys) > 0
        save_obsm = save_obsm or len(obsm_keys) > 0

    return {
        "x": save_x,
        "obs": save_obs,
        "obsm": save_obsm,
        "x_keys": x_keys if len(x_keys) > 0 else None,
        "obs_keys": obs_keys if len(obs_keys) > 0 else None,
        "obsm_keys": obsm_keys if len(obsm_keys) > 0 else None,
    }


class PrepareData:
    def __init__(
        self,
        datasets,
        output,
        dimensions=None,
        groups=[],
        group_nfeatures=10,
        markers=[],
        output_format="zarr",
        no_auto_groups=False,
        save_whitelist=None,
    ):
        self.groups = groups
        self.group_nfeatures = group_nfeatures
        self.markers = markers
        self.output_format = output_format
        self.no_auto_groups = no_auto_groups
        if save_whitelist is None:
            save_whitelist = whitelist_todict(None)
        self.save_whitelist = save_whitelist
        for dataset in datasets:
            for key in list(dataset.obsm.keys()):
                m = dataset.obsm[key]
                dim = m.shape[1]
                if not (1 < dim <= 3):
                    del dataset.obsm[key]
        if len(datasets) > 1:
            for i in range(len(datasets)):
                dataset = datasets[i]
                if "group" not in dataset.var:
                    dataset.var["group"] = dataset.uns.get("name", "dataset {}".format(i + 1))
                if i > 0 and not np.array_equal(datasets[0].obs.index, dataset.obs.index):
                    raise ValueError("obs ids are not equal")
            dataset = anndata.concat(datasets, axis=1, label="group", merge="unique")
        else:
            dataset = datasets[0]
        dataset.var.index = dataset.var.index.str.replace("/", "_")
        dataset.var_names_make_unique()
        dataset.obs.index.name = "id"
        dataset.var.index.name = "id"
        self.base_output = output
        dimensions_supplied = dimensions is not None and len(dimensions) > 0
        self.dimensions = [] if not dimensions_supplied else dimensions
        self.measures = []
        self.others = []
        self.dataset = dataset
        if save_whitelist["x"]:
            if scipy.sparse.issparse(dataset.X) and not scipy.sparse.isspmatrix_csc(dataset.X):
                dataset.X = dataset.X.tocsc()
            for layer_name in dataset.layers.keys():
                X = dataset.layers[layer_name]
                if scipy.sparse.issparse(X) and not scipy.sparse.isspmatrix_csc(X):
                    dataset.layers[layer_name] = X.tocsc()

        for i in range(len(dataset.obs.columns)):
            name = dataset.obs.columns[i]
            c = dataset.obs[name]
            if pd.api.types.is_object_dtype(c):
                dataset.obs[name] = dataset.obs[name].astype("category")
                c = dataset.obs[name]
            if not dimensions_supplied and isinstance(c.dtype, CategoricalDtype):
                if 1 < len(c.cat.categories) < 2000:
                    self.dimensions.append(name)
                    if c.isna().sum() > 0:
                        logger.info("Replacing nans in {}".format(name))
                        dataset.obs[name] = dataset.obs[name].astype(str)
                        dataset.obs.loc[dataset.obs[name].isna(), name] = ""
                        dataset.obs[name] = dataset.obs[name].astype("category")
                else:
                    self.others.append(name)
            elif not pd.api.types.is_string_dtype(c) and not pd.api.types.is_object_dtype(c):
                self.measures.append("obs/" + name)
            else:
                self.others.append(name)

    def execute(self):
        output_format = self.output_format
        dataset = self.dataset
        if self.groups is None and not self.no_auto_groups:
            groups = []
            existing_fields = set()
            scanpy_marker_keys = get_scanpy_marker_keys(dataset)
            for key in scanpy_marker_keys:
                group_by = dataset.uns[key]["params"]["groupby"]
                if isinstance(group_by, np.ndarray):
                    group_by = ",".join(group_by)
                existing_fields.add(group_by)
            for field in dataset.obs.columns:
                field_lc = field.lower()
                for cluster_field in CLUSTER_FIELDS:
                    if field_lc.find(cluster_field) != -1 and cluster_field not in existing_fields:
                        groups.append(field)
                        break

            self.groups = groups
        if self.save_whitelist["x"] and self.groups is not None and len(self.groups) > 0:
            use_pegasus = False
            use_scanpy = False
            try:
                import pegasus as pg

                use_pegasus = True
            except ModuleNotFoundError:
                pass
            if not use_pegasus:
                try:
                    import scanpy as sc

                    use_scanpy = True
                    if "log1p" not in dataset.uns:
                        dataset.uns["log1p"] = {}
                    if "base" not in dataset.uns["log1p"]:
                        dataset.uns["log1p"]["base"] = None
                except ModuleNotFoundError:
                    pass
            if not use_pegasus and not use_scanpy:
                raise ValueError("Please install pegasuspy or scanpy to compute markers")
            first_time = True

            for group in self.groups:
                field = group
                if group not in dataset.obs:  # test if multiple comma separated fields
                    split_groups = group.split(",")
                    if len(split_groups) > 1:
                        use_split_groups = True
                        for split_group in split_groups:
                            if split_group not in dataset.obs:
                                use_split_groups = False
                                break
                        if use_split_groups:
                            dataset.obs[field] = dataset.obs[split_groups[0]].str.cat(
                                dataset.obs[split_groups[1:]], sep=","
                            )

                if field in dataset.obs:
                    if not isinstance(dataset.obs[field].dtype, CategoricalDtype):
                        dataset.obs[field] = dataset.obs[field].astype(str).astype("category")
                    if len(dataset.obs[field].cat.categories) > 1:
                        key_added = "rank_genes_" + str(field)
                        value_counts = dataset.obs[field].value_counts()
                        filtered_value_counts = value_counts[value_counts >= 3]
                        if len(filtered_value_counts) >= 2:
                            if first_time:
                                logger.info(
                                    "Using {} to compute markers".format(
                                        "pegasuspy" if use_pegasus else "scanpy"
                                    )
                                )
                                first_time = False
                            logger.info("Computing markers for {}".format(field))
                            if use_pegasus:
                                pg.de_analysis(
                                    dataset,
                                    cluster=field,
                                    de_key=key_added,
                                    subset=filtered_value_counts.index.to_list(),
                                )
                            else:
                                sc.tl.rank_genes_groups(
                                    dataset,
                                    field,
                                    key_added=key_added,
                                    method="t-test",
                                    groups=filtered_value_counts.index.to_list(),
                                )
                else:
                    raise ValueError(group + " not found in " + ", ".join(dataset.obs.columns))
        schema = self.get_schema()
        schema["format"] = output_format
        if output_format in ["parquet", "zarr"]:
            output_dir = self.base_output
        else:
            output_dir = os.path.splitext(self.base_output)[0]
        filesystem = get_fs(output_dir)
        filesystem.makedirs(output_dir, exist_ok=True)
        results = schema.get("results", [])

        if len(results) > 0:
            uns_dir = os.path.join(output_dir, "uns")
            is_gzip = output_format != "jsonl"
            filesystem.makedirs(uns_dir, exist_ok=True)

            for i in range(len(results)):
                full_result = results[i]
                result_id = full_result.pop("id")
                # keep id, name, type in schema, store rest externally
                results[i] = dict(
                    id=result_id,
                    name=full_result.pop("name"),
                    type=full_result.pop("type"),
                    content_type="application/json",
                    content_encoding="gzip" if is_gzip else None,
                )
                json_result = to_json(full_result)

                result_path = (
                    os.path.join(uns_dir, result_id + ".json.gz")
                    if is_gzip
                    else os.path.join(uns_dir, result_id + ".json")
                )
                with open_file(result_path, "wt", compression="gzip" if is_gzip else None) as out:
                    out.write(json_result)
        images = dataset.uns.pop("images", None)
        if images is not None:
            image_dir = os.path.join(output_dir, "images")
            filesystem.makedirs(image_dir, exist_ok=True)
            for image in images:
                src = image["image"]
                dest = os.path.join(image_dir, os.path.basename(src))
                filesystem.copy(src, dest)
                image["image"] = "images/" + os.path.basename(src)

        if output_format == "parquet":
            from cirrocumulus.parquet_output import save_dataset_pq

            save_dataset_pq(dataset, schema, self.base_output, filesystem, self.save_whitelist)
        elif output_format == "jsonl":
            from cirrocumulus.jsonl_io import save_dataset_jsonl

            save_dataset_jsonl(dataset, schema, output_dir, self.base_output, filesystem)
        elif output_format == "zarr":
            from cirrocumulus.zarr_output import save_dataset_zarr

            save_dataset_zarr(dataset, schema, self.base_output, filesystem, self.save_whitelist)
        else:
            raise ValueError("Unknown format")

    def get_schema(self):
        result = dataset_schema(self.dataset, n_features=self.group_nfeatures)
        markers = result.get("markers", [])

        if self.markers is not None:  # add results specified from file
            markers += get_markers(self.markers)
            markers = filter_markers(self.dataset, markers)

        for marker in markers:
            if marker.get("id") is None:
                marker["id"] = unique_id()
            marker["readonly"] = True
        result["markers"] = markers
        result["format"] = self.output_format
        return result


def create_parser(description=False):
    parser = argparse.ArgumentParser(
        description="Prepare a dataset for cirrocumulus server" if description else None
    )
    parser.add_argument("dataset", help="Path to a h5ad, loom, or Seurat (rds) file", nargs="+")
    parser.add_argument("--out", help="Path to output directory")
    parser.add_argument(
        "--format", help="Output format", choices=["parquet", "jsonl", "zarr"], default="zarr"
    )
    parser.add_argument(
        "--whitelist",
        help="Optional whitelist of fields to save when output format is parquet or zarr. Use obs, obsm, or X to save all entries for these fields. Use field.name to save a specific entry (e.g. obs.leiden)",
        action="append",
    )
    parser.add_argument(
        "--markers",
        help='Path to JSON file of precomputed markers that maps name to features. For example {"a":["gene1", "gene2"], "b":["gene3"]',
        action="append",
    )
    parser.add_argument(
        "--no-auto-groups",
        dest="no_auto_groups",
        help="Disable automatic cluster field detection to compute differential expression results for",
        action="store_true",
    )
    parser.add_argument(
        "--groups",
        help='List of groups to compute markers for (e.g. louvain). Markers created with cumulus/scanpy are automatically included. Separate multiple groups with a comma to combine groups using "AND" logic (e.g. louvain,day)',
        action="append",
    )
    parser.add_argument(
        "--group_nfeatures", help="Number of marker genes/features to include", type=int, default=10
    )
    parser.add_argument("--spatial", help=SPATIAL_HELP)
    return parser


def main(argsv):
    args = create_parser(True).parse_args(argsv)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    out = args.out
    no_auto_groups = args.no_auto_groups
    save_whitelist = args.whitelist

    input_datasets = args.dataset  # multimodal
    output_format = args.format
    if out is None:
        out = os.path.splitext(os.path.basename(input_datasets[0]))[0]
    out = out.rstrip("/")
    output_format2extension = dict(parquet=".cpq", jsonl=".jsonl", zarr=".zarr", h5ad=".h5ad")
    if not out.lower().endswith(output_format2extension[output_format]):
        out += output_format2extension[output_format]
    save_whitelist = whitelist_todict(save_whitelist)
    datasets = []
    for input_dataset in input_datasets:
        filesystem = get_fs(input_dataset)
        adata = read_adata(
            input_dataset,
            filesystem,
            spatial_directory=args.spatial,
            use_raw=False,
            backed=not save_whitelist["x"],
        )
        datasets.append(adata)
        adata.uns["name"] = os.path.splitext(
            os.path.basename(input_dataset.rstrip(filesystem.sep))
        )[0]

    prepare_data = PrepareData(
        datasets=datasets,
        output=out,
        dimensions=args.groups,
        groups=args.groups,
        group_nfeatures=args.group_nfeatures,
        markers=args.markers,
        output_format=output_format,
        no_auto_groups=no_auto_groups,
        save_whitelist=save_whitelist,
    )
    prepare_data.execute()


if __name__ == "__main__":
    import sys

    main(sys.argv)
