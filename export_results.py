"""Export mesh results and update the README results section."""

import argparse
import json
from pathlib import Path
import shutil


RESULTS_START = "<!-- benchmark-results:start -->"
RESULTS_END = "<!-- benchmark-results:end -->"


def update_readme(readme: Path, results: str) -> None:
    content = readme.read_text(encoding="utf-8") if readme.exists() else ""
    block = f"{RESULTS_START}\n{results.rstrip()}\n{RESULTS_END}"
    if (RESULTS_START in content) != (RESULTS_END in content):
        raise ValueError("README results markers must appear as a pair.")
    if RESULTS_START in content:
        before, rest = content.split(RESULTS_START, 1)
        _, after = rest.split(RESULTS_END, 1)
        content = before + block + after
    else:
        content = content.rstrip() + "\n\n" + block + "\n"
    readme.write_text(content, encoding="utf-8")


def format_mesh_quality(report_file: Path) -> str:
    if not report_file.is_file():
        return "—"

    report = json.loads(report_file.read_text(encoding="utf-8"))
    meshes = (report.get("mesh_quality") or {}).get("meshes", {})
    measurements = []
    for filename, label in (
        ("Accordion_Volumetric.vtk", "Volume"),
        ("Accordion_Surface.stl", "Surface"),
        ("Accordion_Cavity.stl", "Cavity"),
    ):
        for measure, stats in meshes.get(filename, {}).get("measures", {}).items():
            values = " / ".join(
                f"{stats[key]:.3g}" if stats.get(key) is not None else "—"
                for key in ("minimum", "mean")
            )
            measurements.append(f"{label} {measure}: {values}")
    return "<br>".join(measurements) or "—"


def export_results(job: Path, output: Path = Path("results.md")) -> Path:
    job, output = Path(job), Path(output)
    result_files = sorted(job.glob("*/result.json"))
    if not result_files:
        raise ValueError(f"No trial result.json files found in {job}")
    lines = [
        "## Benchmark results",
        "",
        f"Job: `{job.name}`",
        "",
        "| Harness | Model | Reward | Mesh quality | Mesh preview |",
        "| --- | --- | --- | --- | --- |",
    ]

    for result_file in result_files:
        result = json.loads(result_file.read_text(encoding="utf-8"))
        agent = result["config"]["agent"]
        harness = agent.get("name") or "—"
        model = agent.get("model_name") or "Reference solution"
        rewards = (result.get("verifier_result") or {}).get("rewards") or {}
        reward = rewards.get("reward")
        reward_text = f"{reward:g}" if reward is not None else "—"
        quality = format_mesh_quality(result_file.parent / "verifier" / "report.json")

        preview = result_file.parent / "verifier" / "mesh.png"
        image = "—"
        if preview.is_file():
            relative = Path("results-images") / result_file.parent.parent.name / f"{result_file.parent.name}.png"
            destination = output.parent / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(preview, destination)
            image = f'<img src="{relative.as_posix()}" width="180" alt="Mesh preview">'

        row = f"| {harness} | {model} | {reward_text} | {quality} | {image} |"
        if harness == "oracle":
            lines.insert(6, row)
        else:
            lines.append(row)

    lines.extend([
        "",
        "Mesh quality values are **minimum / mean**, from Gmsh. "
        "These diagnostics do not change the reward. Missing results appear as `—`.",
    ])
    output.parent.mkdir(parents=True, exist_ok=True)
    results = "\n".join(lines) + "\n"
    output.write_text(results, encoding="utf-8")
    update_readme(output.parent / "README.md", results)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path, help="Harbor job folder")
    parser.add_argument("-o", "--output", type=Path, default=Path("results.md"))
    args = parser.parse_args()
    print(f"Wrote {export_results(args.job, args.output)} and updated {args.output.parent / 'README.md'}")
