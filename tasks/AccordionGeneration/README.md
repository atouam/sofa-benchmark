# AccordionGeneration

A Harbor task for generating an accordion soft actuator with Gmsh and running it in a supplied SOFA pressure scene. The model chooses the geometry and parameterization.

The full model-facing instructions are in [instruction.md](instruction.md). Benchmark setup and results are in the [project README](../../README.md).

## Submission

Write a standalone script at `/app/AccordionGeneration.py`. It must run headlessly without arguments and generate these files in `mesh/`:

| File | Content |
| --- | --- |
| `Accordion_Parametric.step` | CAD geometry |
| `Accordion_Surface.stl` | Triangular actuator surface |
| `Accordion_Volumetric.vtk` | Material volume with first-order tetrahedra |
| `Accordion_Cavity.stl` | Triangular surface for the pressure constraint |

Use millimetres and expose named parameters with working defaults. Inspect `/app/SurfacePressureConstraint_Accordion.py` to determine compatibility requirements; keep the scene unchanged.

The model has **600 seconds**. Generation must finish within **45 seconds**. Source size is limited to **64 KiB**, each output to **8 MiB**, the volume to **5,000 vertices / 30,000 tetrahedra**, and each STL to **10,000 vertices / 30,000 triangles**.

## Verifier and reward

Harbor transfers the submitted generator to a separate verifier container. The verifier:

1. Runs the generator in a fresh directory.
2. Reads the four outputs with Gmsh. Files must be nonempty and within the limits, with finite coordinates, valid vertex references and the required element types. The STEP file must contain readable geometry.
3. Initializes the fixed SOFA scene and runs **20 timesteps** at `dt=0.01 s` (**0.2 seconds** of simulated time).

The scene must load a nonempty body and cavity, select body vertices for fixation, and contain one `SurfacePressureConstraint`. Components must remain valid and body/cavity positions and velocities must remain finite. SOFA Error/Fatal messages cause failure; warnings are recorded.

**Reward is 1 when generation, output checks and simulation all pass; otherwise 0.** Displacement has no minimum target. Quality and preview failures do not change the reward.

This POC checks execution and simulation compatibility. It does not grade visual resemblance, regeneration after parameter changes, cavity closure/orientation, or physical accuracy.

## Recorded diagnostics

[mesh_quality.py](tests/mesh_quality.py) uses Gmsh's `getElementQualities()`:

| Mesh | Measures |
| --- | --- |
| Volume | `minSICN`, `minDetJac` |
| Surface and cavity | `minSICN` |

Each measure records **minimum / mean**, plus counts of non-finite and non-positive values. There is no quality threshold in the reward.

On a successful simulation, `report.json` also records:

- `scene.max_displacement_mm`: the largest distance any body vertex moved between its initial position and its final position. This is measured at the final timestep.
- Completed steps, simulated time and the final pressure-constraint value.
- Body vertex/tetrahedron counts and cavity triangle count.
- SOFA errors and warnings. Process exit codes and execution times are recorded for each stage.

`mesh.png` shows the generated actuator surface before simulation, with triangle edges and a fixed camera. Gmsh renders it using Xvfb and software OpenGL. Quality reporting has a 20-second limit; rendering has a 15-second limit. Both run after output checks pass and are optional diagnostics.

## Run and inspect

Run commands from the **project root**, after completing the setup in the [project README](../../README.md).

Test the reference solution with Harbor's oracle agent:

```bash
uv run harbor run -p tasks/AccordionGeneration -a oracle --job-name accordion-oracle
```

Run the configured model/harness comparison:

```bash
uv run harbor run -c benchmark.yaml --env-file .env
```

During a model attempt, these commands run generation and the local scene check from `/app`:

```bash
python AccordionGeneration.py
python run_scene.py
```

Harbor's verifier additionally regenerates the submission and checks all four outputs.

Open saved runs with:

```bash
uv run harbor view jobs
```

A trial's **Verifier** tab contains `report.json`, `reward.txt`, stage logs, `mesh.png` when available, and regenerated files under `generated/`.

To add a run's table to the project README:

```bash
uv run python export_results.py jobs/YOUR_JOB_FOLDER
```

The exporter updates the marked results section in the project README, writes `results.md`, and copies preview images into `results-images/`.

## Task files

| Path | Purpose |
| --- | --- |
| [instruction.md](instruction.md) | Model-facing task |
| [task.toml](task.toml) | Runtime limits and separate-verifier configuration |
| [environment/](environment/) | Agent Dockerfile, supplied scene and local runner |
| [tests/](tests/) | Verifier Dockerfile, protected scene, checks and diagnostics |
| [solution/](solution/) | Reference generator and oracle entry point |

Both Dockerfiles build from Ubuntu 24.04 and install the official SOFA **26.06** release, Python **3.12**, Gmsh **4.15.2** and NumPy **2.5.3**. The SOFA download is checked against its SHA-256. Tutorial examples are removed from the images, and the reference solution is supplied only to the oracle.
