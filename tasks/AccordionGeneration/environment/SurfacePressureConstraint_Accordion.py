# Adapted from SoftRobots.DesignOptimization/GmshTutorial (AGPL-3.0).
# Updated plugin and solver names for SOFA 26.06.
import Sofa
from pathlib import Path

def createScene(rootNode):
    # The generator and runner use mesh/ in the selected working directory.
    mesh_dir = Path.cwd() / "mesh"

    rootNode.addObject('RequiredPlugin', pluginName=[
        'SoftRobots',
        'Sofa.Component.AnimationLoop',
        'Sofa.Component.Constraint.Lagrangian.Correction',
        'Sofa.Component.Constraint.Lagrangian.Solver',
        'Sofa.Component.Engine.Select',
        'Sofa.Component.IO.Mesh',
        'Sofa.Component.LinearSolver.Direct',
        'Sofa.Component.LinearSystem',
        'Sofa.Component.Mapping.Linear',
        'Sofa.Component.Mass',
        'Sofa.Component.ODESolver.Backward',
        'Sofa.Component.SolidMechanics.FEM.Elastic',
        'Sofa.Component.SolidMechanics.Spring',
        'Sofa.Component.StateContainer',
        'Sofa.Component.Topology.Container.Dynamic',
        'Sofa.Component.Topology.Container.Constant',
        'Sofa.Component.Topology.Mapping',
        'Sofa.Component.Visual',
        'Sofa.GL.Component.Rendering3D',
    ])
    rootNode.addObject('VisualStyle', displayFlags='showVisualModels hideBehaviorModels showCollisionModels hideBoundingCollisionModels showForceFields showInteractionForceFields hideWireframe')

    rootNode.addObject('FreeMotionAnimationLoop')
    rootNode.addObject('BlockGaussSeidelConstraintSolver', maxIterations=100, tolerance = 0.0000001)

    #bunny
    bunny = rootNode.addChild('bunny')
    bunny.addObject('EulerImplicitSolver', name='odesolver')
    bunny.addObject('SparseLDLSolver', name='preconditioner', template='CompressedRowSparseMatrixMat3x3d')

    bunny.addObject('MeshVTKLoader', name='loader', filename=str(mesh_dir / 'Accordion_Volumetric.vtk'))
    bunny.addObject('TetrahedronSetTopologyContainer', src='@loader', name='container')
    bunny.addObject('TetrahedronSetTopologyModifier')

    bunny.addObject('MechanicalObject', name='tetras', template='Vec3', showIndices=False)
    bunny.addObject('UniformMass', totalMass=0.5)
    bunny.addObject('TetrahedronFEMForceField', template='Vec3', name='FEM', method='large', poissonRatio=0.3,  youngModulus=18000)

    bunny.addObject('BoxROI', name='boxROI', box=[-15, -7, -15,  15, -3, 15], drawBoxes=True, position="@tetras.rest_position", tetrahedra="@container.tetrahedra")
    bunny.addObject('RestShapeSpringsForceField', points='@boxROI.indices', stiffness=1e12)

    bunny.addObject('LinearSolverConstraintCorrection', linearSolver='@preconditioner')
    #bunny.addObject('UncoupledConstraintCorrection')


    #bunny/cavity
    cavity = bunny.addChild('cavity')
    cavity.addObject('MeshSTLLoader', name='loader', filename=str(mesh_dir / 'Accordion_Cavity.stl'))
    cavity.addObject('MeshTopology', src='@loader', name='topo')
    cavity.addObject('MechanicalObject', name='cavity')
    cavity.addObject('SurfacePressureConstraint', triangles='@topo.triangles', value=16, valueType='pressure')
    cavity.addObject('BarycentricMapping', name='mapping',  mapForces=False, mapMasses=False)


    #bunny/bunnyVisu
    bunnyVisu = bunny.addChild('visu')
    bunnyVisu.addObject('TriangleSetTopologyContainer', name='container')
    bunnyVisu.addObject('TriangleSetTopologyModifier')
    bunnyVisu.addObject('Tetra2TriangleTopologicalMapping', name='Mapping', input="@../container", output="@container")

    bunnyVisu.addObject('OglModel', color=[0.3, 0.2, 0.2, 0.6])
    bunnyVisu.addObject('IdentityMapping')


    return rootNode
