#!/usr/bin/env python3
"""Parametric accordion (bellows) soft-actuator mesh generator.

Generates the CAD geometry and meshes required by
``SurfacePressureConstraint_Accordion.py``:

    mesh/Accordion_Parametric.step   CAD geometry (OpenCASCADE, millimetres)
    mesh/Accordion_Surface.stl       outer triangular surface
    mesh/Accordion_Volumetric.vtk    first-order tetrahedral material volume
    mesh/Accordion_Cavity.stl        internal cavity surface (pressure constraint)

All dimensions are in millimetres.  Run head-less without arguments:

    python AccordionGeneration.py
"""

import math
import os
import sys

import numpy as np

import gmsh

# --------------------------------------------------------------------------- #
# Parameterisation (millimetres) - change these to regenerate the geometry.
# --------------------------------------------------------------------------- #
N_FOLDS = 5            # number of corrugation periods (pleats) along the axis
HEIGHT = 25.0          # total outer height of the actuator
R_CREST = 9.0          # outer radius at a pleat crest (widest)
R_VALLEY = 6.5         # outer radius at a pleat valley (narrowest)
WALL_THICKNESS = 2.5   # radial material thickness (crest -> cavity crest)
END_MARGIN_LEVELS = 2  # axial cap margin, expressed in half-period levels
BASE_Y = -5.0          # y coordinate of the bottom face (inside fixation box)

MESH_SIZE_MAX = 1.6    # target global element size
MESH_SIZE_MIN = 0.5    # minimum element size near small features

OUTPUT_DIR = "mesh"
STEP_NAME = "Accordion_Parametric.step"
SURFACE_NAME = "Accordion_Surface.stl"
VOLUME_NAME = "Accordion_Volumetric.vtk"
CAVITY_NAME = "Accordion_Cavity.stl"


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _make_revolved_solid(occ, profile, angle=2.0 * math.pi):
    """Revolve a closed (r, y) profile around the global Y axis."""
    points = [occ.addPoint(r, y, 0.0) for (r, y) in profile]
    lines = [occ.addLine(a, b) for a, b in zip(points[:-1], points[1:])]
    lines.append(occ.addLine(points[-1], points[0]))
    loop = occ.addCurveLoop(lines)
    surface = occ.addPlaneSurface([loop])
    out = occ.revolve([(2, surface)], 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, angle)
    return out


def _outer_profile():
    """Closed (r, y) cross-section of the solid outer body."""
    period = HEIGHT / (2.0 * N_FOLDS)
    profile = [(0.0, BASE_Y)]
    for level in range(2 * N_FOLDS + 1):
        radius = R_CREST if level % 2 == 0 else R_VALLEY
        profile.append((radius, BASE_Y + level * period))
    profile.append((0.0, BASE_Y + HEIGHT))
    return profile


def _cavity_profile():
    """Closed (r, y) cross-section of the internal cavity."""
    period = HEIGHT / (2.0 * N_FOLDS)
    first = END_MARGIN_LEVELS
    last = 2 * N_FOLDS - END_MARGIN_LEVELS
    profile = [(0.0, BASE_Y + first * period)]
    for level in range(first, last + 1):
        radius = R_CREST if level % 2 == 0 else R_VALLEY
        profile.append((radius - WALL_THICKNESS, BASE_Y + level * period))
    profile.append((0.0, BASE_Y + last * period))
    return profile


def _surface_max_radius(tag):
    """Maximum radial distance (from the Y axis) of a surface's mesh nodes."""
    _, coords, _ = gmsh.model.mesh.getNodes(2, tag, includeBoundary=True)
    if len(coords) == 0:
        return 0.0
    coords = np.asarray(coords, dtype=np.float64).reshape(-1, 3)
    return float(np.max(np.hypot(coords[:, 0], coords[:, 2])))


# --------------------------------------------------------------------------- #
# Mesh extraction / output helpers
# --------------------------------------------------------------------------- #
def _all_nodes():
    node_tags, coords, _ = gmsh.model.mesh.getNodes()
    node_tags = np.asarray(node_tags, dtype=np.int64)
    coords = np.asarray(coords, dtype=np.float64).reshape(-1, 3)
    return {int(t): coords[i] for i, t in enumerate(node_tags)}


def _surface_triangles(surface_tags, node_map):
    """Return an (n, 3, 3) array of triangle vertex coordinates."""
    triangles = []
    for tag in surface_tags:
        elem_types, _, elem_node_tags = gmsh.model.mesh.getElements(2, tag)
        for etype, conn in zip(elem_types, elem_node_tags):
            if etype != 2:  # only first-order triangles
                continue
            conn = np.asarray(conn, dtype=np.int64).reshape(-1, 3)
            for tri in conn:
                triangles.append([node_map[int(n)] for n in tri])
    if not triangles:
        return np.zeros((0, 3, 3), dtype=np.float64)
    return np.asarray(triangles, dtype=np.float64)


def _signed_volume(triangles):
    a = triangles[:, 0, :]
    b = triangles[:, 1, :]
    c = triangles[:, 2, :]
    return float(np.sum(np.einsum("ij,ij->i", a, np.cross(b, c))) / 6.0)


