"""Street dressing for the Emerald exchange scene (250-frame loop, run on the kinetic-wall scene).

    blender -b IN.blend -P dress_scene.py -- PROPS_DIR TEX_DIR OUT.blend

* forklift cargo -> money pallet (Pack_Money.usdz) with a sprayed USDT stencil on the camera side;
  the forklift jolts over a bump, four bundles fly off the top, burst on the wet asphalt and the
  loose notes are carried off-screen by the wind before the loop point
* concrete street lights with warm lamps (one flickers) and sagging wires across the top of the frame
* CCTV cameras under the sign corners, a traffic cone, a manhole with looping steam, a branded mat
* puddles mixed into the cobblestone material
"""
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

PROPS, TEX, OUT = sys.argv[sys.argv.index("--") + 1:]
D, scn = bpy.data, bpy.context.scene
F0, F1 = 1, 250
LOOP = F1 - F0 + 1
rng = random.Random(11)
col = D.collections.new("Street_Dressing")
scn.collection.children.link(col)


def imported(fn):
    before = set(D.objects)
    fn()
    bpy.context.view_layer.update()
    return [o for o in D.objects if o not in before]


def join_into(objs, name):
    """Join the meshes of an import into one object with transforms applied; delete the empties."""
    meshes = [o for o in objs if o.type == "MESH"]
    empties = [o.name for o in objs if o.type != "MESH"]
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for n in empties:
        if n in D.objects:
            D.objects.remove(D.objects[n])
    ob.name = name
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
    return ob


def bbox(ob):
    if ob.type == "MESH":                                    # bound_box is stale right after data.transform()
        mw = ob.matrix_world
        pts = [mw @ v.co for v in ob.data.vertices]
    else:
        pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def fit(ob, size_axis, size, base=None, center_xy=None):
    """Scale to `size` along an axis, then put the bottom on `base` and centre on `center_xy` (mesh-level)."""
    lo, hi = bbox(ob)
    k = size / (hi[size_axis] - lo[size_axis])
    ob.data.transform(Matrix.Scale(k, 4))
    ob.data.update()
    lo, hi = bbox(ob)
    c = (lo + hi) / 2
    off = Vector((0, 0, 0))
    if center_xy is not None:
        off.x, off.y = center_xy[0] - c.x, center_xy[1] - c.y
    if base is not None:
        off.z = base - lo.z
    ob.data.transform(Matrix.Translation(off))
    ob.data.update()


def channelbag(idb):
    ad = idb.animation_data
    return ad.action.layers[0].strips[0].channelbag(ad.action_slot)


def mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = D.materials.new(name)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value, b.inputs["Metallic"].default_value = rough, metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def tex_material(name, base, rough=None, metal=None, normal=None, emit=None, emit_strength=0.0):
    m = D.materials.new(name)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]

    def img(path, non_color=False):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = D.images.load(path, check_existing=True)
        if non_color:
            t.image.colorspace_settings.name = "Non-Color"
        return t

    nt.links.new(img(base).outputs["Color"], b.inputs["Base Color"])
    if rough:
        nt.links.new(img(rough, True).outputs["Color"], b.inputs["Roughness"])
    if metal:
        nt.links.new(img(metal, True).outputs["Color"], b.inputs["Metallic"])
    if normal:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(img(normal, True).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if emit:
        nt.links.new(img(emit).outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit_strength
    return m


# ================================================================== 1. money pallet on the forklift
fork = D.objects["forklift_truck"]
old = D.objects["Asset3DLoader.sceneRoot"]
scn.frame_set(F0)
olo, ohi = bbox(old)
old.hide_render = old.hide_viewport = True
pallet = join_into(imported(lambda: bpy.ops.wm.usd_import(filepath=os.path.join(PROPS, "money/pack.usdz"), set_frame_range=False)),
                   "USDT_Pallet")
pallet.data.transform(Matrix.Rotation(math.radians(90), 4, "Z"))      # long side towards the camera (-X)
fit(pallet, 1, 1.55, base=olo.z, center_xy=((olo.x + ohi.x) / 2 + 0.25, (olo.y + ohi.y) / 2))
plo, phi = bbox(pallet)
# sprayed USDT stencil on the camera-facing (-X) side of the wrap
st = D.materials.new("USDT_Stencil")
nt = st.node_tree
b = nt.nodes["Principled BSDF"]
t = nt.nodes.new("ShaderNodeTexImage")
t.image = D.images.load(os.path.join(TEX, "usdt_stencil.png"))
t.extension = "CLIP"
nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
nt.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
b.inputs["Roughness"].default_value = 0.55
nt.links.new(t.outputs["Color"], b.inputs["Emission Color"])
b.inputs["Emission Strength"].default_value = 0.9                           # readable in the dark street
me = D.meshes.new("usdt_decal")
w, h = (phi.y - plo.y) * 0.92, (phi.z - plo.z) * 0.62
x = plo.x - 0.006
yc, zc = (plo.y + phi.y) / 2, plo.z + (phi.z - plo.z) * 0.55
me.from_pydata([(x, yc + w / 2, zc - h / 2), (x, yc - w / 2, zc - h / 2), (x, yc - w / 2, zc + h / 2),
                (x, yc + w / 2, zc + h / 2)], [], [(0, 1, 2, 3)])
uv = me.uv_layers.new()
for li, u in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
    uv.data[li].uv = u
me.materials.append(st)
decal = D.objects.new("USDT_Stencil", me)
col.objects.link(decal)
for ob in (pallet, decal):
    ob.parent = fork
    ob.matrix_parent_inverse = fork.matrix_world.inverted()
point = D.objects.get("Point")
if point:
    point.location.z += 0.6                                                # lamp above the taller load

# ---- bump: forklift jolts at the drop frame (adds to the existing per-frame keys)
DROP = 76
for fc in channelbag(fork).fcurves:
    if fc.data_path == "location" and fc.array_index == 2:
        for k in fc.keyframe_points:
            dt = k.co[0] - DROP
            if -2 <= dt <= 10:
                k.co[1] += 0.07 * math.sin(math.pi * (dt + 2) / 6) * math.exp(-max(dt, 0) / 5)
    if fc.data_path == "rotation_euler" and fc.array_index == 1:
        for k in fc.keyframe_points:
            dt = k.co[0] - DROP
            if -2 <= dt <= 12:
                k.co[1] += math.radians(2.2) * math.sin(math.pi * (dt + 2) / 7) * math.exp(-max(dt, 0) / 6)
    fc.update()


# ---- falling bundles + bursting notes
def fork_world(f):
    scn.frame_set(f)
    return fork.matrix_world.copy()


bill_mat = D.materials.get("Bill")
band = mat("Bundle_Band", (0.75, 0.62, 0.35), rough=0.6)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(0.156, 0.066, 0.05), verts=bm.verts)
bundle_mesh = D.meshes.new("bundle")
bm.to_mesh(bundle_mesh)
bm.free()
uvl = bundle_mesh.uv_layers.new()
for p in bundle_mesh.polygons:
    for li in p.loop_indices:
        co = bundle_mesh.vertices[bundle_mesh.loops[li].vertex_index].co
        uvl.data[li].uv = (co.x / 0.156 + 0.5, co.y / 0.066 + 0.5)
bundle_mesh.materials.append(bill_mat if bill_mat else mat("Bundle", (0.3, 0.4, 0.3)))
band_mesh = D.meshes.new("band")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(0.03, 0.068, 0.052), verts=bm.verts)
bm.to_mesh(band_mesh)
bm.free()
band_mesh.materials.append(band)
note_mesh = D.meshes.get("bill")

