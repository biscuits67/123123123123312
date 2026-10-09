"""Finishes the user's Emerald exchange scene (their .blend) for a seamless 250-frame loop:

    * hero: idle cut to 250 frames with the last 3 s eased back into frame 1, two arm lifts per loop,
      emerald bob/spin retimed to 250 frames;
    * EMERALD sign: two neon stutters per loop, the green spill light and the rim stutter with it;
    * wind: $20 bills tumbling across the frame (each wraps off-screen, so the loop has no seam)
      and a few bills lying on the wet cobblestones;
    * amber beacon blinking on the forklift roof;
    * camera: subtle handheld sway and a slow push-in that eases back out by the loop point;
    * render settings for an RTX card (OptiX, adaptive sampling, denoise) and MP4 output.

    blender -b IN.blend -P finish_scene.py -- OUT.blend
"""
import math
import random
import sys

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

OUT = sys.argv[sys.argv.index("--") + 1]
D, scn = bpy.data, bpy.context.scene
F0, F1 = 1, 250
LOOP = F1 - F0 + 1                      # frame 251 == frame 1
P = "mixamorig:"
rng = random.Random(7)


def channelbag(idblock):
    ad = idblock.animation_data
    return ad.action.layers[0].strips[0].channelbag(ad.action_slot)


def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- hero: 250-frame loop
rig = D.objects["Hero_Rig"]
bag = channelbag(rig)
curves = {}
for fc in bag.fcurves:
    curves.setdefault(fc.data_path, {})[fc.array_index] = fc
BLEND0 = 176                            # ease back into frame 1 over frames 176..251
ARM = [f'pose.bones["{P}{n}"].rotation_quaternion' for n in ("RightArm", "RightForeArm", "RightHand")]
for path, comps in curves.items():
    n = max(comps) + 1
    samples = {f: [comps[i].evaluate(f) if i in comps else 0.0 for i in range(n)] for f in range(F0, F1 + 2)}
    if path in ARM:   # palm-up hold: rebuild the lift so it has two lifts per 250 frames
        q_lo, q_hi = Quaternion(samples[1]), Quaternion([comps[i].evaluate(106) for i in range(4)])
        new = {f: list(q_lo.slerp(q_hi, 0.5 - 0.5 * math.cos(2 * math.pi * (f - F0) * 2 / LOOP))) for f in samples}
    else:
        first, last = samples[F0], samples[F1 + 1]
        if path.endswith("rotation_quaternion") and sum(a * b for a, b in zip(first, last)) < 0:
            for f in samples:
                if f > F1 // 2:
                    samples[f] = [-x for x in samples[f]]
            last = samples[F1 + 1]
        new = {}
        for f, v in samples.items():
            s = smooth((f - BLEND0) / (F1 + 1 - BLEND0))
            new[f] = [x + s * (a - b) for x, a, b in zip(v, first, last)]
        if path.endswith("rotation_quaternion"):
            new = {f: list(Quaternion(v).normalized()) for f, v in new.items()}
    for i, fc in comps.items():
        fc.keyframe_points.clear()
        fc.keyframe_points.add(len(new))
        for k, f in zip(fc.keyframe_points, sorted(new)):
            k.co = (f, new[f][i])
            k.interpolation = "LINEAR"
        fc.update()
rig.animation_data.action.use_frame_range = True
rig.animation_data.action.frame_start, rig.animation_data.action.frame_end = F0, F1 + 1

for name in ("Hero_Emerald", "Hero_Emerald_Glow"):
    for d in D.objects[name].animation_data.drivers:
        e = d.driver
        if d.data_path == "location":
            e.expression = f"0.09 + 0.012*sin((frame-1)*{2 * math.pi * 2 / LOOP:.7f})"       # 2 bobs
        else:
            e.expression = f"(frame-1)*{2 * math.pi / LOOP:.7f}"                            # 1 turn

# ---------------------------------------------------------------- neon stutter
text_mat = D.objects["Text"].data.materials[0]
rim_mat = D.objects["Cube.021"].data.materials[0]
spill = D.objects["Area.001"].data
BASE = {"text": 2.2, "rim": 3.0, "spill": spill.energy}
# (frame, brightness factor) - held until the next key
STUTTER = [(1, 1), (68, 1), (69, 0.08), (71, 1), (73, 0.15), (74, 0.6), (76, 0.05), (80, 1),
           (178, 1), (179, 0.1), (181, 0.9), (182, 0.07), (185, 1), (F1 + 1, 1)]
if text_mat.node_tree.animation_data:
    text_mat.node_tree.animation_data_clear()


