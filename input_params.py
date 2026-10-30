class MeshConfig:
    """
    A class to store and manage the configuration of mesh generation.

    Attributes:
        name (str): Name for generated .geo and .fld files.
        outline (str): Path to the shapefile that defines the outline of the mesh domain.
        resolution_entries (list of dict): Ordered resolution entries. Each entry specifies its shapefile and gradation parameters.
        raster_bounds (tuple): A 4-tuple specifying the shared raster extent for all resolution shapefiles in the domain.
                              This is based on the input file projection.
        raster_resolution (tuple): A 2-tuple that defines the x- and y- resolution of the raster. The larger the value, the greater the computational time
                              units are pixels
        raster_file (str or None): Path to an existing raster file (optional). If None, a new raster is generated.
        meshed_plots (list of str): A list of shapefiles representing regions to be meshed as subdomains (optional).

    Methods:
        __init__: Initializes a new MeshConfig object with the provided parameters.
    """
    def __init__(self, name, outline, resolution_entries,
                 raster_bounds, raster_resolution=(800, 800), raster_file=None, meshed_plots=None,
                 meshed_plots_ids=None):
        if len(raster_bounds) != 4:
            raise ValueError("raster_bounds must contain four coordinates")
        if len(raster_resolution) != 2:
            raise ValueError("raster_resolution must contain an x and y pixel count")
        if meshed_plots is not None and meshed_plots_ids is not None and len(meshed_plots) != len(meshed_plots_ids):
            raise ValueError("meshed_plots and meshed_plots_ids must have the same length")
        for entry in resolution_entries:
            if set(entry) != {"shapefile", "gradation_params"}:
                raise ValueError("each resolution entry must contain shapefile and gradation_params")

        self.name = name
        self.outline = outline
        self.resolution_entries = resolution_entries
        self.raster_bounds = raster_bounds
        self.raster_resolution = raster_resolution
        self.raster_file = raster_file
        self.meshed_plots = meshed_plots if meshed_plots is not None else []
        self.meshed_plots_ids = meshed_plots_ids if meshed_plots_ids is not None else []


class MeshGenerationConfig:
    """Settings that control how a mesh configuration is generated."""
    def __init__(self, meshname, shapefiles_directory,
                 target_coordinate_system, qmesh_version="qmeshcontainers",
                 generate_fields=True, reuse_existing_rasters=False,
                 boundary_physical_id=1000, area_physical_id=1,
                 nested_raster_outside_value=1000000,
                 raster_reprojection_fill_value=1000.0,
                 is_global=False, fix_open_loops=True,
                 meshed_plot_extra_points_per_vertex=10):
        if qmesh_version not in ("qmesh3", "qmeshcontainers"):
            raise ValueError(
                "qmesh_version must be 'qmesh3' or 'qmeshcontainers'"
            )
        if not isinstance(generate_fields, bool):
            raise ValueError("generate_fields must be a boolean")
        if not isinstance(reuse_existing_rasters, bool):
            raise ValueError("reuse_existing_rasters must be a boolean")
        if not isinstance(is_global, bool):
            raise ValueError("is_global must be a boolean")
        if not isinstance(fix_open_loops, bool):
            raise ValueError("fix_open_loops must be a boolean")

        self.meshname = meshname
        self.shapefiles_directory = shapefiles_directory
        self.target_coordinate_system = target_coordinate_system
        self.qmesh_version = qmesh_version
        self.generate_fields = generate_fields
        self.reuse_existing_rasters = reuse_existing_rasters
        self.boundary_physical_id = boundary_physical_id
        self.area_physical_id = area_physical_id
        # This Gmsh field value applies outside nested raster extents. It must
        # be larger than all desired mesh sizes so the Min field ignores it.
        self.nested_raster_outside_value = nested_raster_outside_value
        self.raster_reprojection_fill_value = raster_reprojection_fill_value
        self.is_global = is_global
        self.fix_open_loops = fix_open_loops
        self.meshed_plot_extra_points_per_vertex = (
            meshed_plot_extra_points_per_vertex
        )


