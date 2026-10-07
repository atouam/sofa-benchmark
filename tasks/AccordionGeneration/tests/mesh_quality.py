"""Record Gmsh element-quality diagnostics; these never determine the reward."""
import argparse
import json
from pathlib import Path

import gmsh
import numpy as np


def summarize(values):
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    return {
        "count": len(values),
        "non_finite_count": int(len(values) - len(finite)),
        "non_positive_count": int(np.count_nonzero(finite <= 0)),
        "minimum": float(finite.min()) if len(finite) else None,
        "mean": float(finite.mean()) if len(finite) else None,
    }


def measure_file(path, dimension, measures):
    gmsh.initialize(readConfigFiles=False)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.open(str(path))
        _, blocks, _ = gmsh.model.mesh.getElements(dimension)
        tags = np.concatenate(blocks) if blocks else np.array([], dtype=np.uint64)
        if not len(tags):
            raise ValueError("Gmsh loaded no elements")
        return {"dimension": dimension, "elements": len(tags), "measures": {
            metric: summarize(gmsh.model.mesh.getElementQualities(tags.tolist(), metric))
            for metric in measures
        }}
    finally:
        gmsh.finalize()


def measure(work):
    report = {"status": "ok", "meshes": {}}
    for name, dimension, measures in [
        ("Accordion_Volumetric.vtk", 3, ("minDetJac", "minSICN")),
        ("Accordion_Surface.stl", 2, ("minSICN",)),
        ("Accordion_Cavity.stl", 2, ("minSICN",)),
    ]:
        try:
            # Fresh Gmsh state for each file prevents an import failure from
            # affecting the diagnostics for the following files.
            report["meshes"][name] = measure_file(Path(work) / "mesh" / name, dimension, measures)
        except Exception as exc:
            report["meshes"][name] = {"dimension": dimension, "error": str(exc) or type(exc).__name__}
            report["status"] = "partial"
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        result = measure(args.workdir)
    except Exception as exc:
        result = {"status": "unavailable", "error": str(exc) or type(exc).__name__}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