for mat, key in ((text_mat, "text"), (rim_mat, "rim")):
    sock = mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
    for f, v in STUTTER:
        sock.default_value = BASE[key] * v
        sock.keyframe_insert("default_value", frame=f)
    for fc in channelbag(mat.node_tree).fcurves:
        for k in fc.keyframe_points:
            k.interpolation = "CONSTANT"
for f, v in STUTTER:
    spill.energy = BASE["spill"] * v
    spill.keyframe_insert("energy", frame=f)
for fc in channelbag(spill).fcurves:
    for k in fc.keyframe_points:
        k.interpolation = "CONSTANT"

# ---------------------------------------------------------------- $20 bills in the wind
bill_img = D.images["Image_0.001"]          # the $20 note from the money stacks
bm_mat = D.materials.new("Bill")
nt = bm_mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = bill_img
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.55
bsdf.inputs["Subsurface Weight"].default_value = 0.0
bsdf.inputs["Sheen Weight"].default_value = 0.2
bill_mesh = D.meshes.new("bill")
W, H, NX = 0.156, 0.066, 8
verts = [(-W / 2 + W * i / NX, -H / 2 + H * j, 0) for j in (0, 1) for i in range(NX + 1)]
faces = [(i, i + 1, NX + 2 + i, NX + 1 + i) for i in range(NX)]
bill_mesh.from_pydata(verts, [], faces)
uv = bill_mesh.uv_layers.new()
for poly in bill_mesh.polygons:
    for li in poly.loop_indices:
        x, y, _ = bill_mesh.vertices[bill_mesh.loops[li].vertex_index].co
        uv.data[li].uv = (x / W + 0.5, y / H + 0.5)
bill_mesh.materials.append(bm_mat)
col = D.collections.new("Wind_Bills")
scn.collection.children.link(col)

cam = D.objects["Camera"]
cam_inv = cam.matrix_world.inverted()
half = cam.data.sensor_width / 2 / cam.data.lens          # horizontal half-width per metre of depth


def world_at(depth, sx, height):
    """Point at camera depth `depth` (m), horizontal screen position sx (-1 left .. 1 right), world height."""
    p = cam.matrix_world @ Vector((sx * half * depth, 0, -depth))
    p.z = height
    return p


for i in range(16):
    ob = D.objects.new(f"Bill_{i:02d}", bill_mesh)
    col.objects.link(ob)
    bend = ob.modifiers.new("flutter", "SIMPLE_DEFORM")
    bend.deform_method, bend.deform_axis = "BEND", "Y"
    depth = rng.uniform(4.5, 11.0)
    laps = 1 if depth > 7 else rng.choice((1, 2))        # crossings per loop (integer -> seamless)
    off, h0 = rng.random(), rng.uniform(0.25, 2.2)
    sway, spin = rng.uniform(0.15, 0.5), [rng.choice((-2, -1, 1, 2)) for _ in range(3)]
    ph = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    edge = 1.25 + 0.4 / depth                           # start/end just outside the frame
    for f in range(F0, F1 + 1):
        p = ((f - F0) / LOOP * laps + off) % 1.0
        t = 2 * math.pi * p
        sx = -edge + 2 * edge * p
        h = h0 + sway * math.sin(t * 2 + ph[0]) + 0.12 * math.sin(t * 5 + ph[1])
        ob.location = world_at(depth + 0.6 * math.sin(t + ph[2]), sx, max(0.05, h))
        ob.rotation_euler = Euler((spin[0] * t + ph[1], spin[1] * t + ph[2], spin[2] * t * 0.5 + ph[3]))
        bend.angle = math.radians(55) * math.sin(t * 6 + ph[3])
        ob.keyframe_insert("location", frame=f)
        ob.keyframe_insert("rotation_euler", frame=f)
        bend.keyframe_insert("angle", frame=f)
    for fc in channelbag(ob).fcurves:
        for k in fc.keyframe_points:
            k.interpolation = "LINEAR"

# a few notes lying on the wet ground around the hero and the money pallet
GROUND = [(-58.6, -72.1, 25), (-59.4, -73.6, -40), (-60.3, -71.0, 70), (-57.9, -74.4, 10),
          (-60.9, -73.0, -75), (-59.1, -70.0, 35), (-61.5, -74.8, 55)]
for i, (x, y, rz) in enumerate(GROUND):
    ob = D.objects.new(f"Bill_ground_{i}", bill_mesh)
    col.objects.link(ob)
    ob.location = (x, y, 0.004)
    ob.rotation_euler = (0, 0, math.radians(rz))

