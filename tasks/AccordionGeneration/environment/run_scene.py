"""Check the supplied SOFA pressure scene using meshes in WORKDIR/mesh/."""
import argparse
import importlib.util
import json
import os
from pathlib import Path


def run_scene(scene, workdir, steps=20, dt=0.01):
    import numpy as np
    import Sofa.Core
    import Sofa.Helper
    import Sofa.Simulation

    report = {"passed": False, "errors": [], "warnings": [], "steps": 0}
    root = None

    class Collector(Sofa.Helper.MessageHandler):
        def process(self, message):
            severity = message["type"]
            if severity not in ("Error", "Fatal", "Warning"):
                return
            field = "warnings" if severity == "Warning" else "errors"
            text = f'{message["sender"]}: {message["message"]}'
            if text not in report[field] and len(report[field]) < 20:
                report[field].append(text)

    def check_components(node):
        for obj in node.objects:
            state = obj.findData("componentState")
            if state is not None and str(state.value) == "Invalid":
                raise RuntimeError(f"Invalid SOFA component: {obj.getPathName()}")
        for child in node.children:
            check_components(child)

    try:
        scene = Path(scene).resolve()
        workdir = Path(workdir).resolve()
        for name in ("Accordion_Volumetric.vtk", "Accordion_Cavity.stl"):
            mesh = workdir / "mesh" / name
            if not mesh.is_file() or not mesh.stat().st_size:
                raise ValueError(f"Generate mesh/{name} before running the scene")
        os.chdir(workdir)
        spec = importlib.util.spec_from_file_location("fixed_accordion_scene", scene)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = Sofa.Core.Node("root")
        root.dt = dt
        root.gravity = [0, 0, 0]
        with Collector():
            module.createScene(root)
            Sofa.Simulation.init(root)
            body, cavity = root.bunny, root.bunny.cavity
            tetrahedra = len(body.container.tetrahedra.value)
            triangles = len(cavity.topo.triangles.value)
            if not tetrahedra or not triangles:
                raise RuntimeError("Scene loaded an empty body or cavity")
            if not len(body.boxROI.indices.value):
                raise RuntimeError("The fixation box selected no body vertices")
            pressure = [obj for obj in cavity.objects if obj.getClassName() == "SurfacePressureConstraint"]
            if len(pressure) != 1:
                raise RuntimeError("Expected one active SurfacePressureConstraint")
            rest = np.array(body.tetras.position.value, copy=True)
            if not len(rest) or not np.isfinite(rest).all():
                raise RuntimeError("Invalid initial mechanical state")
            check_components(root)
            if report["errors"]:
                raise RuntimeError("SOFA initialization reported errors")
            for index in range(steps):
                Sofa.Simulation.animate(root, dt)
                for mechanical in (body.tetras, cavity.cavity):
                    if not np.isfinite(mechanical.position.value).all() or not np.isfinite(mechanical.velocity.value).all():
                        raise RuntimeError("Non-finite state during simulation")
                check_components(root)
                if report["errors"]:
                    raise RuntimeError("SOFA animation reported errors")
                report["steps"] = index + 1
            current = np.asarray(body.tetras.position.value)
            displacement = float(np.linalg.norm(current - rest, axis=1).max())
            if not np.isfinite(displacement):
                raise RuntimeError("Non-finite simulation displacement")
            report.update(passed=True, vertices=len(rest), tetrahedra=tetrahedra,
                          cavity_triangles=triangles, time_s=float(root.time.value),
                          pressure_value=np.asarray(pressure[0].value.value).reshape(-1).tolist(),
                          max_displacement_mm=displacement)
    except (Exception, SystemExit) as exc:
        report["error"] = str(exc) or type(exc).__name__
    finally:
        if root is not None:
            Sofa.Simulation.unload(root)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, default=Path(__file__).with_name("SurfacePressureConstraint_Accordion.py"))
    parser.add_argument("--workdir", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=Path("scene_report.json"))
    args = parser.parse_args()
    output = args.output.resolve()
    result = run_scene(args.scene, args.workdir.resolve())
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(0 if result["passed"] else 1)
