#!/usr/bin/env python3
"""Parametric generator for an accordion-shaped soft actuator.

The script builds a CAD model of a bellows/accordion body (a solid of
revolution whose radius oscillates along its main axis) together with an
internal cylindrical pressure cavity.  It meshes the geometry and writes:

    mesh/Accordion_Parametric.step : CAD geometry (OpenCASCADE)
    mesh/Accordion_Surface.stl     : outer triangular surface mesh
    mesh/Accordion_Volumetric.vtk  : first-order tetrahedral volume mesh
    mesh/Accordion_Cavity.stl      : internal cavity surface for the
                                     SOFA SurfacePressureConstraint

All lengths are expressed in millimetres.

The actuator is aligned with the Y axis so that the fixation BoxROI of the
supplied SOFA scene (box = [-15, -7, -15, 15, -3, 15]) selects a band of the
lower part of the body.  Everything can be regenerated from the parameters
below; no external files are required.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import gmsh
import numpy as np

# ---------------------------------------------------------------------------
# Parameters (mm).  Change these values to regenerate the CAD and the meshes.
# ---------------------------------------------------------------------------

#: Long axis of the actuator (Y), from -LENGTH/2 to +LENGTH/2.
LENGTH_MM = 20.0

#: Number of accordion folds (bellows periods) along the long axis.
N_FOLDS = 4

#: Mean outer radius of the bellows.
MEAN_RADIUS_MM = 7.5

#: Amplitude of the outer-radius oscillation (folds).
FOLD_AMPLITUDE_MM = 1.5

#: Radius of the internal pressure cavity.
CAVITY_RADIUS_MM = 3.5

#: Material wall left at both ends of the cavity.
END_WALL_MM = 1.5

#: Number of CAD sections sampled per fold (radius resolution of the CAD).
SECTIONS_PER_FOLD = 4

#: Target 1D/2D/3D mesh element size range in mm.
MESH_SIZE_MIN_MM = 1.5
MESH_SIZE_MAX_MM = 2.5

#: 3D meshing algorithm (10 = HXT, fast; 1 = Delaunay).
MESH_ALGORITHM_3D = 10

OUTPUT_DIRNAME = "mesh"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _triangle_soup(node_tags, node_coords, node_index, element_types,
                   element_node_tags):
    """Return an (N, 3, 3) float array of triangles for the given elements."""
    triangles = []
    coords = node_coords
    for etype, conn in zip(element_types, element_node_tags):
        conn = np.asarray(conn, dtype=np.int64)
        if etype == 2:  # first-order triangle
            conn = conn.reshape(-1, 3)
        elif etype == 3:  # second-order triangle -> drop mid-edge nodes
            conn = conn.reshape(-1, 6)[:, :3]
        else:
            continue
        idx = np.array([node_index[t] for t in conn.ravel()]).reshape(conn.shape)
        pts = coords[idx]
        triangles.append(pts)
    if not triangles:
        return np.zeros((0, 3, 3), dtype=float)
    return np.concatenate(triangles, axis=0)


def _write_ascii_stl(path: Path, triangles: np.ndarray, name: str) -> None:
    """Write a triangle soup as an ASCII STL file."""
    with path.open("w", encoding="ascii") as fh:
        fh.write(f"solid {name}\n")
        for tri in triangles:
            a, b, c = tri
            n = np.cross(b - a, c - a)
            ln = np.linalg.norm(n)
            if ln > 0.0:
                n = n / ln
            else:
                n = np.zeros(3)
            fh.write(f"  facet normal {n[0]:.7e} {n[1]:.7e} {n[2]:.7e}\n")
            fh.write("    outer loop\n")
            for p in (a, b, c):
                fh.write(f"      vertex {p[0]:.7e} {p[1]:.7e} {p[2]:.7e}\n")
            fh.write("    endloop\n")
            fh.write("  endfacet\n")
        fh.write(f"endsolid {name}\n")


def _write_legacy_vtk_tets(path: Path, points: np.ndarray,
                           tets: np.ndarray, title: str) -> None:
    """Write a legacy ASCII VTK unstructured grid with tetrahedra only."""
    npoints = points.shape[0]
    ntets = tets.shape[0]
    with path.open("w", encoding="ascii") as fh:
        fh.write("# vtk DataFile Version 3.0\n")
        fh.write(f"{title}\n")
        fh.write("ASCII\n")
        fh.write("DATASET UNSTRUCTURED_GRID\n")
        fh.write(f"POINTS {npoints} double\n")
        for p in points:
            fh.write(f"{p[0]:.9e} {p[1]:.9e} {p[2]:.9e}\n")
        fh.write(f"CELLS {ntets} {ntets * 5}\n")
        for t in tets:
            fh.write(f"4 {t[0]} {t[1]} {t[2]} {t[3]}\n")
        fh.write(f"CELL_TYPES {ntets}\n")
        for _ in range(ntets):
            fh.write("10\n")


# ---------------------------------------------------------------------------
# Geometry and mesh generation
# ---------------------------------------------------------------------------

def build_geometry():
    """Create the OCC geometry and return the relevant entity tags."""
    y0 = -0.5 * LENGTH_MM
    n_sections = N_FOLDS * SECTIONS_PER_FOLD + 1
    if n_sections < 2:
        n_sections = 2

    # Loft through circles whose radius oscillates along the long (Y) axis.
    # makeRuled avoids B-spline overshoot between the sampled sections.
    loops = []
    for i in range(n_sections):
        y = y0 + LENGTH_MM * i / (n_sections - 1)
        phase = 2.0 * math.pi * N_FOLDS * (y - y0) / LENGTH_MM
        radius = MEAN_RADIUS_MM + FOLD_AMPLITUDE_MM * math.cos(phase)
        circle = gmsh.model.occ.addCircle(0.0, y, 0.0, radius,
                                          zAxis=[0.0, 1.0, 0.0])
        loops.append(gmsh.model.occ.addCurveLoop([circle]))

    outer = gmsh.model.occ.addThruSections(loops, makeSolid=True,
                                           makeRuled=True)
    outer_vol = outer[0][1]

    # Internal cylindrical pressure cavity.
    cavity_vol = gmsh.model.occ.addCylinder(
        0.0, y0 + END_WALL_MM, 0.0,
        0.0, LENGTH_MM - 2.0 * END_WALL_MM, 0.0,
        CAVITY_RADIUS_MM,
    )

    gmsh.model.occ.synchronize()

    cavity_surfaces = [s[1] for s in
                       gmsh.model.getBoundary([(3, cavity_vol)],
                                              oriented=False)]
    outer_surfaces = [s[1] for s in
                      gmsh.model.getBoundary([(3, outer_vol)],
                                             oriented=False)]

    # Keep the cavity as a free (non-conforming) closed surface embedded in
    # the solid so that it can be exported for the pressure constraint.
    gmsh.model.occ.remove([(3, cavity_vol)], recursive=False)
    gmsh.model.occ.synchronize()

    return outer_vol, outer_surfaces, cavity_surfaces


def generate(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("Accordion")

        outer_vol, outer_surfaces, cavity_surfaces = build_geometry()

        # CAD geometry (exported before meshing).
        gmsh.write(str(out_dir / "Accordion_Parametric.step"))

        gmsh.option.setNumber("Mesh.MeshSizeMin", MESH_SIZE_MIN_MM)
        gmsh.option.setNumber("Mesh.MeshSizeMax", MESH_SIZE_MAX_MM)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.option.setNumber("Mesh.Algorithm3D", MESH_ALGORITHM_3D)
        gmsh.model.mesh.generate(3)

        # --- collect nodes -------------------------------------------------
        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        node_coords = np.asarray(node_coords, dtype=float).reshape(-1, 3)
        node_index = {int(t): i for i, t in enumerate(node_tags)}

        # --- tetrahedra (first order only) ---------------------------------
        element_types, element_tags, element_nodes = \
            gmsh.model.mesh.getElements(3, outer_vol)
        tet_list = []
        for etype, conn in zip(element_types, element_nodes):
            if etype != 4:
                continue
            tet_list.append(np.asarray(conn, dtype=np.int64).reshape(-1, 4))
        if not tet_list:
            raise RuntimeError("Gmsh produced no first-order tetrahedra")
        tet_tags = np.concatenate(tet_list, axis=0)

        # Renumber to only the nodes referenced by the tetrahedra.
        used = np.unique(tet_tags)
        remap = {int(t): i for i, t in enumerate(used)}
        tet_index = np.array([[remap[int(t)] for t in tet]
                              for tet in tet_tags], dtype=np.int64)
        tet_points = node_coords[[node_index[int(t)] for t in used]]

        # --- surfaces ------------------------------------------------------
        def surface_triangles(surface_tags):
            arrays = []
            for tag in surface_tags:
                etypes, etags, enodes = gmsh.model.mesh.getElements(2, tag)
                arrays.append(_triangle_soup(node_tags, node_coords,
                                             node_index, etypes, enodes))
            return np.concatenate(arrays, axis=0) if arrays else \
                np.zeros((0, 3, 3), dtype=float)

        outer_tris = surface_triangles(outer_surfaces)
        cavity_tris = surface_triangles(cavity_surfaces)
        if outer_tris.shape[0] == 0:
            raise RuntimeError("Gmsh produced no outer surface triangles")
        if cavity_tris.shape[0] == 0:
            raise RuntimeError("Gmsh produced no cavity surface triangles")

        # --- write outputs -------------------------------------------------
        _write_legacy_vtk_tets(out_dir / "Accordion_Volumetric.vtk",
                               tet_points, tet_index, "Accordion volume")
        _write_ascii_stl(out_dir / "Accordion_Surface.stl",
                         outer_tris, "Accordion_Surface")
        _write_ascii_stl(out_dir / "Accordion_Cavity.stl",
                         cavity_tris, "Accordion_Cavity")

        stats = {
            "volume_vertices": int(tet_points.shape[0]),
            "tetrahedra": int(tet_index.shape[0]),
            "surface_triangles": int(outer_tris.shape[0]),
            "surface_vertices": int(len(np.unique(outer_tris.reshape(-1, 3),
                                                   axis=0))),
            "cavity_triangles": int(cavity_tris.shape[0]),
            "cavity_vertices": int(len(np.unique(cavity_tris.reshape(-1, 3),
                                                 axis=0))),
        }
        return stats
    finally:
        gmsh.finalize()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=Path.cwd() / OUTPUT_DIRNAME,
                        help="output directory (default: ./mesh)")
    args = parser.parse_args()

    stats = generate(args.out)
    print(f"Wrote meshes to {args.out.resolve()}")
    for key in sorted(stats):
        print(f"  {key}: {stats[key]}")


if __name__ == "__main__":
    main()
