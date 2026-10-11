# thetis-regional-mesh-generation

Generate regional-scale unstructured meshes for the **Thetis** coastal ocean model using QGIS-derived shapefiles plus
**qmesh/qmesh3** to produce **Gmsh** `.geo/.fld` inputs, then run **gmsh** to create a `.msh` mesh and optionally convert
it to a shapefile for visualisation in QGIS. The included configuration focuses on the Pentland Firth and Orkney waters,
but the mesh configuration and GIS inputs can be adapted for any region.

This repository contains:
- **Python scripts** to build mesh metric rasters and Gmsh input files
- A curated `shapefiles/` directory containing domain outlines, resolution outlines, and refinement regions

---

## Project layout (high level)

- `mesh_generation.py` — main workflow: build `.geo/.fld`, optionally reuse `.nc` rasters, run `gmsh`, then export a mesh shapefile
- `msh_to_shp.py` — standalone utility to convert an existing Gmsh mesh to a shapefile
- `input_params.py` — configuration for the overall domain + nested higher-resolution inner domains
- `shapefiles/` — input GIS layers (outlines, resolution outlines, refinement regions, plus some base files)

---

## Requirements

### Python

A virtual environment is required. From the repository root, create and activate one named
`qmesh-venv`, then pin `setuptools` below version 81 before installing qmesh:

```bash
python3 -m venv qmesh-venv
source qmesh-venv/bin/activate
python -m pip install "setuptools<81"
```

There are two options for installing and running qmesh:

#### qmesh3

Install qmesh3 following its [installation instructions](https://github.com/qmesh3/qmesh3/tree/master).
Install `gmsh` separately and ensure the `gmsh` executable is on your `PATH`.

#### qmeshcontainers and Docker

```bash
python -m pip install qmeshcontainers
```

Once `qmeshcontainers` is installed, grant your user access to Docker:

```bash
sudo groupadd docker
sudo usermod -aG docker "$USER"
```

Log out and back in for the new group membership to take effect, then verify Docker:

```bash
docker run hello-world
```

---

## Input data (shapefiles)

All paths in `input_params.py` are **relative to the `shapefiles/` directory** (the main script does `os.chdir("shapefiles")`).

Important subfolders:
- `shapefiles/outlines/` — outer boundary shapefiles for the mesh domain
- `shapefiles/resolution_outlines/` — polygons/lines used to drive resolution in different areas (e.g. mainland/islands)
- `shapefiles/refinement_regions/` — extra refinement regions (usually polygons for a specific area of interest)
- `shapefiles/base_files/` — source shapefiles used to build/maintain the above

---

## Configuring the mesh

Mesh configuration lives in `input_params.py`.

Conceptually:
- `overall_domain` describes the broad domain outline + resolution controls
- `inner_domains` is a list of nested, higher-resolution domains whose `.fld` fields are inserted into the overall `.geo`

Key configuration fields (per domain):
- `name`: base name used for generated `.geo`, `.fld`, and `.nc`
- `outline`: outline shapefile used as the domain boundary
- `resolution_entries`: ordered reusable entries, each defining a shapefile and the gradation parameters passed to qmesh
- `raster_bounds` and `raster_resolution`: shared raster extent and pixel resolution for every resolution shapefile in that domain
- `raster_file`: set to an existing `.nc` to reuse a previously generated raster
- `meshed_plots` / `meshed_plots_ids`: optional subdomains to embed with specific physical IDs

---

## Running mesh generation

From the repository root, with `qmesh3`:

```bash
source qmesh-venv/bin/activate
python mesh_generation.py
```

or with `qmeshcontainers`:

```bash
source qmesh-venv/bin/activate
qmeshcontainer -mwd
cd <PATH_TO_REPO>
python mesh_generation.py
```

`qmeshcontainer -mwd` starts in the parent directory, so change back to the repository directory inside the container before running the script.

Inside `mesh_generation.py` you can control:
- `qmesh_version` (`"qmesh3"` or `"qmeshcontainers"`)
- `new_fld_files` (generate fresh `.geo/.fld`)
- `load_existing_raster` (reuse existing `.nc` rasters instead of regenerating)

### Outputs

Running `mesh_generation.py` typically produces (names depend on your config):
- One or more metric rasters: `*.nc` (e.g. `overall_domain.nc`, `PFmesh.nc`, `FoWmesh.nc`)
- Gmsh inputs: `*.geo` and `*.fld`
- Final mesh: `<meshname>.msh`
- Generation log: `<meshname>.log`
- Visualisation shapefile for the mesh (written by qmesh)

Note: the `.geo/.fld/.nc/.msh/.log` files are written inside the `shapefiles/` directory because the script changes into that folder.

### Converting an existing mesh

To create QGIS-friendly shapefile output from an existing mesh without regenerating it:

```bash
python msh_to_shp.py shapefiles/OrkneysAdjoint-v0.msh
```

Use `--qmesh-version qmesh3` when using qmesh3, or `--coordinate-system` to override the default `EPSG:32630` mesh CRS.

---

## Troubleshooting

- **Missing `.shx` / `.dbf` / `.prj`**: a shapefile is a *set* of files. Ensure all components are present.
- **Projection/CRS issues**: the input shapefiles are in `EPSG:4326`, while generated mesh files use `EPSG:32630`. The raster bounds in `input_params.py` must use the input shapefiles' coordinates, and gradation distances are in the target CRS's metres.

---

## Notes

This repository focuses on mesh *generation inputs* and mesh creation for downstream hydrodynamic modelling. If you need the
mesh in a particular format or with additional physical region tagging, say what solver/workflow you’re targeting and we
can adjust the export steps accordingly.
