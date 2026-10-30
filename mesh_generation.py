"""
Reusable qmesh and Gmsh mesh-generation workflow.

Scenario-specific domains and run settings are read from input_params.py.
"""

import sys
import subprocess
import traceback
import re

from qmesh_tools import get_qmesh_module


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


def insert_fld_to_geo(output_file_name, geo_file, inner_domains,
                      nested_raster_outside_value):
    """
    Appends one or more .fld files to the main .geo file, to include nested high-resolution domains.

    :param output_file_name: Name of the new .geo file to write (without extension).
    :param geo_file: Base .geo file name (without extension) for the overall domain.
    :param inner_domains: List of MeshConfig objects representing finer resolution domains.
    :param nested_raster_outside_value: Gmsh mesh size to use outside a nested
        raster's extent. This should exceed all desired mesh sizes so the
        combined minimum field ignores the nested raster outside its area.
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
                "Field[{0}].OutsideValue = {1};\n".format(
                    base_id, nested_raster_outside_value
                ),
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
    """Return the axis unit declared by a QGIS coordinate reference system."""
    unit_names = re.findall(
        r'(?:UNIT|LENGTHUNIT|ANGLEUNIT)\s*\[\s*"([^"]+)"',
        coordinate_system.toWkt(),
    )
    if not unit_names:
        raise ValueError(
            "Could not determine the coordinate unit for CRS {}".format(
                coordinate_system.authid()
            )
        )

    unit_name = unit_names[-1]
    unit_names = {
        "degree": "degrees",
        "metre": "metres",
        "meter": "metres",
    }
    return unit_names.get(unit_name.lower(), unit_name)


def get_coordinate_unit_from_string(coordinate_system):
    """Return the declared axis unit for a target CRS string."""
    from qgis.core import QgsCoordinateReferenceSystem

    target_crs = QgsCoordinateReferenceSystem()
    if not target_crs.createFromString(coordinate_system):
        raise ValueError(
            "Could not create a coordinate reference system from {!r}".format(
                coordinate_system
            )
        )
    return get_coordinate_unit(target_crs)


def describe_target_coordinate_system(coordinate_system, coordinate_unit):
    """Describe common WGS 84 UTM coordinate systems with their units."""
    epsg_prefix = "EPSG:"
    if coordinate_system.upper().startswith(epsg_prefix):
        epsg_code = coordinate_system[len(epsg_prefix):]
        if epsg_code.isdigit() and 32601 <= int(epsg_code) <= 32660:
            return "WGS 84 / UTM zone {}N ({}; {})".format(
                int(epsg_code) - 32600, coordinate_system, coordinate_unit
            )
        if epsg_code.isdigit() and 32701 <= int(epsg_code) <= 32760:
            return "WGS 84 / UTM zone {}S ({}; {})".format(
                int(epsg_code) - 32700, coordinate_system, coordinate_unit
            )
    return "{} ({})".format(coordinate_system, coordinate_unit)


def print_resolution_entry(resolution_entry, raster_bounds, raster_resolution,
                           source_coordinate_system, target_coordinate_system,
                           target_coordinate_unit):
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
            describe_target_coordinate_system(
                target_coordinate_system, target_coordinate_unit
            )
        ),
        "  Raster bounds: x={} to {}, y={} to {} {}".format(
            *(tuple(raster_bounds) + (coordinate_unit,))
        ),
        "  Raster resolution: {} x {} pixels".format(*raster_resolution),
        "  Minimum resolution: {} {}".format(
            min_resolution, target_coordinate_unit
        ),
        "  Maximum resolution: {} {}".format(
            max_resolution, target_coordinate_unit
        ),
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


def generate_geo_fld(config, generation_config):
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
    :param generation_config: Settings shared by the mesh-generation run.
    :return: None
    """
    coordinate_system = generation_config.target_coordinate_system
    target_coordinate_unit = get_coordinate_unit_from_string(coordinate_system)

    # Reading outline, and converting to polylines and polygon shapes to communicate with qGIS
    boundaries = qmesh.vector.Shapes()
    boundaries.fromFile(config.outline)
    loopShapes = qmesh.vector.identifyLoops(
        boundaries,
        isGlobal=generation_config.is_global,
        defaultPhysID=generation_config.boundary_physical_id,
        fixOpenLoops=generation_config.fix_open_loops,
    )
    polygonShapes = qmesh.vector.identifyPolygons(
        loopShapes, meshedAreaPhysID=generation_config.area_physical_id
    )

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
                target_coordinate_unit,
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
            plot_loops = qmesh.vector.identifyLoops(
                plot,
                fixOpenLoops=generation_config.fix_open_loops,
                extraPointsPerVertex=(
                    generation_config.meshed_plot_extra_points_per_vertex
                ),
            )
            plot_polygon = qmesh.vector.identifyPolygons(plot_loops, meshedAreaPhysID=config.meshed_plots_ids[i])
            loopShapes, polygonShapes = qmesh.vector.insertRegions(loopShapes, polygonShapes, plot_loops, plot_polygon)

    # Create domain object and write gmsh files.
    domain = qmesh.mesh.Domain()

    # Set geometry polylines and polygons
    domain.setGeometry(loopShapes, polygonShapes)

    # Specify coordinate system
    domain.setTargetCoordRefSystem(
        coordinate_system,
        fldFillValue=generation_config.raster_reprojection_fill_value,
    )

    # Specify gradation metric for gmsh
    domain.setMeshMetricField(meshMetricRaster)

    # Write .geo and .fld files
    domain.writeGmshFiles(config.name + '.geo', config.name + '.fld')


def convert_mesh(name, coordinate_system):
    """
    Generates a shapefile based on the mesh. Useful for visualisation in QGIS
    :param name: Name of mesh file that needs to be converted to *.shp
    :return: None
    """
    mesh = qmesh.mesh.Mesh()
    mesh.readGmsh(name + '.msh', coordinate_system)
    mesh.writeShapefile(name)


if __name__ == '__main__':
    import os
    from input_params import generation_config, inner_domains, overall_domain

    if not os.path.isdir(generation_config.shapefiles_directory):
        raise ValueError(
            "Shapefiles directory does not exist: {}".format(
                generation_config.shapefiles_directory
            )
        )
    os.chdir(generation_config.shapefiles_directory)
    name = generation_config.meshname

    log_file = open(name + ".log", "w")
    terminal_stdout = sys.stdout
    terminal_stderr = sys.stderr
    sys.stdout = Tee(terminal_stdout, log_file)
    sys.stderr = Tee(terminal_stderr, log_file)

    try:
        sys.stdout.write("Writing mesh-generation log to {}.log\n".format(name))
        qmesh = get_qmesh_module(generation_config.qmesh_version)

        if generation_config.generate_fields:
            for inner in inner_domains:
                if not generation_config.reuse_existing_rasters:
                    inner.raster_file = None
                generate_geo_fld(inner, generation_config)
            if not generation_config.reuse_existing_rasters:
                overall_domain.raster_file = None
            generate_geo_fld(overall_domain, generation_config)

        # Create
        insert_fld_to_geo(
            name,
            overall_domain.name,
            inner_domains,
            generation_config.nested_raster_outside_value,
        )

        run_gmsh(name)

        # Convert the gmsh *.msh file to a *.shp file for visualisation in qGIS
        convert_mesh(name, generation_config.target_coordinate_system)
    except BaseException:
        traceback.print_exc(file=log_file)
        log_file.flush()
        raise
    finally:
        sys.stdout = terminal_stdout
        sys.stderr = terminal_stderr
        log_file.close()