G, FPS = 9.81, 24.0
dt = 1 / FPS
WM = {f: fork_world(f) for f in range(F0, F1 + 1)}
scn.frame_set(F0)                                    # bundle seats are measured on the frame-1 pallet
ground_z = 0.02
bundles = []
for i in range(4):
    px, py = plo.x + 0.18 + 0.1 * i, phi.y - 0.3 - 0.38 * i
    inv = pallet.matrix_world.inverted()                  # sit exactly on the wrap: ray-cast down onto the pallet
    hit, loc, _, _ = pallet.ray_cast(inv @ Vector((px, py, phi.z + 1)), (inv.to_3x3() @ Vector((0, 0, -1))).normalized())
    top = (pallet.matrix_world @ loc).z if hit else phi.z
    local = WM[F0].inverted() @ Vector((px, py, top + 0.026))
    drop = DROP + 2 + i
    b_ob = D.objects.new(f"Drop_Bundle_{i}", bundle_mesh)
    col.objects.link(b_ob)
    bd = D.objects.new(f"Drop_Band_{i}", band_mesh)
    col.objects.link(bd)
    bd.parent = b_ob
    yaw0 = rng.uniform(-0.4, 0.4)
    vel = None
    pos = None
    rot = Euler((0, 0, yaw0))
    spin = Vector((rng.uniform(-9, 9), rng.uniform(-12, 12), rng.uniform(-4, 4)))
    landed = None
    for f in range(F0, F1 + 1):
        if f <= drop:
            pos = WM[f] @ local
            if f == drop:
                prev = WM[f - 1] @ local
                vel = (pos - prev) * FPS + Vector((-rng.uniform(1.2, 1.9), rng.uniform(-0.3, 0.3), rng.uniform(1.0, 1.6)))
            b_ob.location = pos
            b_ob.rotation_euler = WM[f].to_euler()
            b_ob.rotation_euler.z += yaw0
        elif landed is None:
            vel.z -= G * dt
            pos = pos + vel * dt
            rot = Euler((rot.x + spin.x * dt, rot.y + spin.y * dt, rot.z + spin.z * dt))
            if pos.z <= ground_z + 0.03:
                pos.z = ground_z + 0.03
                landed = f
            b_ob.location, b_ob.rotation_euler = pos, rot
        visible = landed is None or f < landed + 1
        b_ob.scale = (1, 1, 1) if visible else (0, 0, 0)
        b_ob.keyframe_insert("location", frame=f)
        b_ob.keyframe_insert("rotation_euler", frame=f)
        b_ob.keyframe_insert("scale", frame=f)
    for fc in channelbag(b_ob).fcurves:
        for k in fc.keyframe_points:
            k.interpolation = "CONSTANT" if fc.data_path == "scale" else "LINEAR"
    bundles.append((b_ob, pos.copy(), landed))

# loose notes from each burst: kick up, flutter, wind carries them off to screen right (-Y) and up
for i, (b_ob, p0, landed) in enumerate(bundles):
    if landed is None or note_mesh is None:
        continue
    for j in range(9):
        n = D.objects.new(f"Burst_Note_{i}_{j}", note_mesh)
        col.objects.link(n)
        v = Vector((rng.uniform(-1.2, 0.8), rng.uniform(-1.5, 1.5), rng.uniform(1.2, 3.0)))
        p = p0.copy()
        ph = [rng.uniform(0, 6.3) for _ in range(3)]
        wind = Vector((rng.uniform(-0.3, 0.6), -rng.uniform(2.6, 4.2), rng.uniform(0.2, 0.9)))
        for f in range(F0, F1 + 1):
            alive = landed <= f
            if alive and f > landed:
                v += (wind - v) * 0.06                                       # drag towards the wind
                v.z -= 1.2 * dt
                p = p + v * dt
                p.z = max(p.z, 0.03)
            t_ = (f - landed) * dt
            n.location = p if alive else p0
            n.rotation_euler = (ph[0] + 7 * t_, ph[1] + 5 * t_ * math.sin(ph[2]), ph[2] + 3 * t_)
            gone = alive and (p.y < -84 or p.z > 9)
            n.scale = (1, 1, 1) if alive and not gone and f < F1 - 2 else (0, 0, 0)
            n.keyframe_insert("location", frame=f)
            n.keyframe_insert("rotation_euler", frame=f)
            n.keyframe_insert("scale", frame=f)
        for fc in channelbag(n).fcurves:
            for k in fc.keyframe_points:
                k.interpolation = "CONSTANT" if fc.data_path == "scale" else "LINEAR"

