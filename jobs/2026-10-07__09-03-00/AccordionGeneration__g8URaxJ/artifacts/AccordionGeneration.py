#!/usr/bin/env python3
"""
Parametric Accordion Actuator Generator for SOFA simulation.
Generates CAD geometry and meshes compatible with SurfacePressureConstraint_Accordion scene.
"""

import gmsh
import numpy as np
import os


def create_accordion():
    """Generate parametric accordion actuator geometry using Gmsh Python API."""
    
    # === PARAMETERS ===
    length = 50.0        # Total length in mm
    width = 30.0         # Width in mm  
    height = 25.0       # Height in mm
    
    # Number of pleats (folds) along length
    num_pleats = 8
    
    # Mesh parameters
    mesh_size = 5.0      # Base mesh size in mm
    surface_mesh_size = 3.0   # Surface mesh resolution
    volume_mesh_size = 4.0   # Volume mesh resolution
    
    # Setup Gmsh
    gmsh.clear()
    
    # Create points for pleat vertices
    n_segments = num_pleats + 1
    
    segment_length = length / (n_segments - 1)
    t_values = [(i * segment_length, (i + 1) * segment_length) 
                 for i in range(n_segments)]
    
    # Store point tags for each corner of each segment's top/bottom face
    top_points = []
    bottom_points = []
    
    for i in range(n_segments):
        t = i * segment_length
        top_points.append((t, height/2.0, 0.0))
        bottom_points.append((t, -height/2.0, 0.0))
    
    # Create all vertices
    points = []
    for i, (x, y, z) in enumerate(top_points):
        pt_tag = gmsh.model.geo.addPoint(x, y, z, mesh_size * 1e3, "Linear", -1)
        points.append((pt_tag, True))  # top point
    
    for i, (x, y, z) in enumerate(bottom_points):
        pt_tag = gmsh.model.geo.addPoint(x, y, z, mesh_size * 1e3, "Linear", -1)
        points.append((pt_tag, False))  # bottom point
    
    # Add vertices for pleat folds (offset in x direction)
    offset = length / num_pleats * 0.5
    
    fold_points_top = []
    fold_points_bottom = []
    
    for i in range(num_pleats):
        t1, t2 = t_values[i]
        center_t = (t1 + t2) / 2
        
        # Fold vertex on top face (offset in x)
        fold_top = gmsh.model.geo.addPoint(center_t, height/2.0 - offset, 0.0, 
                                          surface_mesh_size * 1e3, "Linear", -1)
        fold_points_top.append(fold_top)
        
        # Fold vertex on bottom face (offset in x opposite direction)
        fold_bottom = gmsh.model.geo.addPoint(center_t, -height/2.0 - offset, 0.0,
                                             surface_mesh_size * 1e3, "Linear", -1)
        fold_points_bottom.append(fold_bottom)
    
    # === CREATE LINES ===
    
    # Top face perimeter lines
    line_tags = []
    
    # Side lines connecting top corners
    for i in range(n_segments - 1):
        pt1, _ = points[i]
        pt2, _ = points[i + 1]
        tag = gmsh.model.geo.addLine(pt1, pt2, -1)
        line_tags.append(tag)
    
    # Bottom face perimeter lines
    for i in range(n_segments - 1):
        pt1, _ = points[n_segments + i]
        pt2, _ = points[n_segments + i + 1]
        tag = gmsh.model.geo.addLine(pt1, pt2, -1)
        line_tags.append(tag)
    
    # Side fold lines
    for i in range(num_pleats):
        top_fold = fold_points_top[i]
        bottom_fold = fold_points_bottom[i]
        
        # Left side of pleat
        t_left = (t_values[i][0] + t_values[i+1][0]) / 2 - offset
        p_left = gmsh.model.geo.addPoint(t_left, height/2.0 + offset, 0.0,
                                         surface_mesh_size * 1e3, "Linear", -1)
        tag = gmsh.model.geo.addLine(pt1=points[i*2][0], pt2=top_fold, curve=-1)
        line_tags.append(tag)
        
        # Right side of pleat  
        t_right = (t_values[i][0] + t_values[i+1][0]) / 2 + offset
        p_right = gmsh.model.geo.addPoint(t_right, height/2.0 + offset, 0.0,
                                          surface_mesh_size * 1e3, "Linear", -1)
        tag = gmsh.model.geo.addLine(pt1=points[i*2][0], pt2=p_left, curve=-1)
        line_tags.append(tag)
    
    # Connect top and bottom with fold lines
    for i in range(num_pleats):
        top_fold = fold_points_top[i]
        bottom_fold = fold_points_bottom[i]
        
        # Top-to-fold connection
        p_mid_top = gmsh.model.geo.addPoint(
            (t_values[i][0] + t_values[i+1][0]) / 2, 
            height/2.0, 0.0, surface_mesh_size * 1e3, "Linear", -1)
        
        # Bottom-to-fold connection  
        p_mid_bot = gmsh.model.geo.addPoint(
            (t_values[i][0] + t_values[i+1][0]) / 2,
            -height/2.0, 0.0, surface_mesh_size * 1e3, "Linear", -1)
    
    # === CREATE PLANES/FACES ===
    
    plane_tags = []
    
    # Top face planes
    for i in range(n_segments - 1):
        pt1, _ = points[i]
        pt2, _ = points[i + 1]
        tag = gmsh.model.geo.addPlaneSurface([line_tags[i]], -1)
        plane_tags.append(tag)
    
    # Bottom face planes
    for i in range(n_segments - 1):
        pt1, _ = points[n_segments + i]
        pt2, _ = points[n_segments + i + 1]
        tag = gmsh.model.geo.addPlaneSurface([line_tags[i]], -1)
        plane_tags.append(tag)
    
    # Pleat face planes (front and back of each pleat)
    for i in range(num_pleats):
        # Front face
        pt_fold = fold_points_top[i]
        pt_prev = points[i*2][0] if i > 0 else top_points[i][0]
        
        tag = gmsh.model.geo.addPlaneSurface(
            [line_tags[i * num_pleats], line_tags[(i+1) * num_pleats]], -1)
        plane_tags.append(tag)
    
    # === CREATE SOLID VOLUME ===
    
    volume_tag = gmsh.model.geo.addVolume(plane_tags, -1)
    
    gmsh.model.geo.synchronize()
    
    # === MESH THE MODEL ===
    
    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", mesh_size * 1e3)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 4.0)
    
    gmsh.model.mesh.generate(2)
    gmsh.model.mesh.generate(3)
    
    # === EXPORT FILES ===
    
    os.makedirs("mesh", exist_ok=True)
    
    # Export STEP file (CAD geometry)
    step_data = gmsh.write()
    with open("mesh/Accordion_Parametric.step", "wb") as f:
        f.write(step_data)
    
    # Export surface STL (2D mesh)
    stl_surface = gmsh.model.mesh.toStl()
    with open("mesh/Accordion_Surface.stl", "wb") as f:
        f.write(stl_surface)
    
    # Export volume VTK file
    vtk_data = gmsh.model.mesh.toVtk()
    with open("mesh/Accordion_Volumetric.vtk", "wb") as f:
        f.write(vtk_data)
    
    # Create cavity STL for pressure constraint (top surface only)
    cavity_coords = []
    for i in range(n_segments):
        t, y, z = top_points[i]
        cavity_coords.append((t, y, z))
    
    with open("mesh/Accordion_Cavity.stl", "wb") as f:
        stl_header = b"solid Accordion_Cavity\n"
        f.write(stl_header)
        
        for i in range(len(cavity_coords) - 1):
            p0 = cavity_coords[i]
            p1 = cavity_coords[i+1]
            
            # Find adjacent point for normal calculation
            if i + 2 < len(cavity_coords):
                p2 = cavity_coords[i+2]
            else:
                p2 = cavity_coords[i-1] if i > 0 else p0
            
            v1 = np.array(p1) - np.array(p0)
            v2 = np.array(p2) - np.array(p0)
            normal = np.cross(v1, v2)
            normal = normal / (np.linalg.norm(normal) + 1e-10)
            
            f.write(b"facet normal")
            for coord in normal:
                f.write(f" {coord:.6f}".encode())
            f.write(b"\n")
            f.write(b"  outer loop\n")
            
            for p in [p0, p1, p2]:
                f.write(b"   vertex")
                for coord in p:
                    f.write(f" {coord:.6f}".encode())
            f.write(b"\n  endloop\n")
            f.write(b"endfacet\n")
        
        f.write(b"endsolid Accordion_Cavity\n")
    
    print(f"Generated accordion: {length}x{width}x{height} mm with {num_pleats} pleats")
    print(f"Mesh size: {mesh_size} mm, Volume vertices: {gmsh.model.mesh.getNumberOfNodes()}")


if __name__ == "__main__":
    create_accordion()
