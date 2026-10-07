"""Headless parametric hollow accordion for SurfacePressureConstraint_Accordion.py.

Run: python AccordionGeneration.py (outputs are relative to the working directory).
All lengths and mesh coordinates are millimetres. Edit PARAMETERS to regenerate.
The actuator axis is +Y; the base intersects the scene's fixed BoxROI. Each
bellows is a pair of conical flanks. The sealed air chamber follows the folds
with a radial wall thickness, and has solid bottom and top end caps.

Requires Gmsh and NumPy. No scene changes, GUI, or input meshes are needed.
"""
from pathlib import Path
import math
import struct
import gmsh
import numpy as np

# The position of the base is chosen for the supplied scene's fixation box.
PARAMETERS = dict(
    fold_count=4,                 # integer number of complete bellows
    fold_pitch_mm=5.0,            # axial length of each bellows
    valley_radius_mm=8.0,         # external radius at fold valleys
    crest_radius_mm=10.0,         # external radius at fold crests
    radial_wall_thickness_mm=4.0, # radial separation of conical surfaces
    base_y_mm=-6.0,               # lowest material coordinate
    base_height_mm=6.0,           # straight cylindrical base, up to y=0
    bottom_cap_thickness_mm=3.0,
    top_height_mm=3.0,            # cylindrical section above the folds
    top_cap_thickness_mm=2.5,
    mesh_size_mm=2.3,             # characteristic first-order tetrahedron size
)


def check_parameters(p):
    n = p['fold_count']
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError('fold_count must be a positive integer')
    for key, value in p.items():
        if not math.isfinite(value):
            raise ValueError(f'{key} must be finite')
        if key not in ('base_y_mm', 'fold_count') and value <= 0:
            raise ValueError(f'{key} must be positive')
    if not p['crest_radius_mm'] > p['valley_radius_mm'] > p['radial_wall_thickness_mm']:
        raise ValueError('Require crest radius > valley radius > wall thickness')
    if p['bottom_cap_thickness_mm'] >= p['base_height_mm']:
        raise ValueError('Bottom cap must be thinner than the base height')
    if p['top_cap_thickness_mm'] >= p['top_height_mm']:
        raise ValueError('Top cap must be thinner than the top height')
    # The scene is unchanged: retain at least part of the base in its fixed box.
    if not (p['base_y_mm'] < -3 and p['base_y_mm'] + p['base_height_mm'] > -7):
        raise ValueError('Base must intersect the scene fixation region y=[-7,-3]')
    if p['valley_radius_mm'] > 15:
        raise ValueError('Base radius must fit the scene fixation box (<=15 mm)')


def revolved_solid(profile):
    """Revolve an (r,y) outline, closed against the Y axis, into one solid."""
    occ = gmsh.model.occ
    outline = [(0.0, profile[0][1])] + profile + [(0.0, profile[-1][1])]
    points = [occ.addPoint(r, y, 0) for r, y in outline]
    edges = [occ.addLine(points[i], points[(i + 1) % len(points)])
             for i in range(len(points))]
    face = occ.addPlaneSurface([occ.addCurveLoop(edges)])
    entities = occ.revolve([(2, face)], 0, 0, 0, 0, 1, 0, 2 * math.pi)
    return next(tag for dim, tag in entities if dim == 3)


def write_stl(path, triangles, coordinates):
    """Binary STL preserves small file sizes and works with SOFA's STL loader."""
    with path.open('wb') as stream:
        stream.write(b'Accordion mesh; coordinates in millimetres'.ljust(80, b'\0'))
        stream.write(struct.pack('<I', len(triangles)))
        for tri in triangles:
            xyz = coordinates[tri]
            normal = np.cross(xyz[1] - xyz[0], xyz[2] - xyz[0])
            normal /= np.linalg.norm(normal)
            stream.write(struct.pack('<12fH', *normal, *xyz.ravel(), 0))