# ================================================================== 2. street lights + wires
SL = os.path.join(PROPS, "street-light")
pole_objs = imported(lambda: bpy.ops.wm.obj_import(filepath=os.path.join(SL, "src/Untitled_3.obj"),
                                                   forward_axis="NEGATIVE_Z", up_axis="Y"))
keep = {o.name for o in pole_objs if o.name in ("01", "02")}
for o in pole_objs:
    if o.name not in keep:
        D.objects.remove(o)
pole_src = D.objects["01"]
head_src = D.objects["02"]
pole_mat = tex_material("Pole_Concrete", os.path.join(SL, "textures/Untitled_1_DefaultMaterial_BaseColor.png"),
                        os.path.join(SL, "textures/Untitled_1_DefaultMaterial_Roughness.png"),
                        os.path.join(SL, "textures/Untitled_1_DefaultMaterial_Metallic.png"),
                        os.path.join(SL, "textures/Untitled_1_DefaultMaterial_Normal.png"))
head_mat = tex_material("Lamp_Head", os.path.join(SL, "textures/BaseColor.png"),
                        os.path.join(SL, "textures/Roughness.png"), os.path.join(SL, "textures/Metallic.png"),
                        os.path.join(SL, "textures/Untitled_3_02_1_Normal.png"),
                        os.path.join(SL, "textures/em.png"), 6.0)
for o, m_ in ((pole_src, pole_mat), (head_src, head_mat)):
    o.data.materials.clear()
    o.data.materials.append(m_)
bpy.ops.object.select_all(action="DESELECT")
pole_src.select_set(True)
head_src.select_set(True)
bpy.context.view_layer.objects.active = pole_src
bpy.ops.object.join()
pole_src.name = "StreetLight_src"
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
pole_src.data.transform(Matrix.Scale(0.01, 4))                              # model is in centimetres
lo, hi = bbox(pole_src)
print("pole bbox", lo, hi)
# pole base centre at origin; the arm points +X in the model
pole_src.data.transform(Matrix.Translation(-Vector((0.35, (lo.y + hi.y) / 2, lo.z))))
for c in list(pole_src.users_collection):
    c.objects.unlink(pole_src)
POLES = [(-53.15, -66.35), (-53.15, -79.15), (-53.15, -92.0), (-53.15, -53.5)]
lamps = []
tops = []
for i, (px, py) in enumerate(POLES):
    o = D.objects.new(f"StreetLight_{i}", pole_src.data)
    col.objects.link(o)
    o.location = (px, py, 0)
    o.rotation_euler = (0, 0, math.pi)                                        # arm over the road (-X)
    arm_end = o.matrix_world @ Vector((1.15, 0, 4.95))
    tops.append(o.matrix_world @ Vector((0.0, 0, 6.3)))
    L = D.objects.new(f"StreetLight_Lamp_{i}", D.lights.new(f"StreetLight_Lamp_{i}", "SPOT"))
    L.data.energy, L.data.color = 900, (1.0, 0.74, 0.45)
    L.data.spot_size, L.data.spot_blend, L.data.shadow_soft_size = math.radians(110), 0.6, 0.15
    L.location = arm_end
    L.rotation_euler = (0, 0, 0)                                             # spot shines down -Z
    L.visible_camera = False
    col.objects.link(L)
    lamps.append(L)
# flicker on the left lamp: two short stutters per loop (constant keys, closed loop)
fl = lamps[0].data
for f, k_ in ((1, 1), (40, 1), (41, 0.15), (43, 0.9), (44, 0.1), (47, 1), (163, 1), (164, 0.2), (166, 1), (F1 + 1, 1)):
    fl.energy = 900 * k_
    fl.keyframe_insert("energy", frame=f)
for fc in channelbag(fl).fcurves:
    for k in fc.keyframe_points:
        k.interpolation = "CONSTANT"
