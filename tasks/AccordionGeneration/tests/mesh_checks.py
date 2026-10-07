"""Check required output formats and limits before loading them into SOFA."""
import argparse
import json
from pathlib import Path

import gmsh
import numpy as np

OUTPUTS = ("Accordion_Parametric.step", "Accordion_Surface.stl",
           "Accordion_Volumetric.vtk", "Accordion_Cavity.stl")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_mesh(path, cell_type, max_vertices, max_elements):
    gmsh.initialize(readConfigFiles=False)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.open(str(path))
        node_tags, coordinates, _ = gmsh.model.mesh.getNodes()
        types, element_tags, element_nodes = gmsh.model.mesh.getElements()
        expected_type = {"tetra": 4, "triangle": 2}[cell_type]
        require(len(node_tags) > 0 and np.isfinite(coordinates).all(),
                f"Empty or non-finite coordinates: {path.name}")
        require(all(int(t) == expected_type for t in types),
                f"Expected {cell_type} elements only: {path.name}")
        count = sum(len(tags) for tags in element_tags)
        require(count > 0, f"Empty mesh: {path.name}")
        require(len(node_tags) <= max_vertices and count <= max_elements,
                f"Mesh exceeds task limits: {path.name}")
        for nodes in element_nodes:
            require(np.isin(nodes, node_tags).all(), f"Invalid vertex indices: {path.name}")
        return {"vertices": len(node_tags), "elements": count, "element_type": cell_type}
    finally:
        gmsh.finalize()


def check_outputs(work):
    folder = Path(work) / "mesh"
    require(folder.is_dir() and not folder.is_symlink(), "Provide a regular mesh/ directory")
    for name in OUTPUTS:
        path = folder / name
        require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 8 * 1024 * 1024,
                f"Missing, empty, oversized or symlinked mesh/{name}")

    metrics = {}
    for name, cell_type, vertices, elements in [
        ("Accordion_Volumetric.vtk", "tetra", 5000, 30000),
        ("Accordion_Surface.stl", "triangle", 10000, 30000),
        ("Accordion_Cavity.stl", "triangle", 10000, 30000),
    ]:
        metrics[name] = read_mesh(folder / name, cell_type, vertices, elements)

    gmsh.initialize(readConfigFiles=False)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("submitted_cad")
        entities = gmsh.model.occ.importShapes(str(folder / "Accordion_Parametric.step"))
        require(bool(entities), "STEP contains no readable geometry")
        metrics["Accordion_Parametric.step"] = {"imported_entities": len(entities)}
    finally:
        gmsh.finalize()
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = {"passed": False}
    try:
        report.update(metrics=check_outputs(args.workdir), passed=True)
    except Exception as exc:
        report["error"] = str(exc) or type(exc).__name__
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(report, indent=2, allow_nan=False))
    raise SystemExit(0 if report["passed"] else 1)