# ---------------------------------------------------------------- amber beacon on the forklift roof
fork = D.objects["forklift_truck"]
bb = [fork.matrix_world @ Vector(c) for c in fork.bound_box]
top = max(p.z for p in bb)
cx = sum(p.x for p in bb) / 8
cab_y = max(p.y for p in bb) - 0.9                     # roof over the seat, away from the forks
bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.06, depth=0.1, location=(cx, cab_y, top + 0.05))
lamp = bpy.context.object
lamp.name = "Forklift_Beacon"
bm = D.materials.new("Beacon")
b = bm.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (1.0, 0.35, 0.02, 1)
b.inputs["Emission Color"].default_value = (1.0, 0.35, 0.02, 1)
lamp.data.materials.append(bm)
glow = D.objects.new("Forklift_Beacon_Light", D.lights.new("Forklift_Beacon_Light", "POINT"))
glow.data.color, glow.data.shadow_soft_size = (1.0, 0.45, 0.08), 0.05
glow.location = (cx, cab_y, top + 0.14)
scn.collection.objects.link(glow)
for ob in (lamp, glow):
    ob.parent = fork
    ob.matrix_parent_inverse = fork.matrix_world.inverted()
es = b.inputs["Emission Strength"]
for f in range(F0, F1 + 1, 25):                         # 10 blinks per loop
    for df, on in ((0, True), (6, False)):
        es.default_value = 25.0 if on else 0.0
        es.keyframe_insert("default_value", frame=f + df)
        glow.data.energy = 6.0 if on else 0.0
        glow.data.keyframe_insert("energy", frame=f + df)
for idb in (bm.node_tree, glow.data):
    for fc in channelbag(idb).fcurves:
        for k in fc.keyframe_points:
            k.interpolation = "CONSTANT"

# ---------------------------------------------------------------- camera: handheld sway + slow push-in
# every term has a whole number of cycles per loop, so frame 251 matches frame 1 exactly
base = cam.matrix_world.copy()
fwd = (base.to_3x3() @ Vector((0, 0, -1))).normalized()
up = base.to_3x3() @ Vector((0, 1, 0))
right = base.to_3x3() @ Vector((1, 0, 0))
cam.animation_data_clear()
for f in range(F0, F1 + 1):
    t = 2 * math.pi * (f - F0) / LOOP
    push = 0.55 * (0.5 - 0.5 * math.cos(t))            # eases ~0.55 m in and back out
    pos = base.translation + fwd * push + up * (0.012 * math.sin(2 * t + 0.4) + 0.006 * math.sin(7 * t)) \
        + right * (0.015 * math.sin(3 * t + 1.1) + 0.005 * math.sin(9 * t + 2.0))
    rot = (base.to_3x3() @ Euler((math.radians(0.22 * math.sin(3 * t + 0.7) + 0.08 * math.sin(8 * t)),
                                  math.radians(0.28 * math.sin(2 * t + 2.1) + 0.07 * math.sin(11 * t + 1.0)),
                                  math.radians(0.15 * math.sin(4 * t + 0.3)))).to_matrix()).to_euler()
    cam.matrix_world = Matrix.Translation(pos) @ rot.to_matrix().to_4x4()
    cam.keyframe_insert("location", frame=f)
    cam.keyframe_insert("rotation_euler", frame=f)
for fc in channelbag(cam).fcurves:
    for k in fc.keyframe_points:
        k.interpolation = "LINEAR"

# ---------------------------------------------------------------- render settings (RTX 3050)
scn.frame_start, scn.frame_end = F0, F1
scn.render.fps = 24
c = scn.cycles
c.device = "GPU"
c.samples, c.adaptive_threshold, c.use_adaptive_sampling = 160, 0.04, True
c.use_denoising = True
try:
    c.denoiser = "OPTIX"                                  # only listed on a machine with an RTX card
except TypeError:
    pass                                                  # keep the file's denoiser (OptiX on the user's PC)
c.time_limit = 0
scn.render.use_persistent_data = True
scn.render.resolution_x, scn.render.resolution_y, scn.render.resolution_percentage = 1920, 1080, 100
im = scn.render.image_settings
if hasattr(im, "media_type"):
    im.media_type = "VIDEO"
im.file_format = "FFMPEG"
ff = scn.render.ffmpeg
ff.format, ff.codec, ff.constant_rate_factor, ff.ffmpeg_preset = "MPEG4", "H264", "HIGH", "GOOD"
scn.render.filepath = "//render/emerald_"
scn.frame_set(F0)

# fonts and the unpacked textures live on the user's PC, relative to the original file in Downloads:
# make those paths absolute so the finished file works from any folder
HOME = "C:\\Users\\QWERTY\\Downloads\\"
for idb in list(D.fonts) + list(D.images):
    fp = idb.filepath
    if fp.startswith("//") and not idb.packed_file:
        idb.filepath = HOME + fp[2:].replace("/", "\\")
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT)