def _write_stl(path, triangles, name):
    with open(path, "w", encoding="ascii") as fh:
        fh.write(f"solid {name}\n")
        for tri in triangles:
            normal = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            norm = np.linalg.norm(normal)
            if norm > 0.0:
                normal = normal / norm
            fh.write(f"  facet normal {normal[0]:.9g} {normal[1]:.9g} {normal[2]:.9g}\n")
            fh.write("    outer loop\n")
            for vertex in tri:
                fh.write(
                    f"      vertex {vertex[0]:.9g} {vertex[1]:.9g} {vertex[2]:.9g}\n"
                )
            fh.write("    endloop\n")
            fh.write("  endfacet\n")
        fh.write(f"endsolid {name}\n")


def _volume_tetrahedra(volume_tags):
    """Return a list of first-order tetrahedra as node-tag quadruples."""
    tets = []
    for tag in volume_tags:
        elem_types, _, elem_node_tags = gmsh.model.mesh.getElements(3, tag)
        for etype, conn in zip(elem_types, elem_node_tags):
            if etype != 4:  # only first-order tetrahedra
                continue
            conn = np.asarray(conn, dtype=np.int64).reshape(-1, 4)
            tets.extend(conn.tolist())
    return tets


def _write_vtk(path, tets, node_map):
    """Write a legacy ASCII VTK unstructured grid containing tets only."""
    node_tags = sorted(node_map)
    index = {tag: i for i, tag in enumerate(node_tags)}
    with open(path, "w", encoding="ascii") as fh:
        fh.write("# vtk DataFile Version 2.0\nAccordion material volume\nASCII\n")
        fh.write("DATASET UNSTRUCTURED_GRID\n")
        fh.write(f"POINTS {len(node_tags)} double\n")
        for tag in node_tags:
            x, y, z = node_map[tag]
            fh.write(f"{x:.9g} {y:.9g} {z:.9g}\n")
        fh.write(f"CELLS {len(tets)} {5 * len(tets)}\n")
        for tet in tets:
            fh.write(
                "4 " + " ".join(str(index[int(n)]) for n in tet) + "\n"
            )
        fh.write(f"CELL_TYPES {len(tets)}\n")
        for _ in tets:
            fh.write("10\n")


# --------------------------------------------------------------------------- #
# Main generation
# --------------------------------------------------------------------------- #
def generate(output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("AccordionActuator")
        occ = gmsh.model.occ

        outer = _make_revolved_solid(occ, _outer_profile())
        cavity = _make_revolved_solid(occ, _cavity_profile())
        occ.synchronize()

        materials, _ = occ.cut(
            [(3, tag) for dim, tag in outer if dim == 3],
            [(3, tag) for dim, tag in cavity if dim == 3],
            removeObject=True,
            removeTool=True,
        )
        occ.synchronize()

        volume_tags = [tag for dim, tag in materials if dim == 3]
        if not volume_tags:
            volume_tags = [tag for dim, tag in gmsh.model.getEntities(3)]

        step_path = os.path.join(output_dir, STEP_NAME)
        gmsh.write(step_path)

        boundaries = gmsh.model.getBoundary(
            [(3, tag) for tag in volume_tags], oriented=False
        )
        surface_tags = [tag for dim, tag in boundaries if dim == 2]

        gmsh.option.setNumber("Mesh.MeshSizeMin", MESH_SIZE_MIN)
        gmsh.option.setNumber("Mesh.MeshSizeMax", MESH_SIZE_MAX)
        gmsh.option.setNumber("Mesh.MeshSizeFactor", 1.0)
        gmsh.option.setNumber("Mesh.ElementOrder", 1)
        gmsh.option.setNumber("Mesh.Algorithm", 6)
        gmsh.option.setNumber("Mesh.Algorithm3D", 1)
        gmsh.option.setNumber("Mesh.Optimize", 1)
        gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.removeDuplicateNodes()

        # The cavity lies strictly inside the outer radius R_CREST - WALL,
        # while every outer patch reaches the crest radius R_CREST.
        threshold = R_CREST - 0.5 * WALL_THICKNESS
        cavity_tags, skin_tags = [], []
        for tag in surface_tags:
            if _surface_max_radius(tag) < threshold:
                cavity_tags.append(tag)
            else:
                skin_tags.append(tag)
        if not cavity_tags:
            raise RuntimeError("No internal cavity surface detected")

        all_nodes = _all_nodes()
        tets = _volume_tetrahedra(volume_tags)
        if not tets:
            raise RuntimeError("No first-order tetrahedra in the material volume")

        used_tags = set()
        for tet in tets:
            used_tags.update(int(n) for n in tet)
        node_map = {tag: all_nodes[tag] for tag in used_tags}

        _write_vtk(os.path.join(output_dir, VOLUME_NAME), tets, node_map)

        skin = _surface_triangles(skin_tags, node_map)
        _write_stl(os.path.join(output_dir, SURFACE_NAME), skin, "accordion_surface")

        cavity = _surface_triangles(cavity_tags, node_map)
        # Orient the cavity faces outward (away from the cavity centre) so that
        # a positive pressure inflates the actuator.
        if _signed_volume(cavity) < 0.0:
            cavity = cavity[:, ::-1, :]
        _write_stl(os.path.join(output_dir, CAVITY_NAME), cavity, "accordion_cavity")

    finally:
        gmsh.finalize()


if __name__ == "__main__":
    try:
        generate()
    except Exception as exc:  # pragma: no cover - surfaced to the caller
        print(f"Accordion generation failed: {exc}", file=sys.stderr)
        raise