# sagging wires between pole tops (3 conductors), extended past the frame
wire_m = mat("Wire", (0.01, 0.01, 0.01), rough=0.4)
order = sorted(range(len(tops)), key=lambda i: tops[i].y)
for w_i, dz in enumerate((0.0, -0.25, -0.5)):
    cu = D.curves.new(f"Wire_{w_i}", "CURVE")
    cu.dimensions, cu.bevel_depth, cu.bevel_resolution = "3D", 0.008, 2
    sp = cu.splines.new("POLY")
    pts = []
    for a_, b_ in zip(order, order[1:]):
        A, B = tops[a_] + Vector((0.12 * (w_i - 1), 0, dz)), tops[b_] + Vector((0.12 * (w_i - 1), 0, dz))
        for s in range(16):
            u = s / 16
            p = A.lerp(B, u)
            p.z -= 0.9 * 4 * u * (1 - u)                                   # catenary-ish sag
            pts.append(p)
    pts.append(tops[order[-1]] + Vector((0.12 * (w_i - 1), 0, dz)))
    sp.points.add(len(pts) - 1)
    for pt, p in zip(sp.points, pts):
        pt.co = (*p, 1)
    ob = D.objects.new(f"Wire_{w_i}", cu)
    ob.data.materials.append(wire_m)
    col.objects.link(ob)

# ================================================================== 3. CCTV under the sign corners
cam_obj = join_into(imported(lambda: bpy.ops.import_scene.gltf(filepath=os.path.join(PROPS, "cctv-camera/source/camera.glb"))),
                    "CCTV_src")
fit(cam_obj, 2, 0.32, base=0.0, center_xy=(0, 0))
lo, hi = bbox(cam_obj)
cam_obj.data.transform(Matrix.Translation((0, 0, -hi.z)))                    # hang from the top of the mount
dark = mat("CCTV_Body", (0.018, 0.019, 0.021), rough=0.32, metal=0.3)
lens = mat("CCTV_Lens", (0.0, 0.0, 0.0), rough=0.03)
lo_, hi_ = bbox(cam_obj)
for i in range(len(cam_obj.data.materials)):
    cam_obj.data.materials[i] = dark                     # the scan's white plastic glows like a lamp at night
lens_slot = len(cam_obj.data.materials)
cam_obj.data.materials.append(lens)
for p in cam_obj.data.polygons:                           # dark glass on the lower, forward-facing dome
    if p.center.z < lo_.z + (hi_.z - lo_.z) * 0.35:
        p.material_index = lens_slot
for c in list(cam_obj.users_collection):
    c.objects.unlink(cam_obj)
for i, y in enumerate((-77.35, -69.65)):
    o = D.objects.new(f"CCTV_{i}", cam_obj.data)
    col.objects.link(o)
    o.location = (-52.72, y, 4.44)
    o.rotation_euler = (0, 0, math.radians(180 + (20 if i == 0 else -20)))
    led = D.objects.new(f"CCTV_LED_{i}", D.lights.new(f"CCTV_LED_{i}", "POINT"))
    led.data.energy, led.data.color, led.data.shadow_soft_size = 0.03, (1, 0.05, 0.05), 0.005
    led.location = o.location + Vector((-0.12, 0, -0.18))
    col.objects.link(led)

# ================================================================== 4. manhole + steam, cone, mat
mh = join_into(imported(lambda: bpy.ops.import_scene.gltf(filepath=os.path.join(PROPS, "manhole/scene.gltf"))), "Manhole")
MH = (-55.15, -72.55)
fit(mh, 0, 0.7, base=-0.005, center_xy=MH)
steam = D.materials.new("Steam")
nt = steam.node_tree
nt.nodes.remove(nt.nodes["Principled BSDF"])
vol = nt.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Color"].default_value = (0.85, 0.9, 0.88, 1)
vol.inputs["Anisotropy"].default_value = 0.4
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])


def noise_at(offset_expr, weight_expr):
    mp = nt.nodes.new("ShaderNodeMapping")
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    d_ = mp.inputs["Location"].driver_add("default_value", 2).driver
    d_.expression = offset_expr
    mp.inputs["Scale"].default_value = (2.2, 2.2, 0.9)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 1.6, 6
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    wv = nt.nodes.new("ShaderNodeValue")
    wv.outputs[0].driver_add("default_value").driver.expression = weight_expr
    m_ = nt.nodes.new("ShaderNodeMath")
    m_.operation = "MULTIPLY"
    nt.links.new(nz.outputs["Fac"], m_.inputs[0])
    nt.links.new(wv.outputs[0], m_.inputs[1])
    return m_