RESOLUTION_ENTRIES = {
    "mainland": {
        "shapefile": "resolution_outlines/mainland.shp",
        "gradation_params": (1500.0, 20000.0, 0.5),
    },
    "big_islands": {
        "shapefile": "resolution_outlines/islands/big_islands.shp",
        "gradation_params": (300.0, 20000.0, 0.5),
    },
    "westray": {
        "shapefile": "refinement_regions/Westray/westray_refinement.shp",
        "gradation_params": (100.0, 20000.0, 3.0),
    },
    "fow": {
        "shapefile": "resolution_outlines/FoW/FoW.shp",
        "gradation_params": (100.0, 20000.0, 0.5),
    },
    "fow_refinement": {
        "shapefile": "refinement_regions/FoW/FoW_refinement.shp",
        "gradation_params": (100.0, 20000.0, 3.0),
    },
    "stronsay_firth": {
        "shapefile": "refinement_regions/StronsayFirth/stronsay_firth_refinement.shp",
        "gradation_params": (150.0, 20000.0, 3.0),
    },
    "shapinsay": {
        "shapefile": "refinement_regions/Shapinsay/shapinsay_north_refinement.shp",
        "gradation_params": (150.0, 20000.0, 3.0),
    },
    "outer_sound": {
        "shapefile": "refinement_regions/OuterSound/outer_sound_refinement.shp",
        "gradation_params": (150.0, 20000.0, 5.0),
    },
    "inner_sound": {
        "shapefile": "refinement_regions/InnerSound/inner_sound_refinement.shp",
        "gradation_params": (150.0, 20000.0, 5.0),
    },
    "brims": {
        "shapefile": "refinement_regions/Brims/brims_refinement.shp",
        "gradation_params": (150.0, 20000.0, 5.0),
    },
    "swona_eddies": {
        "shapefile": "refinement_regions/PF/swona_eddies.shp",
        "gradation_params": (150.0, 20000.0, 5.0),
    },
    "stroma_eddies": {
        "shapefile": "refinement_regions/PF/stroma_eddies.shp",
        "gradation_params": (150.0, 20000.0, 5.0),
    },
    "pf_islands": {
        "shapefile": "resolution_outlines/PF/PF_islands.shp",
        "gradation_params": (30.0, 20000.0, 1.0),
    },
    "meygen_lease_area": {
        "shapefile": "refinement_regions/InnerSound/Meygen_lease_area_polygons.shp",
        "gradation_params": (50.0, 20000.0, 5.0),
    },
    "swona_eddies_pf": {
        "shapefile": "refinement_regions/PF/swona_eddies.shp",
        "gradation_params": (100.0, 20000.0, 5.0),
    },
    "stroma_eddies_pf": {
        "shapefile": "refinement_regions/PF/stroma_eddies.shp",
        "gradation_params": (100.0, 20000.0, 5.0),
    },
    "fow_detailed": {
        "shapefile": "resolution_outlines/FoW/FoW.shp",
        "gradation_params": (100.0, 20000.0, 1.0, 0.003),
    },
    "fow_refinement_detailed": {
        "shapefile": "refinement_regions/FoW/FoW_refinement.shp",
        "gradation_params": (100.0, 20000.0, 5.0),
    },
    "westray_detailed": {
        "shapefile": "refinement_regions/Westray/westray_refinement.shp",
        "gradation_params": (100.0, 20000.0, 5.0),
    },
    "turbine_deployment_area": {
        "shapefile": "refinement_regions/FoW/turbine_deployment_area_FoW.shp",
        "gradation_params": (100.0, 20000.0, 3.0),
    },
    "shapinsay_detailed": {
        "shapefile": "refinement_regions/Shapinsay/shapinsay_north_refinement.shp",
        "gradation_params": (150.0, 20000.0, 5.0),
    },
    "von_karman_street": {
        "shapefile": "refinement_regions/Westray/von_karman_street.shp",
        "gradation_params": (100.0, 20000.0, 3.0),
    },
    "greenholms": {
        "shapefile": "resolution_outlines/FoW/GreenHolms.shp",
        "gradation_params": (30.0, 20000.0, 3.0),
    },
}


def select_resolution_entries(*names):
    return [RESOLUTION_ENTRIES[name] for name in names]

# Overall domain
OverallDomain = MeshConfig(
    name="overall_domain",
    outline="outlines/Outlines_no_small.shp",
    resolution_entries=select_resolution_entries(
        "mainland", "big_islands", "westray", "fow", "fow_refinement",
        "stronsay_firth", "shapinsay", "outer_sound", "inner_sound", "brims",
        "swona_eddies", "stroma_eddies", "pf_islands",
    ),
    raster_bounds=(-4.7, -1.10, 57.0, 60.6),
    raster_resolution=(800, 800),
    raster_file="overall_domain.nc",
    meshed_plots=[],
    meshed_plots_ids=[]
)

# Inner domains - insert these for more resolution without having to have a really big raster in the overall domain
PF = MeshConfig(
    name="PFmesh",
    outline="outlines/outlines_PF.shp",
    resolution_entries=select_resolution_entries(
        "mainland", "big_islands", "outer_sound", "inner_sound", "meygen_lease_area",
        "brims", "swona_eddies_pf", "stroma_eddies_pf", "pf_islands",
    ),
    raster_bounds=(-3.4, -2.85, 58.55, 58.85),
    raster_resolution=(600, 600),
    raster_file="PFmesh.nc",
    meshed_plots=[],
    meshed_plots_ids=[]
)

FoW = MeshConfig(
    name="FoWmesh",
    outline="outlines/outlines_FoW.shp",
    resolution_entries=select_resolution_entries(
        "big_islands", "fow_detailed", "fow_refinement_detailed", "westray_detailed",
        "turbine_deployment_area", "stronsay_firth", "shapinsay_detailed",
        "von_karman_street", "greenholms",
    ),
    raster_bounds=(-3.02, -2.61, 58.94, 59.35),
    raster_resolution=(600, 600),
    raster_file="FoWmesh.nc",
    meshed_plots=[],
    meshed_plots_ids=[]
)


overall_domain = OverallDomain
inner_domains = [PF, FoW]

generation_config = MeshGenerationConfig(
    meshname="OrkneysAdjoint-v0",
    shapefiles_directory="shapefiles",
    target_coordinate_system="EPSG:32630",
    qmesh_version="qmeshcontainers",
    generate_fields=True,
    reuse_existing_rasters=False,
    boundary_physical_id=1000,
    area_physical_id=1,
    nested_raster_outside_value=1000000,
    raster_reprojection_fill_value=1000.0,
    is_global=False,
    fix_open_loops=True,
    meshed_plot_extra_points_per_vertex=10,
)
