"""Money case on the G63 hood: the lid opens and slams shut once per loop, a green glow from the money inside.

    blender -b IN.blend -P case_on_g63.py -- CASE.usdz OUT.blend

* the usdz holds two cases; the closed one is dropped, the open one is split into base (+ money) and lid
  (faces above the rim, z > 1.30 in import units); the lid hangs on a hinge empty on the back edge of the rim
* in the import the lid stands 60 deg open; hinge rotation = 60 deg - opening angle
* opening: ease-out with a little overshoot; closing: falls under gravity, small bounce, the case jolts
* every key is inside 1..250 and the lid is closed at both ends, so the loop stays seamless
"""
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

CASE, OUT = sys.argv[sys.argv.index("--") + 1:]
D, scn = bpy.data, bpy.context.scene
F0, F1 = 1, 250
WIDTH = 0.55                               # m, long side of the case
RIM_Z, HINGE_Y, LID_OPEN_IMPORT = 1.26, 1.35, 60.0

before = set(D.objects)
imgs_before = set(D.images)
bpy.ops.wm.usd_import(filepath=CASE, set_frame_range=False)
new = [o for o in D.objects if o not in before]
meshes = {o.name: o for o in new if o.type == "MESH"}
empties = [o for o in new if o.type == "EMPTY"]
for o in meshes.values():                               # bake the import hierarchy into the meshes
    o.data.transform(o.matrix_world)
    o.parent = None
    o.matrix_world = Matrix.Identity(4)
D.objects.remove(meshes.pop("Object_6"))                # the second, closed case
for o in empties:
    D.objects.remove(o)

# split the shell: faces above the rim belong to the lid
shell = meshes.pop("Object_2")
lid = shell.copy()
lid.data = shell.data.copy()
for c in shell.users_collection:
    c.objects.link(lid)
for ob, keep_lid in ((shell, False), (lid, True)):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if (f.calc_center_median().z > RIM_Z + 0.04) != keep_lid],
                     context="FACES")
    bm.to_mesh(ob.data)
    bm.free()

base = shell
with bpy.context.temp_override(active_object=base, selected_editable_objects=[base, *meshes.values()]):
    bpy.ops.object.join()
base.name, lid.name = "Case_Base", "Case_Lid"

# root at the centre of the bottom, scaled to WIDTH
pts = [v.co for v in base.data.vertices]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
s = WIDTH / (hi.x - lo.x)
origin = Vector(((lo.x + hi.x) / 2, 0.0, lo.z))
coll = base.users_collection[0]
root = D.objects.new("Case_Root", None)
hinge = D.objects.new("Case_Hinge", None)
for e in (root, hinge):
    coll.objects.link(e)
    e.empty_display_size = 0.1
to_root = Matrix.Diagonal((s, s, s, 1)) @ Matrix.Translation(-origin)
base.data.transform(to_root)
base.parent = root
hinge_pos = to_root @ Vector((origin.x, HINGE_Y, RIM_Z))
hinge.parent = root
hinge.location = hinge_pos
lid.data.transform(Matrix.Translation(-hinge_pos) @ to_root)
lid.parent = hinge

# ---------------------------------------------------------------- place on the hood
plate = D.objects["G-class_quarterglass_R_tint.001"]
W3 = plate.matrix_world.to_3x3()
n = (W3 @ max(plate.data.polygons, key=lambda p: p.area).normal).normalized()
pc = sum((plate.matrix_world @ v.co for v in plate.data.vertices), Vector()) / len(plate.data.vertices)
fwd = Vector((n.x, n.y, 0)).normalized()
if fwd.x > 0:
    fwd = -fwd
side = fwd.cross(Vector((0, 0, 1)))
scn.frame_set(F0)
dg = bpy.context.evaluated_depsgraph_get()


def hood(p):
    hit, loc, nrm, *_ = scn.ray_cast(dg, Vector((p.x, p.y, 2.5)), Vector((0, 0, -1)))
    return loc, nrm


spot = pc - fwd * 1.0 + side * 0.05
loc, _ = hood(spot)
nrm = sum((hood(spot + fwd * a + side * b)[1] for a in (-0.2, 0.2) for b in (-0.2, 0.2)), Vector()).normalized()
cam = D.objects["Camera"].matrix_world.translation
to_cam = Vector((cam.x - loc.x, cam.y - loc.y, 0)).normalized()
front = (to_cam + fwd).normalized()                     # between "faces the camera" and "straight on the car"
y_ax = (-front - nrm * nrm.dot(-front)).normalized()    # model -Y (latches) points to the front
x_ax = y_ax.cross(nrm)
R = Matrix((x_ax, y_ax, nrm)).transposed().to_4x4()
root.matrix_world = Matrix.Translation(loc + nrm * 0.002) @ R
print("case at", tuple(round(c, 3) for c in loc), "normal", tuple(round(c, 3) for c in nrm))


# ---------------------------------------------------------------- animation
def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


OPEN = 100.0
O0, O1 = 26, 44            # opening
C0, C1 = 194, 204          # closing (lid hits the rim at C1)


def lid_angle(f):
    if f < O0 or f >= C1 + 10:
        return 0.0
    if f < O1:                                       # ease-out-back to OPEN
        x = (f - O0) / (O1 - O0)
        k = 1.9
        return OPEN * (1 + (k + 1) * (x - 1) ** 3 + k * (x - 1) ** 2)
    if f < C0:
        return OPEN
    if f < C1:                                       # falls under gravity
        x = (f - C0) / (C1 - C0)
        return OPEN * (1 - x * x)
    x = (f - C1) / 10                                # one small bounce
    return 5.0 * math.sin(math.pi * x) * (1 - x)


def jolt(f):
    d = f - C1
    return 0.0 if d < 0 or d > 8 else math.exp(-d / 2.2) * math.sin(d * 2.4)


base_mw = root.matrix_world.copy()
for f in range(F0, F1 + 1):
    hinge.rotation_euler = (math.radians(LID_OPEN_IMPORT - lid_angle(f)), 0, 0)
    hinge.keyframe_insert("rotation_euler", index=0, frame=f)
    j = jolt(f)
    root.matrix_world = base_mw @ Matrix.Translation((0, 0, 0.004 * abs(j))) @ \
        Matrix.Rotation(math.radians(0.6 * j), 4, "Y")
    root.keyframe_insert("location", frame=f)
    root.keyframe_insert("rotation_euler", frame=f)

# green glow from the money, follows how far the lid is open
glow = D.objects.new("Case_Glow", D.lights.new("Case_Glow", "POINT"))
coll.objects.link(glow)
glow.parent = root
glow.location = (0, -0.04, (to_root @ Vector((0, 0, 2.3))).z)    # above the rolls, under the open lid
glow.data.color = (0.25, 1.0, 0.5)
glow.data.shadow_soft_size = 0.12
glow.visible_camera = False
for f in range(F0, F1 + 1):
    glow.data.energy = 7.0 * smooth(lid_angle(f) / OPEN) ** 1.5
    glow.data.keyframe_insert("energy", frame=f)

for ob in (hinge, root, glow.data):
    ad = ob.animation_data
    for layer in ad.action.layers:
        for strip in layer.strips:
            for fc in strip.channelbag(ad.action_slot).fcurves:
                for k in fc.keyframe_points:
                    k.interpolation = "LINEAR"

for img in set(D.images) - imgs_before:              # the case textures live in a temp dir of the importer
    if not img.packed_file:
        img.pack()

scn.frame_start, scn.frame_end = F0, F1
scn.frame_set(F0)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT)
