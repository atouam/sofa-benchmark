# SOFA mesh benchmark

Compare models and coding harnesses on one task: generate a parametric mesh for an accordion soft actuator that works in a supplied SOFA scene.

Harbor runs each model through its harness, collects the submitted Python script, and evaluates it with the same verifier. The reference solution runs as an oracle in the same job.

## The task

The model writes `/app/AccordionGeneration.py` using Gmsh. It chooses the geometry and parameters, inspects the supplied `SurfacePressureConstraint_Accordion.py`, and generates four files in `mesh/`:

| File | Purpose |
| --- | --- |
| `Accordion_Parametric.step` | CAD geometry |
| `Accordion_Surface.stl` | Actuator surface mesh |
| `Accordion_Volumetric.vtk` | First-order tetrahedral material mesh |
| `Accordion_Cavity.stl` | Pressure cavity surface |

The generator runs headlessly, without arguments, using millimetres. The SOFA scene stays unchanged. The complete task and limits are in [instruction.md](tasks/AccordionGeneration/instruction.md).

## Evaluation

1. A separate verifier container receives the submitted generator and runs it in a fresh directory, with a 45-second limit.
2. Gmsh checks that the required outputs are readable and satisfy the file, mesh-size and element-type requirements.
3. The fixed SOFA **26.06** scene initializes and runs **20 timesteps** at `dt=0.01 s`. Mechanical states must remain finite, with no SOFA Error/Fatal diagnostics.

**Reward is 1 when all three stages pass, otherwise 0.** It measures generation and simulation compatibility. Actuator appearance, parameter regeneration and physical accuracy are not graded; displacement is recorded without a minimum target.

Gmsh quality is reported as **minimum / mean**: `minSICN` for the volume, surface and cavity meshes, and `minDetJac` for the volume. A PNG shows the generated surface mesh before simulation. Quality and previews are diagnostics and do not affect the reward.

Both Dockerfiles install SOFA, Gmsh and NumPy directly.

## Run

Requirements: **uv**, **Python 3.14 or later**, and a running Docker engine using Linux containers.

From this folder:

```bash
uv sync
```

Copy `.env.example` to `.env`. Set `OPENROUTER_API_KEY` for the OpenCode and Pi entries. Codex uses your existing Codex login through `CODEX_AUTH_JSON_PATH`:

```dotenv
# Windows
CODEX_AUTH_JSON_PATH=${USERPROFILE}/.codex/auth.json
# WSL/Linux: use ${HOME}/.codex/auth.json instead
```

The home directory is resolved by dotenv. `.env` is ignored by Git.

```bash
uv run harbor run -c benchmark.yaml --env-file .env
```

[benchmark.yaml](benchmark.yaml) defines the comparison:

| Harness | Models |
| --- | --- |
| Oracle | Provided reference solution |
| Codex | GPT-6.1 Sol, GPT-6 Luna |
| OpenCode | DeepSeek V4.1 Flash, GLM 5.3 Flash through OpenRouter |
| Pi | DeepSeek V4.1 Flash, GLM 5.3 Flash through OpenRouter; Qwen3.5 9B through local LM Studio |

Add or remove entries under `agents` to change the comparison. The current configuration uses one attempt per entry, sequential trials, no automatic retries, and 600 seconds per model attempt. Increase `n_attempts` to repeat trials. SoftFingerDesign is an unfinished template and is not included.

For the local Qwen entry, keep LM Studio's server running on port `1234` with `qwen/qwen3.5-9b` available. The detected model is Q4_K_M. Pi uses LM Studio's [OpenAI-compatible Chat Completions API](https://lmstudio.ai/docs/developer/openai-compat). Its container connects through `http://host.docker.internal:1234/v1`, as described in [Docker's host networking guide](https://docs.docker.com/desktop/features/networking/networking-how-tos/#connect-a-container-to-a-service-on-the-host). The URL and placeholder API key are scoped to this entry. If LM Studio authentication is enabled, replace the placeholder with your server token.

## View and export

Each run is saved under `jobs/`. Open Harbor's viewer:

```bash
uv run harbor view jobs
```

In a trial's **Verifier** tab, open `mesh.png`, `report.json`, the logs or the regenerated files in `generated/`.

Export a job as a Markdown table:

```bash
uv run python export_results.py jobs/2026-10-07__02-53-39
```

The exporter writes [results.md](results.md), copies the previews into `results-images/`, and updates the marked results section in `README.md` automatically. The rest of the README is preserved. Replace the job path to export another run. Keep `results-images/` beside the README so the previews display in GitHub and VS Code. With `-o`, the report, images and README are written in the chosen output folder.

<!-- benchmark-results:start -->
## Benchmark results

Job: `2026-10-07__09-03-00`

| Harness | Model | Reward | Mesh quality | Mesh preview |
| --- | --- | --- | --- | --- |
| oracle | Reference solution | 1 | Volume minDetJac: 4.48 / 47.6<br>Volume minSICN: 0.273 / 0.808<br>Surface minSICN: 0.417 / 0.951<br>Cavity minSICN: 0.0595 / 0.467 | <img src="results-images/2026-10-07__09-03-00/AccordionGeneration__BgGjRT9.png" width="180" alt="Mesh preview"> |
| opencode | openrouter/deepseek/deepseek-v4.1-flash | 1 | Volume minDetJac: 0.211 / 2.72<br>Volume minSICN: 0.311 / 0.779<br>Surface minSICN: 0.729 / 0.954<br>Cavity minSICN: 0.729 / 0.949 | <img src="results-images/2026-10-07__09-03-00/AccordionGeneration__a2S7L5E.png" width="180" alt="Mesh preview"> |
| pi | qwen/qwen3.5-9b | 0 | — | — |
| codex | openai/gpt-6.1-sol | 1 | Volume minDetJac: 1.11 / 10.4<br>Volume minSICN: 0.202 / 0.742<br>Surface minSICN: 0.366 / 0.927<br>Cavity minSICN: 0.366 / 0.909 | <img src="results-images/2026-10-07__09-03-00/AccordionGeneration__NZoWJae.png" width="180" alt="Mesh preview"> |
| codex | openai/gpt-6-luna | 1 | Volume minDetJac: 2.99 / 15.5<br>Volume minSICN: 0.3 / 0.808<br>Surface minSICN: 0.665 / 0.936<br>Cavity minSICN: 0.845 / 0.965 | <img src="results-images/2026-10-07__09-03-00/AccordionGeneration__vvUBaeF.png" width="180" alt="Mesh preview"> |
| pi | openrouter/deepseek/deepseek-v4.1-flash | 1 | Volume minDetJac: 1.04 / 10.4<br>Volume minSICN: 0.346 / 0.764<br>Surface minSICN: 0.662 / 0.912<br>Cavity minSICN: 0.863 / 0.971 | <img src="results-images/2026-10-07__09-03-00/AccordionGeneration__XeaRSFQ.png" width="180" alt="Mesh preview"> |

Mesh quality values are **minimum / mean**, from Gmsh. These diagnostics do not change the reward. Missing results appear as `—`.
<!-- benchmark-results:end -->
