"""Reward successful generation, readable outputs and a completed SOFA run."""
import ast
import ctypes
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time

SOURCE = Path("/app/AccordionGeneration.py")
TESTS = Path("/tests")
LOGS = Path("/logs/verifier")
OUTPUTS = ("Accordion_Parametric.step", "Accordion_Surface.stl",
           "Accordion_Volumetric.vtk", "Accordion_Cavity.stl")


def child_limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024, 8 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    if ctypes.CDLL(None).prctl(38, 1, 0, 0, 0) != 0:
        raise RuntimeError("Could not restrict the generator process")


def run_process(command, cwd, log, timeout, candidate=False):
    started = time.monotonic()
    env = {"PATH": "/opt/mesh-venv/bin:/opt/sofa/bin:/usr/bin:/bin", "HOME": "/home/candidate",
           "SOFA_ROOT": "/opt/sofa", "LD_LIBRARY_PATH": "/opt/sofa/lib:/opt/sofa/plugins/SoftRobots/lib",
           "OPENBLAS_NUM_THREADS": "1"}
    options = dict(user=10001, group=10001, extra_groups=(), preexec_fn=child_limits) if candidate else {}
    try:
        with log.open("wb") as stream:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                       start_new_session=True, **options)
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise TimeoutError(f"Process exceeded {timeout} seconds; see {log.name}")
        return {"exit_code": process.returncode, "wall_time_s": round(time.monotonic() - started, 3)}
    finally:
        if candidate:
            subprocess.run(["/usr/bin/pkill", "-KILL", "-u", "10001"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    os.chmod(LOGS, 0o700)
    started = time.monotonic()
    report = {"reward": 0, "checks": {"generation": False, "outputs": False, "scene": False},
              "generation": {}, "outputs": {}, "mesh_quality": {},
              "mesh_preview": {"status": "skipped"}, "scene": {}, "error": None}
    stage = "generation"
    work = Path(tempfile.mkdtemp(prefix="accordion-submitted-"))
    try:
        if SOURCE.is_symlink() or not SOURCE.is_file() or not 0 < SOURCE.stat().st_size <= 65536:
            raise ValueError("Provide /app/AccordionGeneration.py containing 1 byte to 64 KiB")
        code = SOURCE.read_text(encoding="utf-8-sig")
        ast.parse(code, filename=SOURCE.name)
        script = work / SOURCE.name
        script.write_text(code, encoding="utf-8")
        os.chown(work, 10001, 10001)
        os.chmod(work, 0o755)
        report["generation"].update(run_process([sys.executable, "-I", str(script)], work,
                                                LOGS / "generation.log", 45, candidate=True))
        if report["generation"]["exit_code"] != 0:
            raise RuntimeError("Generator exited unsuccessfully; see generation.log")
        report["checks"]["generation"] = True
        with tempfile.TemporaryDirectory(prefix="accordion-trusted-") as control_dir:
            control = Path(control_dir)
            stage = "outputs"
            output_report = control / "outputs.json"
            report["outputs"].update(run_process([sys.executable, "-I", str(TESTS / "mesh_checks.py"),
                                                 str(work), str(output_report)], control, LOGS / "outputs.log", 30))
            if output_report.is_file():
                report["outputs"].update(json.loads(output_report.read_text(encoding="utf-8")))
            report["checks"]["outputs"] = report["outputs"]["exit_code"] == 0 and bool(report["outputs"].get("passed"))
            if not report["checks"]["outputs"]:
                raise RuntimeError(report["outputs"].get("error", "Output checks failed; see outputs.log"))
            # Load only the required data, never the generated Python or agent scene.
            (control / "mesh").mkdir()
            for name in OUTPUTS:
                shutil.copyfile(work / "mesh" / name, control / "mesh" / name)
                os.chmod(control / "mesh" / name, 0o444)
            # Optional diagnostics run in their own process. A failure or timeout
            # here must not prevent SOFA from running or change the reward.
            quality_report = control / "quality.json"
            try:
                report["mesh_quality"].update(run_process(
                    [sys.executable, "-I", str(TESTS / "mesh_quality.py"), str(control), str(quality_report)],
                    control, LOGS / "quality.log", 20))
                if quality_report.is_file():
                    report["mesh_quality"].update(json.loads(quality_report.read_text(encoding="utf-8")))
                else:
                    report["mesh_quality"].update(status="unavailable", error="No quality report; see quality.log")
            except Exception as exc:
                report["mesh_quality"].update(status="unavailable", error=str(exc) or type(exc).__name__)
            preview = LOGS / "mesh.png"
            try:
                report["mesh_preview"].update(run_process(
                    ["/usr/bin/env", "LIBGL_ALWAYS_SOFTWARE=1", "LP_NUM_THREADS=1", "/usr/bin/xvfb-run", "-a",
                     "--server-args=-screen 0 1280x1024x24 -nolisten tcp",
                     sys.executable, "-I", str(TESTS / "mesh_preview.py"), str(control), str(preview)],
                    control, LOGS / "preview.log", 15))
                if report["mesh_preview"]["exit_code"] != 0 or not preview.is_file() or preview.stat().st_size == 0:
                    raise RuntimeError("No mesh preview; see preview.log")
                report["mesh_preview"].update(status="ok", file=preview.name)
            except Exception as exc:
                preview.unlink(missing_ok=True)
                report["mesh_preview"].update(status="unavailable", error=str(exc) or type(exc).__name__)
            stage = "scene"
            scene_report = control / "scene.json"
            report["scene"].update(run_process([sys.executable, "-I", str(TESTS / "run_scene.py"),
                                               "--scene", str(TESTS / "SurfacePressureConstraint_Accordion.py"),
                                               "--workdir", str(control), "--output", str(scene_report)],
                                              control, LOGS / "scene.log", 60))
            if scene_report.is_file():
                report["scene"].update(json.loads(scene_report.read_text(encoding="utf-8")))
            report["checks"]["scene"] = report["scene"]["exit_code"] == 0 and bool(report["scene"].get("passed"))
            if not report["checks"]["scene"]:
                raise RuntimeError(report["scene"].get("error", "SOFA check failed; see scene.log"))
        report["reward"] = int(all(report["checks"].values()))
    except (Exception, SystemExit) as exc:
        report["error"] = stage + ": " + (str(exc) or type(exc).__name__)
    finally:
        generated = LOGS / "generated"
        generated.mkdir(exist_ok=True)
        if not (work / "mesh").is_symlink():
            for name in OUTPUTS:
                path = work / "mesh" / name
                if path.is_file() and not path.is_symlink() and path.stat().st_size <= 8 * 1024 * 1024:
                    shutil.copyfile(path, generated / name)
        shutil.rmtree(work)
    report["wall_time_s"] = round(time.monotonic() - started, 3)
    (LOGS / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    (LOGS / "reward.txt").write_text(str(report["reward"]) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
