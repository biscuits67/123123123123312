"""Put the vanity plates on the scene cars and clean up the G63's missing textures.

    blender -b IN.blend -P apply_plates.py -- PLATES_DIR OUT.blend

* G63 (plate split off as "G-class_quarterglass_R_tint.001"): TEAM
* Porsche: EMERALD on the rear plate, and a copy of that plate mounted on the front bumper
* plates get a planar UV fitted to the plate face, the image texture and a bump from the letter height map
* G63 materials whose image files are missing on the user's PC (Desktop\\гелик) render pink there:
  their image links are dropped and they fall back to a dark plastic colour
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

PLATES, OUT = sys.argv[sys.argv.index("--") + 1:]
D, scn = bpy.data, bpy.context.scene


def plate_material(text):
    m = D.materials.new(f"Plate_{text}")
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    img = D.images.load(os.path.join(PLATES, f"plate_{text}.png"))
    img.pack()
    h = D.images.load(os.path.join(PLATES, f"plate_{text}_height.png"))
    h.colorspace_settings.name = "Non-Color"
    h.pack()
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image, t.extension = img, "EXTEND"
    th = nt.nodes.new("ShaderNodeTexImage")
    th.image, th.extension = h, "EXTEND"
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(th.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.35
    b.inputs["Specular IOR Level"].default_value = 0.6
    return m


def fit_plate(ob, mat):
    """Single material + planar UV over the plate face (viewer's right = +U, world up = +V)."""
    me = ob.data
    me.materials.clear()
    me.materials.append(mat)
    for p in me.polygons:
        p.material_index = 0
    W3 = ob.matrix_world.to_3x3()
    n = (W3 @ max(me.polygons, key=lambda p: p.area).normal).normalized()   # biggest flat side = the face
    if n.dot(sum((W3 @ p.normal * p.area for p in me.polygons), Vector())) < 0:
        n = -n
    right = (-n).cross(Vector((0, 0, 1))).normalized()      # viewer looks along -n
    up = right.cross(-n).normalized()
    pts = [ob.matrix_world @ v.co for v in me.vertices]
    us = [p.dot(right) for p in pts]
    vs = [p.dot(up) for p in pts]
    u0, u1, v0, v1 = min(us), max(us), min(vs), max(vs)
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    uv = me.uv_layers.new(name="UVMap")
    for loop in me.loops:
        u, v = us[loop.vertex_index], vs[loop.vertex_index]
        uv.data[loop.index].uv = ((u - u0) / (u1 - u0), (v - v0) / (v1 - v0))
    return n


# ---------------------------------------------------------------- G63: TEAM
g_plate = D.objects["G-class_quarterglass_R_tint.001"]
fit_plate(g_plate, plate_material("TEAM"))

# ---------------------------------------------------------------- Porsche: EMERALD rear + front
emerald = plate_material("EMERALD")
rear = D.objects["number_plate_number_plate1_0"]
rear_n = fit_plate(rear, emerald)
porsche = set(D.objects["Sketchfab_model"].children_recursive)
front_axle = Vector((-56.28, -74.785))
fwd = Vector((-rear_n.x, -rear_n.y, 0)).normalized()
rc = sum((rear.matrix_world @ v.co for v in rear.data.vertices), Vector()) / len(rear.data.vertices)
z = 0.40                     # flat vertical part of the front bumper (the plate height of the rear sits on a curve here)
dg = bpy.context.evaluated_depsgraph_get()
origin = Vector((front_axle.x, front_axle.y, z)) + fwd * 3.0
hit_loc = None
o = origin.copy()
for _ in range(20):
    hit, loc, nrm, idx, ob, mat = scn.ray_cast(dg, o, -fwd)
    if not hit:
        break
    if ob in porsche:
        hit_loc = loc
        break
    o = loc - fwd * 0.001
front = D.objects.new("number_plate_front", rear.data.copy())
for c in rear.users_collection:
    c.objects.link(front)
# rotate the rear plate 180 deg about Z around its centre, then move it onto the front bumper
R = Matrix.Rotation(math.pi, 4, "Z")
front.matrix_world = Matrix.Translation(hit_loc + fwd * 0.016) @ R @ Matrix.Translation(-rc) @ rear.matrix_world
fit_plate(front, emerald)
print("front plate at", tuple(round(x, 3) for x in hit_loc))

# the bumper inserts of the G63 body ended up with the first plate material (and its unpacked image):
# put them back to black plastic
body = D.objects["G-class_quarterglass_R_tint"]
slots = [s.material for s in body.material_slots]
black = slots.index(D.materials["G-class_black"])
bad = {i for i, m in enumerate(slots) if m and m.name == "Material"}
moved = 0
for p in body.data.polygons:
    if p.material_index in bad:
        p.material_index = black
        moved += 1
print("bumper faces back to black:", moved)

# ---------------------------------------------------------------- G63 pink parts
fixed = []
for m in D.materials:
    if not m.node_tree:
        continue
    for n in list(m.node_tree.nodes):
        if n.type == "TEX_IMAGE" and n.image and not n.image.packed_file and "гелик" in n.image.filepath:
            m.node_tree.nodes.remove(n)
            b = m.node_tree.nodes.get("Principled BSDF")
            if b:
                b.inputs["Base Color"].default_value = (0.02, 0.02, 0.022, 1)
            fixed.append(m.name)
print("dark fallback:", sorted(set(fixed)))
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT)