# seamless rising noise: blend the field scrolled by t*L with the one scrolled by (t-1)*L
a_ = noise_at(f"-((frame-1)%{LOOP})/{LOOP}*3.0", f"1-((frame-1)%{LOOP})/{LOOP}")
b_ = noise_at(f"-(((frame-1)%{LOOP})/{LOOP}-1)*3.0", f"((frame-1)%{LOOP})/{LOOP}")
add = nt.nodes.new("ShaderNodeMath")
add.operation = "ADD"
nt.links.new(a_.outputs[0], add.inputs[0])
nt.links.new(b_.outputs[0], add.inputs[1])
ramp = nt.nodes.new("ShaderNodeMapRange")
ramp.inputs["From Min"].default_value, ramp.inputs["From Max"].default_value = 0.4, 0.68
nt.links.new(add.outputs[0], ramp.inputs["Value"])
# column shape: dense at the bottom centre, fading up and out
rad = nt.nodes.new("ShaderNodeVectorMath")
rad.operation = "DISTANCE"
flat = nt.nodes.new("ShaderNodeVectorMath")
flat.operation = "MULTIPLY"
flat.inputs[1].default_value = (1.0, 1.0, 0.0)                              # radial distance in XY only
nt.links.new(tc.outputs["Generated"], flat.inputs[0])
nt.links.new(flat.outputs["Vector"], rad.inputs[0])
rad.inputs[1].default_value = (0.5, 0.5, 0.0)
shape = nt.nodes.new("ShaderNodeMapRange")
shape.inputs["From Min"].default_value, shape.inputs["From Max"].default_value = 0.08, 0.42
shape.inputs["To Min"].default_value, shape.inputs["To Max"].default_value = 1.0, 0.0
nt.links.new(rad.outputs["Value"], shape.inputs["Value"])
fade = nt.nodes.new("ShaderNodeMapRange")
fade.inputs["To Min"].default_value, fade.inputs["To Max"].default_value = 1.0, 0.0
nt.links.new(sep.outputs["Z"], fade.inputs["Value"])
m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
m3 = nt.nodes.new("ShaderNodeMath"); m3.operation = "MULTIPLY"; m3.inputs[1].default_value = 5.0
nt.links.new(ramp.outputs["Result"], m1.inputs[0]); nt.links.new(shape.outputs["Result"], m1.inputs[1])
nt.links.new(m1.outputs[0], m2.inputs[0]); nt.links.new(fade.outputs["Result"], m2.inputs[1])
nt.links.new(m2.outputs[0], m3.inputs[0])
nt.links.new(m3.outputs[0], vol.inputs["Density"])
nt.links.new(vol.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
bpy.ops.mesh.primitive_cube_add(size=1, location=(MH[0], MH[1], 1.6))
sb = bpy.context.object
sb.name = "Manhole_Steam"
sb.scale = (1.4, 1.4, 3.2)
sb.data.materials.append(steam)
sb.visible_shadow = False
for c in list(sb.users_collection):
    c.objects.unlink(sb)
col.objects.link(sb)
glow = D.objects.new("Manhole_Glow", D.lights.new("Manhole_Glow", "POINT"))
glow.data.energy, glow.data.color, glow.data.shadow_soft_size = 3, (1.0, 0.8, 0.6), 0.3
glow.visible_glossy = False                                                 # no hot spot mirrored in the puddles
glow.location = (MH[0], MH[1], 0.15)
col.objects.link(glow)

cone = join_into(imported(lambda: bpy.ops.import_scene.fbx(filepath=os.path.join(PROPS, "traffic-cone/source/cone.fbx"))), "Cone")
CT = os.path.join(PROPS, "traffic-cone/textures")
cone.data.materials.clear()
cone.data.materials.append(tex_material("Cone", os.path.join(CT, "cone_low_cone_BaseColor.tga.png"),
                                        os.path.join(CT, "cone_low_cone_Roughness.tga.png"), None,
                                        os.path.join(CT, "cone_low_cone_Normal.tga.png")))
fit(cone, 2, 0.55, base=0.0, center_xy=(-55.85, -71.95))

mat_m = tex_material("EM_Mat", os.path.join(TEX, "em_mat.png"))
mat_m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
me = D.meshes.new("em_mat")
X0, Y0, w_, l_ = -53.5, -73.49, 1.1, 1.8
me.from_pydata([(X0 - w_ / 2, Y0 + l_ / 2, 0.012), (X0 + w_ / 2, Y0 + l_ / 2, 0.012), (X0 + w_ / 2, Y0 - l_ / 2, 0.012),
                (X0 - w_ / 2, Y0 - l_ / 2, 0.012)], [], [(0, 1, 2, 3)])
uv = me.uv_layers.new()
for li, u in enumerate([(0, 1), (0, 0), (1, 0), (1, 1)]):
    uv.data[li].uv = u
me.materials.append(mat_m)
col.objects.link(D.objects.new("EM_Mat", me))

# ================================================================== 5. puddles in the cobblestone
g = D.materials["cobblestone_embedded_asphalt"]
nt = g.node_tree
b = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
tc = nt.nodes.new("ShaderNodeTexCoord")
nz = nt.nodes.new("ShaderNodeTexNoise")
nz.inputs["Scale"].default_value, nz.inputs["Detail"].default_value = 0.22, 4
nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
mask = nt.nodes.new("ShaderNodeMapRange")
mask.inputs["From Min"].default_value, mask.inputs["From Max"].default_value = 0.6, 0.64
nt.links.new(nz.outputs["Fac"], mask.inputs["Value"])
r_link = b.inputs["Roughness"].links[0] if b.inputs["Roughness"].is_linked else None
mixr = nt.nodes.new("ShaderNodeMix")
mixr.data_type = "FLOAT"
nt.links.new(mask.outputs["Result"], mixr.inputs[0])
if r_link:
    nt.links.new(r_link.from_socket, mixr.inputs[2])
else:
    mixr.inputs[2].default_value = b.inputs["Roughness"].default_value
mixr.inputs[3].default_value = 0.03
nt.links.new(mixr.outputs[0], b.inputs["Roughness"])
c_link = b.inputs["Base Color"].links[0] if b.inputs["Base Color"].is_linked else None
if c_link:
    mixc = nt.nodes.new("ShaderNodeMix")
    mixc.data_type, mixc.blend_type = "RGBA", "MULTIPLY"
    nt.links.new(mask.outputs["Result"], mixc.inputs[0])
    nt.links.new(c_link.from_socket, mixc.inputs[6])
    mixc.inputs[7].default_value = (0.35, 0.35, 0.37, 1)
    nt.links.new(mixc.outputs[2], b.inputs["Base Color"])
n_link = b.inputs["Normal"].links[0] if b.inputs["Normal"].is_linked else None
if n_link:                                                                  # water is flat
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mixn = nt.nodes.new("ShaderNodeMix")
    mixn.data_type = "VECTOR"
    nt.links.new(mask.outputs["Result"], mixn.inputs[0])
    nt.links.new(n_link.from_socket, mixn.inputs[4])
    nt.links.new(geo.outputs["Normal"], mixn.inputs[5])
    nt.links.new(mixn.outputs[1], b.inputs["Normal"])

for ob in D.objects:                         # Cycles draws point/spot lamps as glowing balls: keep the light only
    if ob.type == "LIGHT" and ob.data.type in ("POINT", "SPOT"):
        ob.visible_camera = False
        ob.visible_glossy = ob.visible_glossy and ob.name != "Point"
for img in D.images:
    if img.filepath.startswith(("/tmp", "/home")) and not img.packed_file:
        img.pack()
scn.frame_set(F0)
scn.frame_start, scn.frame_end = 1, 250     # imports must not touch the loop range

bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT)
