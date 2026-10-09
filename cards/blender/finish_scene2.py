"""Second pass on the finished exchange scene (after finish_scene.py), same 250-frame loop:

    * live rates board: rates_atlas.png (20 states) stepped by a Mapping node, a tick every 25 frames
      with a 6-frame green/red flash on the prices that moved;
    * forklift drive-through: enters from the left with the money pallet, crosses in front of the
      cars in ~6 s, waits off-screen right and re-enters from the left at the loop point;
      headlight + work light ride with it, slight engine judder;
    * atmosphere: thin volumetric haze so the neon, the street lamp and the headlight read as beams;
    * lens: depth of field on the emerald, motion blur (wrap-around jumps keyed constant),
      compositor bloom on the neon, faint chromatic aberration and a vignette.

    blender -b IN.blend -P finish_scene2.py -- ATLAS.png OUT.blend
"""
import math
import sys

import bpy
from mathutils import Vector

ATLAS, OUT = sys.argv[sys.argv.index("--") + 1:]
D, scn = bpy.data, bpy.context.scene
F0, F1 = 1, 250
LOOP = F1 - F0 + 1


def channelbag(idb):
    ad = idb.animation_data
    return ad.action.layers[0].strips[0].channelbag(ad.action_slot)


def interp(idb, kind):
    for fc in channelbag(idb).fcurves:
        for k in fc.keyframe_points:
            k.interpolation = kind


# ---------------------------------------------------------------- live rates board
img = D.images.load(ATLAS)
img.pack()
mat = D.objects["rates_board"].data.materials[0]
nt = mat.node_tree
tex = [n for n in nt.nodes if n.type == "TEX_IMAGE"]
uv = nt.nodes.new("ShaderNodeTexCoord")
mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Scale"].default_value = (1 / 4, 1 / 5, 1)
nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
for t in tex:
    t.image = img
    t.extension = "EXTEND"
    nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
loc = mp.inputs["Location"]
for tick in range(10):
    for state, f in ((tick * 2, F0 + tick * 25), (tick * 2 + 1, F0 + tick * 25 + 6)):
        col, row = state % 4, state // 4
        loc.default_value = (col / 4, (4 - row) / 5, 0)
        loc.keyframe_insert("default_value", frame=f)
interp(nt, "CONSTANT")

# ---------------------------------------------------------------- forklift drive-through
fork = D.objects["forklift_truck"]
cargo = [D.objects[n] for n in ("Asset3DLoader.sceneRoot", "Point") if n in D.objects]
for ob in cargo:
    mw = ob.matrix_world.copy()
    ob.parent = fork
    ob.matrix_world = mw
SHIFT_X = -0.8                                   # 0.8 m nearer the camera: clear of the G63 and the Porsche
x0, z0 = fork.location.x + SHIFT_X, fork.location.z
Y_IN, Y_OUT, DRIVE = -63.0, -79.0, 150           # off-screen left -> off-screen right in 150 frames (~2.5 m/s)
fork.animation_data_clear()
for f in range(F0, F1 + 1):
    if f <= F0 + DRIVE:
        t = (f - F0) / DRIVE
        y = Y_IN + (Y_OUT - Y_IN) * t             # constant speed through the frame
    else:
        y = Y_OUT
    fork.location = (x0, y, z0 + 0.004 * math.sin(f * 1.9) + 0.003 * math.sin(f * 3.7))
    fork.rotation_euler.y = math.radians(0.25) * math.sin(f * 1.3)
    fork.keyframe_insert("location", frame=f)
    fork.keyframe_insert("rotation_euler", index=1, frame=f)
interp(fork, "LINEAR")
for fc in channelbag(fork).fcurves:                # the wrap from Y_OUT back to Y_IN must not smear
    if fc.data_path == "location" and fc.array_index == 1:
        fc.keyframe_points[-1].interpolation = "CONSTANT"

bb = [fork.matrix_world @ Vector(c) for c in fork.bound_box]
front_y = min(p.y for p in bb)                     # forks point along -Y, the way it drives
head = D.objects.new("Forklift_Headlight", D.lights.new("Forklift_Headlight", "SPOT"))
head.data.energy, head.data.color = 350, (1.0, 0.93, 0.82)
head.data.spot_size, head.data.spot_blend, head.data.shadow_soft_size = math.radians(55), 0.45, 0.08
scn.collection.objects.link(head)
head.location = (x0, front_y + 1.6, z0 + 1.9)
head.rotation_euler = Vector((0, -1, -0.75)).to_track_quat("-Z", "Y").to_euler()   # down-forward
head.parent = fork
head.matrix_parent_inverse = fork.matrix_world.inverted()

# its lights fade up/down while it is off-screen, so the light spill never pops at the loop point
def envelope(f):
    up = min(1.0, max(0.0, (f - F0) / 19))
    down = min(1.0, max(0.0, (F0 + 175 - f) / 15))
    return min(up, down) ** 2

