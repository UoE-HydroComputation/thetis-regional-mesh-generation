#!/usr/bin/env python3
"""Convert a Gmsh 2.2 mesh to a shapefile of its exact domain boundary."""

import argparse
from pathlib import Path

import geopandas as gpd
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union


def parse_msh_file(filepath):
    """Return node coordinates and boundary edges from a Gmsh 2.2 mesh."""
    nodes = {}
    line_edges = []
    triangle_edges = {}

    with open(filepath, 'r') as mesh_file:
        lines = iter(mesh_file)
        for line in lines:
            section = line.strip()
            if section == '$Nodes':
                node_count = int(next(lines).strip())
                for _ in range(node_count):
                    parts = next(lines).split()
                    nodes[int(parts[0])] = (float(parts[1]), float(parts[2]))
            elif section == '$Elements':
                element_count = int(next(lines).strip())
                for _ in range(element_count):
                    parts = list(map(int, next(lines).split()))
                    element_type, tag_count = parts[1], parts[2]
                    element_nodes = parts[3 + tag_count:]

                    if element_type == 1 and len(element_nodes) == 2:
                        line_edges.append(tuple(element_nodes))
                    elif element_type == 2 and len(element_nodes) == 3:
                        a, b, c = element_nodes
                        for edge in ((a, b), (b, c), (c, a)):
                            key = tuple(sorted(edge))
                            triangle_edges[key] = triangle_edges.get(key, 0) + 1

    if not nodes:
        raise ValueError(f"No nodes found in mesh file: {filepath}")

    # Gmsh line elements encode the explicit boundary segments. If absent,
    # recover the boundary as the triangle edges incident to one cell.
    boundary_edges = line_edges or [
        edge for edge, incidence in triangle_edges.items() if incidence == 1
    ]
    if not boundary_edges:
        raise ValueError(f"No boundary edges found in mesh file: {filepath}")

    return nodes, boundary_edges


def extract_boundary_polygon(nodes, boundary_edges):
    """Polygonize boundary segments without simplifying their vertices."""
    edge_lines = [
        LineString((nodes[start], nodes[end]))
        for start, end in boundary_edges
    ]
    polygons = list(polygonize(unary_union(edge_lines)))
    if not polygons:
        raise ValueError("Boundary edges do not form any closed polygon")

    # polygonize emits both a polygon with a hole and a polygon filling that
    # hole. Drop the latter; it is not part of the meshed domain.
    hole_rings = [
        Polygon(ring)
        for polygon in polygons
        for ring in polygon.interiors
    ]
    polygons = [
        polygon for polygon in polygons
        if not any(Polygon(polygon.exterior).equals(ring) for ring in hole_rings)
    ]

    return polygons[0] if len(polygons) == 1 else unary_union(polygons)


def create_shapefile(polygon, output_path, crs=None):
    """Write a polygon or multipolygon to an ESRI shapefile."""
    if crs is None:
        print("WARNING: CRS not provided and therefore unassigned")
    gdf = gpd.GeoDataFrame({'id': [1], 'geometry': [polygon]}, crs=crs)
    gdf.to_file(f"{output_path}.shp")
    print(f"Shapefile created: {output_path}.shp")
    return gdf


def main():
    parser = argparse.ArgumentParser(
        description='Convert Gmsh .msh file to shapefile polygon'
    )
    parser.add_argument('input_file', help='Input .msh file path')
    parser.add_argument(
        '-o', '--output',
        help='Output shapefile path (without .shp extension)',
        default=None
    )
    parser.add_argument(
        '--crs',
        help='Coordinate reference system to assign (for example EPSG:32630); '
             'if omitted, the CRS is left unassigned',
        default=None
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = str(Path(args.input_file).with_suffix(''))

    print(f"Parsing mesh file: {args.input_file}")
    nodes, boundary_edges = parse_msh_file(args.input_file)
    print(f"Found {len(nodes)} nodes and {len(boundary_edges)} boundary edges")

    print("Extracting boundary polygon...")
    polygon = extract_boundary_polygon(nodes, boundary_edges)
    print(f"Boundary polygon created: {polygon.geom_type}")

    print(f"Creating shapefile: {args.output}.shp")
    create_shapefile(polygon, args.output, args.crs)
    print("Done!")


if __name__ == '__main__':
    main()
