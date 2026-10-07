"""Render the regenerated surface mesh as a diagnostic PNG with Gmsh."""
import argparse
from pathlib import Path

import gmsh


def render(workdir, output):
    gmsh.initialize(readConfigFiles=False)
    try:
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.open(str(workdir / "mesh" / "Accordion_Surface.stl"))
        for name, value in {
            "General.GraphicsWidth": 1000,
            "General.GraphicsHeight": 800,
            "General.BackgroundGradient": 0,
            "General.Trackball": 0,
            "General.RotationX": 55,
            "General.RotationY": 0,
            "General.RotationZ": 45,
            "General.Orthographic": 1,
            "General.Axes": 0,
            "General.SmallAxes": 1,
            "Geometry.Points": 0,
            "Geometry.Curves": 0,
            "Geometry.Surfaces": 0,
            "Mesh.Points": 0,
            "Mesh.SurfaceFaces": 1,
            "Mesh.SurfaceEdges": 1,
            "Print.Background": 1,
        }.items():
            gmsh.option.setNumber(name, value)
        gmsh.option.setColor("General.Color.Background", 255, 255, 255)
        gmsh.option.setColor("General.Color.Foreground", 40, 40, 40)
        gmsh.fltk.initialize()
        gmsh.fltk.update()
        gmsh.graphics.draw()
        gmsh.write(str(output))
    finally:
        gmsh.finalize()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.workdir, args.output)
