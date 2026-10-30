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

- `mesh_generation.py` — reusable main workflow: generate inputs, run Gmsh, and export a mesh shapefile using `input_params.py`
- `input_params.py` — region-specific mesh domains and complete generation settings
- `qmesh_tools.py` — shared qmesh/qmeshcontainers selection and initialisation helper
- `msh_to_shp.py` — standalone utility to convert an existing Gmsh mesh to a shapefile
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

All GIS paths in `input_params.py` are **relative to
`generation_config.shapefiles_directory`**. The included configuration sets
this to `shapefiles/`; `mesh_generation.py` changes to that directory before
reading the inputs and writing generated files.

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

`generation_config` contains settings shared by the complete run: output
`meshname`, `shapefiles_directory`, target CRS, qmesh installation,
whether to generate `.geo`/`.fld` files or reuse existing rasters, and the
physical-ID, field, and topology-processing values used by qmesh and Gmsh.
To use another region, replace `input_params.py` and its referenced
shapefiles; the reusable `mesh_generation.py` runner requires no
region-specific edits.

`nested_raster_outside_value` is the Gmsh mesh-size value assigned outside
each nested raster's extent. It must be larger than every intended mesh size
so Gmsh's minimum field ignores the nested raster outside its domain.

### Domain and refinement guidance

- **Meshed plots must be line strings**, not polygons. Define a meshed plot in the overall domain and in every inner domain that must contain that subdomain; otherwise it will not appear in the final mesh.
- **Check each inner domain on its own** before inserting it into the overall domain. This makes it much easier to identify geometry or resolution problems.
- **Avoid abrupt inner-domain transitions.** Carry the relevant inner-domain resolution entries into the overall domain, or add a separate transition-resolution shapefile for each inner domain. Without one of these approaches, the resolution can change abruptly at an inserted domain's edge.

The gradation parameters in each `resolution_entries` item are:

```python
(resolution_at_shapefile, resolution_away_from_shapefile,
 gradation_distance, buffer_zone)
```

The first two values are mesh resolutions in the target CRS units. qmesh preserves these metric values when it reprojects the raster, so they are metres for this repository's `EPSG:32630` target CRS. The generation output reads the unit from the target CRS metadata rather than assuming it. The final two values are distances in the shapefile CRS: the buffer zone holds the minimum resolution next to the shapefile, then the gradation distance controls the distance over which the resolution transitions to the away-from-shapefile value. Omit the buffer zone to use qmesh's default of `0.0`.

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

Set the execution behavior in `generation_config` in `input_params.py`:

- `qmesh_version`: `"qmesh3"` or `"qmeshcontainers"`
- `generate_fields`: generate fresh `.geo`/`.fld` inputs
- `reuse_existing_rasters`: reuse the configured `.nc` rasters instead of
  regenerating them
- `shapefiles_directory`: directory containing the GIS inputs and generated
  outputs

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
- **Projection/CRS issues**: the input shapefiles are in `EPSG:4326`, while generated mesh files use `EPSG:32630`. Raster bounds and the final two gradation parameters use input-shapefile coordinates; the first two gradation parameters are mesh resolutions in the target CRS units.
- **Problematic elements**: inspect the `.msh` file in a text editor to help locate the affected elements and trace them back to the input geometry.

---

## Notes

This repository focuses on mesh *generation inputs* and mesh creation for downstream hydrodynamic modelling. If you need the
mesh in a particular format or with additional physical region tagging, say what solver/workflow you’re targeting and we
can adjust the export steps accordingly.