point = D.objects.get("Point")
beacon = D.objects.get("Forklift_Beacon_Light")
if beacon and beacon.data.animation_data:
    beacon.data.animation_data_clear()
for f in range(F0, F1 + 1):
    e = envelope(f)
    for lamp, full in ((head, 350.0), (point, point.data.energy if point else 0)):
        if lamp:
            if f == F0:
                lamp["full"] = full
            lamp.data.energy = lamp["full"] * e
            lamp.data.keyframe_insert("energy", frame=f)
    if beacon:
        beacon.data.energy = 6.0 * e if (f - F0) % 25 < 6 else 0.0
        beacon.data.keyframe_insert("energy", frame=f)
if beacon:
    interp(beacon.data, "CONSTANT")

# ground bills: off the forklift's lane
lane = (x0 - 0.9, x0 + 0.9)
for ob in D.objects:
    if ob.name.startswith("Bill_ground_") and lane[0] - 0.3 < ob.location.x < lane[1] + 0.3:
        ob.location.x = lane[1] + 0.25 if ob.location.x > x0 else lane[0] - 0.6

# ---------------------------------------------------------------- motion blur safety on the wind bills
for ob in D.objects:
    if ob.name.startswith("Bill_") and not ob.name.startswith("Bill_ground") and ob.animation_data:
        fcs = {fc.array_index: fc for fc in channelbag(ob).fcurves if fc.data_path == "location"}
        pts = list(zip(*(fcs[i].keyframe_points for i in range(3))))
        for a, b in zip(pts, pts[1:]):
            if (Vector([k.co[1] for k in a]) - Vector([k.co[1] for k in b])).length > 1.0:   # wrap jump
                for k in a:
                    k.interpolation = "CONSTANT"

# ---------------------------------------------------------------- atmosphere
bpy.ops.mesh.primitive_cube_add(location=(-57.5, -72.5, 4.0))
haze = bpy.context.object
haze.name = "Atmosphere_Haze"
haze.scale = (11, 12, 4.1)
hm = D.materials.new("Haze")
hm.node_tree.nodes.remove(hm.node_tree.nodes["Principled BSDF"])
vol = hm.node_tree.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = 0.005
vol.inputs["Anisotropy"].default_value = 0.55
vol.inputs["Color"].default_value = (0.8, 0.86, 0.9, 1)
hm.node_tree.links.new(vol.outputs["Volume"], hm.node_tree.nodes["Material Output"].inputs["Volume"])
haze.data.materials.append(hm)
haze.visible_shadow = False
scn.cycles.volume_step_rate = 4.0
scn.cycles.volume_max_steps = 256

# ---------------------------------------------------------------- lens: DOF, motion blur
D.objects["Camera"].data.dof.use_dof = True
D.objects["Camera"].data.dof.focus_object = D.objects["Hero_Emerald"]
D.objects["Camera"].data.dof.aperture_fstop = 2.8
scn.render.use_motion_blur = True
scn.render.motion_blur_shutter = 0.5

# ---------------------------------------------------------------- compositor: bloom, CA, vignette
tree = D.node_groups.new("Emerald Grade", "CompositorNodeTree")
tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
N = tree.nodes
rl = N.new("CompositorNodeRLayers")
glare = N.new("CompositorNodeGlare")
glare.inputs["Type"].default_value = "Bloom"
glare.inputs["Quality"].default_value = "High"
glare.inputs["Threshold"].default_value = 1.0
glare.inputs["Strength"].default_value = 0.35
glare.inputs["Size"].default_value = 0.6
lens = N.new("CompositorNodeLensdist")
lens.inputs["Dispersion"].default_value = 0.012
lens.inputs["Fit"].default_value = True
mask = N.new("CompositorNodeEllipseMask")
mask.inputs["Mask"].default_value = 0.0
mask.inputs["Value"].default_value = 1.0
mask.inputs["Size"].default_value = (1.15, 1.05)
blur = N.new("CompositorNodeBlur")
blur.inputs["Size"].default_value = (260, 260)
blur.inputs["Extend Bounds"].default_value = False
lift = N.new("ShaderNodeMapRange")
lift.inputs["To Min"].default_value = 0.55
mix = N.new("ShaderNodeMix")
mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
mix.inputs[0].default_value = 1.0
out = N.new("NodeGroupOutput")
L = tree.links
L.new(rl.outputs["Image"], glare.inputs["Image"])
L.new(glare.outputs["Image"], lens.inputs["Image"])
L.new(mask.outputs["Mask"], blur.inputs["Image"])
L.new(blur.outputs["Image"], lift.inputs["Value"])
L.new(lens.outputs["Image"], mix.inputs[6])
L.new(lift.outputs["Result"], mix.inputs[7])
L.new(mix.outputs[2], out.inputs[0])
scn.compositing_node_group = tree
scn.render.use_compositing = True

scn.frame_set(F0)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT)
