#!/usr/bin/env python3
"""Parametric Gmsh generator for a hollow accordion soft actuator (millimetres)."""
from pathlib import Path
import math
import gmsh

# Public geometry parameters (mm unless stated otherwise).
BASE_Y = -7.0                 # actuator base; overlaps the scene fixation ROI
HEIGHT = 30.0
BASE_RADIUS = 9.0
CREASE_RADIUS = 7.0
BELLOWS_RADIUS = 10.0
FOLDS = 4
WALL = 4.0
CAP = 2.0
RADIAL_SEGMENTS = 36          # circumferential mesh resolution
MESH_SIZE = 3.0               # target tetrahedron edge length, mm

OUT = Path.cwd() / "mesh"


def profile_points(inner=False):
    """Return an axisymmetric radial profile including smooth end collars."""
    top = BASE_Y + HEIGHT
    chamber_bottom = BASE_Y + CAP
    chamber_top = top - CAP
    if inner:
        lo, hi = chamber_bottom, chamber_top
        # The chamber follows the bellows valleys while retaining a printable wall.
        pts = [(BASE_RADIUS - WALL, lo)]
        n = FOLDS * 2
        for k in range(n + 1):
            y = lo + (hi - lo) * k / n
            outer_r = CREASE_RADIUS if k % 2 == 0 else BELLOWS_RADIUS
            pts.append((max(2.0, outer_r - WALL), y))
        pts += [(0.0, hi), (0.0, lo)]
    else:
        # Include collars and alternating inward/outward pleats.
        pts = [(0.0, BASE_Y), (BASE_RADIUS, BASE_Y),
               (BASE_RADIUS, BASE_Y + CAP)]
        lo, hi = BASE_Y + CAP, top - CAP
        n = FOLDS * 2
        for k in range(n + 1):
            y = lo + (hi - lo) * k / n
            radius = CREASE_RADIUS if k % 2 == 0 else BELLOWS_RADIUS
            pts.append((radius, y))
        pts += [(BASE_RADIUS, top - CAP), (BASE_RADIUS, top), (0.0, top)]
    # Remove adjacent duplicates, preserve closed polygon endpoints as needed.
    clean = []
    for p in pts:
        if not clean or abs(p[0]-clean[-1][0])+abs(p[1]-clean[-1][1]) > 1e-8:
            clean.append(p)
    return clean


def revolved_solid(points):
    pids = [gmsh.model.occ.addPoint(r, y, 0) for r, y in points]
    edges = [gmsh.model.occ.addLine(pids[i], pids[(i+1) % len(pids)])
             for i in range(len(pids))]
    wire = gmsh.model.occ.addWire(edges)
    face = gmsh.model.occ.addPlaneSurface([wire])
    entities = gmsh.model.occ.revolve([(2, face)], 0, 0, 0, 0, 1, 0,
                                      2 * math.pi, numElements=[RADIAL_SEGMENTS])
    return [e for e in entities if e[0] == 3]


def setup_mesh():
    gmsh.option.setNumber("Mesh.MeshSizeMin", MESH_SIZE)
    gmsh.option.setNumber("Mesh.MeshSizeMax", MESH_SIZE)
    gmsh.option.setNumber("Mesh.Algorithm3D", 1)
    gmsh.option.setNumber("Mesh.ElementOrder", 1)
    gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)


def write_tetra_vtk(filename):
    """Write a minimal legacy VTK containing tetrahedra only (SOFA friendly)."""
    tags, coords, _ = gmsh.model.mesh.getNodes()
    index = {int(tag): i for i, tag in enumerate(tags)}
    points = coords.reshape((-1, 3))
    types, _, connectivity = gmsh.model.mesh.getElements(3)
    tets = []
    for typ, conn in zip(types, connectivity):
        # Gmsh type 4 is the linear four-node tetrahedron.
        if typ == 4:
            tets.extend([index[int(n)] for n in conn.reshape((-1, 4)).ravel()])
    with open(filename, "w", encoding="ascii") as f:
        f.write("# vtk DataFile Version 3.0\nAccordion tetrahedral volume\nASCII\n")
        f.write("DATASET UNSTRUCTURED_GRID\n")
        f.write(f"POINTS {len(points)} float\n")
        for x, y, z in points:
            f.write(f"{x:.9g} {y:.9g} {z:.9g}\n")
        count = len(tets) // 4
        f.write(f"CELLS {count} {count * 5}\n")
        for i in range(count):
            a, b, c, d = tets[4*i:4*i+4]
            f.write(f"4 {a} {b} {c} {d}\n")
        f.write(f"CELL_TYPES {count}\n")
        f.write("10\n" * count)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("accordion")
    setup_mesh()
    outer = revolved_solid(profile_points(False))
    chamber = revolved_solid(profile_points(True))
    gmsh.model.occ.cut(outer, chamber, removeObject=True, removeTool=True)
    gmsh.model.occ.synchronize()
    gmsh.model.mesh.generate(3)
    gmsh.model.mesh.setOrder(1)
    gmsh.write(str(OUT / "Accordion_Parametric.step"))
    gmsh.write(str(OUT / "Accordion_Surface.stl"))
    write_tetra_vtk(OUT / "Accordion_Volumetric.vtk")
    gmsh.finalize()

    # Export a separate closed cavity surface for SOFA's pressure constraint.
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("accordion_cavity")
    setup_mesh()
    revolved_solid(profile_points(True))
    gmsh.model.occ.synchronize()
    gmsh.model.mesh.generate(2)
    gmsh.write(str(OUT / "Accordion_Cavity.stl"))
    gmsh.finalize()


if __name__ == "__main__":
    main()
