Write a standalone, parametric Gmsh Python script at `/app/AccordionGeneration.py` that generates an accordion-shaped soft actuator compatible with the provided SOFA scene at `/app/SurfacePressureConstraint_Accordion.py`.

Choose the geometry and parameterization yourself. Expose clearly named parameters with working defaults. Changing those parameters must regenerate the corresponding CAD geometry and meshes.

Inspect the supplied scene to determine its mesh and simulation requirements. Keep the scene unchanged.

Your script must run headlessly without arguments, create a `mesh/` directory in its working directory, and write the following files inside it:

- `Accordion_Parametric.step`: the actuator’s CAD geometry.
- `Accordion_Surface.stl`: the actuator’s triangular surface mesh.
- `Accordion_Volumetric.vtk`: the material volume, containing first-order tetrahedra only.
- `Accordion_Cavity.stl`: the triangular surface used by the scene’s pressure constraint.

Use millimetres for all geometry and mesh coordinates. Gmsh and NumPy are installed.

**SOFA version:** 26.06.

**Validation:** the verifier reruns your generator in a fresh directory, checks that the required outputs are readable by Gmsh and within the declared limits, and runs the supplied scene for 20 timesteps at `dt=0.01 s`. Success requires successful generation, scene initialization and simulation, finite mechanical states, and no SOFA Error/Fatal diagnostics. Gmsh element-quality metrics are recorded as diagnostics and do not affect the reward. You may test locally with `python run_scene.py`.

**Limits:** generation must finish within 45 seconds. Source size is limited to 64 KiB and each output to 8 MiB. The volume mesh may contain at most 5,000 vertices and 30,000 tetrahedra; each STL may contain at most 10,000 vertices and 30,000 triangles.

**Scope:** implement the generator. Do not copy pre-existing generators or meshes, or use online solutions specific to this task. Do not access files or process state outside `/app` unless required by the installed tools.

You have **600 seconds** to complete the task.