def generate(p=PARAMETERS):
    check_parameters(p)
    out = Path.cwd() / 'mesh'
    out.mkdir(parents=True, exist_ok=True)
    gmsh.initialize()
    try:
        gmsh.option.setNumber('General.Terminal', 1)
        gmsh.option.setNumber('General.NumThreads', 1)
        gmsh.model.add('Parametric sealed accordion')
        y0 = p['base_y_mm']
        start = y0 + p['base_height_mm']
        radius = p['valley_radius_mm']
        wall = p['radial_wall_thickness_mm']
        folds = [(radius, start)]
        for i in range(p['fold_count']):
            folds.extend([(p['crest_radius_mm'], start + (i + 0.5) * p['fold_pitch_mm']),
                          (radius, start + (i + 1) * p['fold_pitch_mm'])])
        end = folds[-1][1] + p['top_height_mm']
        outer_profile = [(radius, y0)] + folds + [(radius, end)]
        inner_profile = [(radius - wall, y0 + p['bottom_cap_thickness_mm'])]
        inner_profile += [(r - wall, y) for r, y in folds]
        inner_profile += [(radius - wall, end - p['top_cap_thickness_mm'])]
        outer = revolved_solid(outer_profile)
        chamber = revolved_solid(inner_profile)
        # Retain the tool temporarily so its shared boundary can be identified
        # without geometric tolerance guesses, then remove only its volume.
        result, _ = gmsh.model.occ.cut([(3, outer)], [(3, chamber)],
                                      removeObject=True, removeTool=False)
        gmsh.model.occ.synchronize()
        material = [tag for dim, tag in result if dim == 3]
        if len(material) != 1:
            raise RuntimeError('Expected a single connected actuator material volume')
        cavity_surfaces = {tag for dim, tag in gmsh.model.getBoundary(
            [(3, chamber)], oriented=False) if dim == 2}
        material_surfaces = {tag for dim, tag in gmsh.model.getBoundary(
            [(3, material[0])], oriented=False) if dim == 2}
        if not cavity_surfaces.issubset(material_surfaces):
            raise RuntimeError('The chamber must share its complete boundary with material')
        gmsh.model.occ.remove([(3, chamber)], recursive=False)
        gmsh.model.occ.synchronize()
        # Full-turn revolutions can leave their generating meridian faces.
        # Export and mesh only the solid and its actual boundary entities.
        orphan_surfaces = [(2, tag) for _, tag in gmsh.model.getEntities(2)
                           if tag not in material_surfaces]
        if orphan_surfaces:
            gmsh.model.occ.remove(orphan_surfaces, recursive=True)
            gmsh.model.occ.synchronize()
        gmsh.write(str(out / 'Accordion_Parametric.step'))
        gmsh.option.setNumber('Mesh.MeshSizeMin', p['mesh_size_mm'])
        gmsh.option.setNumber('Mesh.MeshSizeMax', p['mesh_size_mm'])
        gmsh.option.setNumber('Mesh.MeshSizeFromCurvature', 0)
        gmsh.option.setNumber('Mesh.ElementOrder', 1)
        gmsh.option.setNumber('Mesh.Algorithm', 6)
        gmsh.option.setNumber('Mesh.Algorithm3D', 1)
        gmsh.option.setNumber('Mesh.Optimize', 1)
        gmsh.model.mesh.generate(3)

        tags, xyz, _ = gmsh.model.mesh.getNodes()
        xyz = np.asarray(xyz).reshape(-1, 3)
        index = {int(tag): i for i, tag in enumerate(tags)}
        types, _, connectivity = gmsh.model.mesh.getElements(3)
        if list(types) != [4]:
            raise RuntimeError('Only first-order tetrahedra are allowed')
        tetrahedra = np.array([[index[int(t)] for t in cell] for cell in
                              np.asarray(connectivity[0]).reshape(-1, 4)], dtype=np.int64)
        # Compact away any nodes not referenced by the material volume.
        used = np.unique(tetrahedra)
        compact = np.full(len(xyz), -1, dtype=np.int64)
        compact[used] = np.arange(len(used))
        tetrahedra = compact[tetrahedra]
        xyz = xyz[used]
        node_index = {tag: int(compact[i]) for tag, i in index.items()}
        # Build boundary face ownership. An opposite material vertex determines
        # the normal unambiguously, including the sloping bellows and end caps.
        faces = {}
        for cell in tetrahedra:
            for j in range(4):
                face = tuple(sorted(np.delete(cell, j)))
                if face in faces:
                    faces[face] = None
                else:
                    faces[face] = int(cell[j])
        surfaces, cavity = [], []
        for surface in sorted(material_surfaces):
            stypes, _, sconn = gmsh.model.mesh.getElements(2, surface)
            if list(stypes) != [2]:
                raise RuntimeError('Expected first-order triangular surfaces')
            for nodes in np.asarray(sconn[0]).reshape(-1, 3):
                tri = np.array([node_index[int(t)] for t in nodes])
                opposite = faces.get(tuple(sorted(tri)))
                if opposite is None:
                    raise RuntimeError('Surface triangle is not a tetrahedron boundary face')
                a, b, c = xyz[tri]
                into_material = np.dot(np.cross(b-a, c-a), xyz[opposite]-a) > 0
                if into_material:
                    tri = tri[[0, 2, 1]]
                surfaces.append(tri)
                if surface in cavity_surfaces:
                    # Chamber outward normal points into the surrounding rubber.
                    cavity.append(tri[[0, 2, 1]])
        surfaces = np.asarray(surfaces)
        cavity = np.asarray(cavity)
        if len(xyz) > 5000 or len(tetrahedra) > 30000:
            raise ValueError('Volume budget exceeded; increase mesh_size_mm')
        for triangles in (surfaces, cavity):
            if len(triangles) > 30000 or len(np.unique(triangles)) > 10000:
                raise ValueError('STL budget exceeded; increase mesh_size_mm')
        chamber_xyz = xyz[cavity]
        signed_volume = np.sum(np.einsum('ij,ij->i', chamber_xyz[:, 0],
                              np.cross(chamber_xyz[:, 1], chamber_xyz[:, 2]))) / 6
        if signed_volume <= 0:
            raise RuntimeError('Cavity must enclose a positive outward-oriented volume')
        # Explicit legacy VTK writer excludes triangles, lines, and CAD vertices.
        with (out / 'Accordion_Volumetric.vtk').open('w') as stream:
            stream.write('# vtk DataFile Version 3.0\nAccordion material in mm\nASCII\nDATASET UNSTRUCTURED_GRID\n')
            stream.write(f'POINTS {len(xyz)} double\n')
            np.savetxt(stream, xyz, fmt='%.12g')
            stream.write(f'CELLS {len(tetrahedra)} {5 * len(tetrahedra)}\n')
            np.savetxt(stream, np.column_stack((np.full(len(tetrahedra), 4), tetrahedra)), fmt='%d')
            stream.write(f'CELL_TYPES {len(tetrahedra)}\n')
            stream.write('10\n' * len(tetrahedra))
        write_stl(out / 'Accordion_Surface.stl', surfaces, xyz)
        write_stl(out / 'Accordion_Cavity.stl', cavity, xyz)
        for path in out.glob('Accordion_*'):
            if path.stat().st_size > 8 * 1024 * 1024:
                raise RuntimeError(f'Output exceeds 8 MiB: {path.name}')
        print(f'Generated {len(xyz)} vertices, {len(tetrahedra)} tetrahedra, '
              f'{len(surfaces)} material boundary triangles, {len(cavity)} cavity triangles; '
              f'cavity volume {signed_volume:.3f} mm^3')
    finally:
        gmsh.finalize()


if __name__ == '__main__':
    generate()
