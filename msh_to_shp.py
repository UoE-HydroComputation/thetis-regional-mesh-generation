"""Convert a Gmsh mesh to a shapefile for visualisation."""

import argparse
import os


def get_qmesh_module(version):
    """Select the appropriate qmesh module."""
    if version == "qmesh3":
        import qmesh3 as qmesh
    else:
        import qmesh

        qmesh.initialise()
    return qmesh


def convert_mesh(qmesh, mesh_file, coordinate_system):
    """Write a shapefile alongside a Gmsh mesh."""
    mesh = qmesh.mesh.Mesh()
    mesh.readGmsh(mesh_file, coordinate_system)
    mesh.writeShapefile(os.path.splitext(mesh_file)[0])


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert a Gmsh .msh mesh to a shapefile using qmesh."
    )
    parser.add_argument("mesh_file", help="Path to the input .msh file")
    parser.add_argument(
        "--qmesh-version",
        choices=("qmesh3", "qmeshcontainers"),
        default="qmeshcontainers",
        help="qmesh installation to use (default: qmeshcontainers)",
    )
    parser.add_argument(
        "--coordinate-system",
        default="EPSG:32630",
        help="CRS of the mesh coordinates (default: EPSG:32630)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    convert_mesh(
        get_qmesh_module(args.qmesh_version),
        args.mesh_file,
        args.coordinate_system,
    )
