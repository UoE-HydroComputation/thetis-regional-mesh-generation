"""
Mesh generation for Pentland Firth/Orkneys

Shapefiles folder contains all the necessary files from qGIS to describe the geometry we wish to model.
The generate_mesh function calls qmesh; we feed into the necessary inputs based on the mesh characteristics
as described below.
If qmesh is not installed, this can be run in a qmeshcontainer (i.e. docker).
"""

import sys
import subprocess
import traceback


class Tee(object):
    """Write output to the terminal and a log file."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


def get_qmesh_module(version):
    """
    Selects the appropriate qmesh module based on version, 'qmesh3' or 'qmeshcontainers'.
    """
    if version == 'qmesh3':
        import qmesh3 as qmesh
    else:
        import qmesh
        qmesh.initialise()  # Initializing qgis API (only necessary when using qmeshcontainer)
    return qmesh


def insert_fld_to_geo(output_file_name, geo_file, inner_domains):
    """
    Appends one or more .fld files to the main .geo file, to include nested high-resolution domains.

    :param output_file_name: Name of the new .geo file to write (without extension).
    :param geo_file: Base .geo file name (without extension) for the overall domain.
    :param inner_domains: List of MeshConfig objects representing finer resolution domains.
    :return: None
    """
    with open(geo_file + ".geo", "r") as f_in:
        lines = f_in.readlines()

    if inner_domains:
        lines.pop()

        field_lines = []
        fields_list = [1]  # Always include the base field

        for idx, domain in enumerate(inner_domains):
            base_id = 200 + idx * 100
            fld_file = domain.name

            field_lines.extend([
                "\n", "// hi-res area {}\n".format(domain.name),
                "Field[{0}] = Structured;\n".format(base_id),
                'Field[{0}].FileName = "{1}.fld";\n'.format(base_id, fld_file),
                "Field[{0}].TextFormat = 1;\n".format(base_id),
                "Field[{0}].OutsideValue = 1000000;\n".format(base_id),
                "Field[{0}].SetOutsideValue = 1;\n".format(base_id),
                "Field[{1}] = MathEval;\n".format(base_id, base_id + 1),
                'Field[{1}].F = "F{0}";\n'.format(base_id, base_id + 1),
            ])

            fields_list.append(base_id + 1)

        # Add final Background Field using all MathEval fields plus 1
        field_lines.append("//\n")
        field_lines.append("Field[666] = Min;\n")
        field_lines.append("Field[666].FieldsList = {{{}}};\n".format(", ".join(str(f) for f in fields_list)))
        field_lines.append("\nBackground Field = 666;\n")

        lines.extend(field_lines)

    with open(output_file_name + ".geo", "w") as f_out:
        f_out.writelines(lines)


def get_coordinate_unit(coordinate_system):
    """Return the unit used by a qmesh/QGIS coordinate reference system."""
    try:
        is_geographic = coordinate_system.isGeographic()
    except AttributeError:
        is_geographic = coordinate_system.geographicFlag()
    return "degrees" if is_geographic else "metres"


def describe_target_coordinate_system(coordinate_system):
    """Describe common WGS 84 UTM coordinate systems with their units."""
    epsg_prefix = "EPSG:"
    if coordinate_system.upper().startswith(epsg_prefix):
        epsg_code = coordinate_system[len(epsg_prefix):]
        if epsg_code.isdigit() and 32601 <= int(epsg_code) <= 32660:
            return "WGS 84 / UTM zone {}N ({}; metres)".format(
                int(epsg_code) - 32600, coordinate_system
            )
        if epsg_code.isdigit() and 32701 <= int(epsg_code) <= 32760:
            return "WGS 84 / UTM zone {}S ({}; metres)".format(
                int(epsg_code) - 32700, coordinate_system
            )
    return coordinate_system


def print_resolution_entry(resolution_entry, raster_bounds, raster_resolution,
                           source_coordinate_system, target_coordinate_system):
    """Print the configuration used to create one mesh-resolution raster."""
    gradation_params = resolution_entry["gradation_params"]
    min_resolution = gradation_params[0]
    max_resolution = gradation_params[1]
    gradation_distance = gradation_params[2]
    buffer_zone = gradation_params[3] if len(gradation_params) > 3 else 0.0
    coordinate_unit = get_coordinate_unit(source_coordinate_system)
    details = [
        "FILE: {}".format(resolution_entry["shapefile"]),
        "  Input shapefile CRS: {} ({}; {})".format(
            source_coordinate_system.description(),
            source_coordinate_system.authid(),
            coordinate_unit,
        ),
        "  Target mesh CRS: {}".format(
            describe_target_coordinate_system(target_coordinate_system)
        ),
        "  Raster bounds: x={} to {}, y={} to {} {}".format(
            *(tuple(raster_bounds) + (coordinate_unit,))
        ),
        "  Raster resolution: {} x {} pixels".format(*raster_resolution),
        "  Minimum resolution: {} m".format(min_resolution),
        "  Maximum resolution: {} m".format(max_resolution),
        "  Gradation distance: {} {}".format(gradation_distance, coordinate_unit),
        "  Buffer zone: {} {}{}".format(
            buffer_zone,
            coordinate_unit,
            " (default)" if len(gradation_params) == 3 else "",
        ),
    ]
    sys.stdout.write("\n".join(details) + "\n")
    sys.stdout.flush()


def run_gmsh(name):
    """Run Gmsh and stream its combined output to the current stdout."""
    command = ["gmsh", "-2", name + ".geo", "-o", name + ".msh"]
    sys.stdout.write("Running command: {}\n".format(" ".join(command)))
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )
    for line in iter(process.stdout.readline, ""):
        sys.stdout.write(line)
    process.stdout.close()
    if process.wait() != 0:
        raise RuntimeError("gmsh failed while generating {}.msh".format(name))


def generate_geo_fld(config, coordinate_system='EPSG:32630'):
    """
    Generating .geo .fld files. Configuration file should have following inputs:

    :param config: A mesh configuration object (from input_params.py), typically either `overall_domain` or one of the `inner_domains`. Must have the following attributes:
        - name: Output base name for generated .geo/.fld files
        - outline: Path to shapefile defining the outer boundary
        - resolution_entries: Ordered resolution entries, each containing a shapefile and gradation parameters
        - raster_bounds: Shared boundary tuple for raster generation
        - raster_resolution: Tuple defining raster resolution (pixels)
        - raster_file: (Optional) path to an existing raster .nc file (used if skipping raster generation)
        - meshed_plots: (Optional) list of shapefiles defining subregions to mesh
    :param coordinate_system: The coordinate system (default: 'EPSG:32630').
    :return: None
    """
    # Reading outline, and converting to polylines and polygon shapes to communicate with qGIS
    boundaries = qmesh.vector.Shapes()
    boundaries.fromFile(config.outline)
    loopShapes = qmesh.vector.identifyLoops(boundaries, isGlobal=False, defaultPhysID=1000, fixOpenLoops=True)
    polygonShapes = qmesh.vector.identifyPolygons(loopShapes, meshedAreaPhysID=1)

    # Create raster for mesh gradation for increased resolution around regions of interest highlighted by shapefiles
    # Iteratively create these rasters and store the associated qmesh objects in a list
    gradation = []
    if config.raster_file is None:
        for resolution_entry in config.resolution_entries:
            boundary_shapefiles = qmesh.vector.Shapes()
            boundary_shapefiles.fromFile(resolution_entry["shapefile"])
            print_resolution_entry(
                resolution_entry,
                config.raster_bounds,
                config.raster_resolution,
                boundary_shapefiles.getCoordRefSystem(),
                coordinate_system,
            )
            gradation.append(qmesh.raster.meshMetricTools.gradationToShapes())
            gradation[-1].setShapes(boundary_shapefiles)
            gradation[-1].setRasterBounds(*config.raster_bounds)
            gradation[-1].setRasterResolution(*config.raster_resolution)
            gradation[-1].setGradationParameters(*resolution_entry["gradation_params"])
            gradation[-1].calculateLinearGradation()
            # gradation[-1].writeNetCDF('grad_'+str(i)+'.nc') # Output netCDF4 format raster

        if len(gradation) == 1:
            # If we only have one shapefile that defines the resolution, then use only that one to define our raster
            meshMetricRaster = gradation[0]
        else:
            # Mix all the information from multiple shapefiles to create a single raster that encompasses all
            # information
            meshMetricRaster = qmesh.raster.meshMetricTools.minimumRaster(gradation)  # grad_0

        # Export raster that defines the resolution; this can be used directly later instead of being regenerated
        meshMetricRaster.writeNetCDF(config.name + '.nc')
    else:
        # Read in existing mesh gradation raster
        meshMetricRaster = qmesh.raster.meshMetricTools.gradationToShapes()
        meshMetricRaster.fromNetCDF(config.raster_file)

    if config.meshed_plots is not None:
        for i in range(len(config.meshed_plots)):
            print('Meshed plot: {}'.format(config.meshed_plots[i]))
            print('Meshed plot ID: {}'.format(config.meshed_plots_ids[i]))
            plot = qmesh.vector.Shapes()
            plot.fromFile(config.meshed_plots[i])
            plot_loops = qmesh.vector.identifyLoops(plot,
                                                    fixOpenLoops=True, extraPointsPerVertex=10)
            plot_polygon = qmesh.vector.identifyPolygons(plot_loops, meshedAreaPhysID=config.meshed_plots_ids[i])
            loopShapes, polygonShapes = qmesh.vector.insertRegions(loopShapes, polygonShapes, plot_loops, plot_polygon)

    # Create domain object and write gmsh files.
    domain = qmesh.mesh.Domain()

    # Set geometry polylines and polygons
    domain.setGeometry(loopShapes, polygonShapes)

    # Specify coordinate system
    domain.setTargetCoordRefSystem(coordinate_system, fldFillValue=1000.0)

    # Specify gradation metric for gmsh
    domain.setMeshMetricField(meshMetricRaster)

    # Write .geo and .fld files
    domain.writeGmshFiles(config.name + '.geo', config.name + '.fld')


def convert_mesh(name):
    """
    Generates a shapefile based on the mesh. Useful for visualisation in QGIS
    :param name: Name of mesh file that needs to be converted to *.shp
    :return: None
    """
    mesh = qmesh.mesh.Mesh()
    mesh.readGmsh(name + '.msh', 'EPSG:32630')
    mesh.writeShapefile(name)


if __name__ == '__main__':
    """
    In this example we have put together the files for the Orkneys, and we call on these to the function
    """
    import os
    from input_params import overall_domain, inner_domains, meshname

    # Configuration for mesh generation
    qmesh_version = 'qmeshcontainers'  # 'qmesh3' or 'qmeshcontainers'
    new_fld_files = True  # Set to True if need to generate new .fld and .geo files
    load_existing_raster = False  # Set to True to load files from existing .nc raster (won't generate new ones)

    # Name for new mesh
    name = meshname

    os.chdir("shapefiles")  # Change working directory to folder that contains input files

    log_file = open(name + ".log", "w")
    terminal_stdout = sys.stdout
    terminal_stderr = sys.stderr
    sys.stdout = Tee(terminal_stdout, log_file)
    sys.stderr = Tee(terminal_stderr, log_file)

    try:
        sys.stdout.write("Writing mesh-generation log to {}.log\n".format(name))
        qmesh = get_qmesh_module(qmesh_version)

        if new_fld_files:
            for inner in inner_domains:
                if not load_existing_raster:
                    inner.raster_file = None
                generate_geo_fld(inner, coordinate_system='EPSG:32630')
            if not load_existing_raster:
                overall_domain.raster_file = None
            generate_geo_fld(overall_domain, coordinate_system='EPSG:32630')

        # Create
        insert_fld_to_geo(name, overall_domain.name, inner_domains)

        run_gmsh(name)

        # Convert the gmsh *.msh file to a *.shp file for visualisation in qGIS
        convert_mesh(name)
    except BaseException:
        traceback.print_exc(file=log_file)
        log_file.flush()
        raise
    finally:
        sys.stdout = terminal_stdout
        sys.stderr = terminal_stderr
        log_file.close()
