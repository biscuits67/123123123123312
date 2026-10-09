"""Builds the hooded hero for the Emerald exchange scene from separate pieces:

    Y Bot + Neutral Idle (Mixamo, FBX with skin), Balenciaga hoodie (Marvelous Designer FBX),
    skinny pants (FBX), one Balenciaga Defender scan (OBJ) mirrored for the other foot.

The clothes were made in an "arms down" pose, so the rig is first posed to match them (fit pose),
weights are transferred from the posed Y Bot surface, and the clothes are then un-skinned back
into the rig's rest pose (inverse linear blend skinning). After that they follow any Mixamo
animation of the same skeleton. The body is kept only where it shows: gloved hands and a
balaclava head.

    blender -b -P hero_build.py -- IDLE.fbx HOODIE.fbx HOODIE_TEX.png PANTS.fbx PANTS_TEX_DIR SHOE.obj \
        BALACLAVA.fbx BALACLAVA_TEX.jpg OUT.blend
"""
import math
import os
import sys

import bpy  # noqa: E402  (bpy must come before bmesh/mathutils when run as a module)
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

IDLE, HOODIE, HOODIE_TEX, PANTS, PANTS_TEX, SHOE, BALA, BALA_TEX, OUT = sys.argv[sys.argv.index("--") + 1:]
P = "mixamorig:"

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene


def imported(fn):
    before = set(bpy.data.objects)
    fn()
    bpy.context.view_layer.update()
    return [o for o in bpy.data.objects if o not in before]


# ---------------------------------------------------------------- rig + body
objs = imported(lambda: bpy.ops.import_scene.fbx(filepath=IDLE))
arm = next(o for o in objs if o.type == "ARMATURE")
arm.name = arm.data.name = "Hero_Rig"
action = arm.animation_data.action
action.name = "Hero_Idle"
f0, f1 = (int(x) for x in action.frame_range)
arm.animation_data.action = None
for pb in arm.pose.bones:  # the import leaves the idle's first frame on the bones: start from the rest pose
    pb.matrix_basis.identity()
bpy.context.view_layer.update()
surf = bpy.data.objects["Alpha_Surface"]
joints = bpy.data.objects["Alpha_Joints"]
A = arm.matrix_world.copy()
Ainv = A.inverted()


def bone_head(name):
    return A @ arm.data.bones[P + name].head_local


# fit pose: upright rest pose with the arms hanging into the sleeves, legs open slightly into the trouser legs
CUFF = {"Left": Vector((0.262, -0.02, 0.93)), "Right": Vector((-0.258, -0.02, 0.945))}
for side in ("Left", "Right"):
    pb = arm.pose.bones[P + side + "Arm"]
    head = bone_head(side + "Arm")
    rest_dir = (A.to_3x3() @ (arm.data.bones[P + side + "Arm"].tail_local - arm.data.bones[P + side + "Arm"].head_local)).normalized()
    rot = rest_dir.rotation_difference((CUFF[side] - head).normalized())
    m_world = Matrix.Translation(head) @ rot.to_matrix().to_4x4() @ Matrix.Translation(-head) @ (A @ arm.data.bones[P + side + "Arm"].matrix_local)
    pb.matrix = Ainv @ m_world
    bpy.context.view_layer.update()
    sgn = 1 if side == "Left" else -1
    leg = arm.pose.bones[P + side + "UpLeg"]
    head = bone_head(side + "UpLeg")
    rot = Matrix.Rotation(math.radians(2.2) * sgn, 4, "Y")
    leg.matrix = Ainv @ (Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ (A @ arm.data.bones[P + side + "UpLeg"].matrix_local))
    bpy.context.view_layer.update()

bones = [b.name for b in arm.data.bones]
bidx = {n: i for i, n in enumerate(bones)}
skin = np.array([np.array(arm.pose.bones[n].matrix @ arm.data.bones[n].matrix_local.inverted()) for n in bones])  # armature space


def posed_body(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices])
    me.calc_loop_triangles()
    tris = np.array([tuple(t.vertices) for t in me.loop_triangles])
    ev.to_mesh_clear()
    W = np.zeros((len(ob.data.vertices), len(bones)), np.float32)
    names = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        for g in v.groups:
            if names[g.group] in bidx:
                W[v.index, bidx[names[g.group]]] = g.weight
    W /= np.maximum(W.sum(1, keepdims=True), 1e-8)
    return co, tris, W


bco, btris, bW = posed_body(surf)
dominant = np.array(bones)[bW.argmax(1)]


def is_arm(n, side):
    return n.startswith(P + side) and any(k in n for k in ("Shoulder", "Arm", "Hand"))


def is_leg(n, side):
    return n.startswith(P + side) and any(k in n for k in ("Leg", "Foot", "Toe"))


REGIONS = {
    "armL": lambda n: is_arm(n, "Left"),
    "armR": lambda n: is_arm(n, "Right"),
    "legL": lambda n: is_leg(n, "Left") or n.endswith("Hips"),
    "legR": lambda n: is_leg(n, "Right") or n.endswith("Hips"),
    "trunk": lambda n: not any(k in n for k in ("ForeArm", "Hand", "Leg", "Foot", "Toe")),
}
bvh = {}
for key, test in REGIONS.items():
    ok = np.array([test(n) for n in dominant])
    t = btris[ok[btris].all(1)]
    bvh[key] = BVHTree.FromPolygons([Vector(c) for c in bco], [tuple(x) for x in t])


def transfer(points, region_of):
    """Barycentric weights from the nearest posed body triangle of the given region."""
    W = np.zeros((len(points), len(bones)), np.float32)
    for i, p in enumerate(points):
        loc, nrm, fi, d = bvh[region_of[i]].find_nearest(Vector(p))
        key = region_of[i]
        if fi is None:
            key = "trunk"
            loc, nrm, fi, d = bvh[key].find_nearest(Vector(p))
        tri = bvh_tris[key][fi]
        a, b, c = (bco[j] for j in tri)
        v0, v1, v2 = b - a, c - a, np.array(loc) - a
        d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
        den = d00 * d11 - d01 * d01 or 1e-12
        wb, wc = (d11 * d20 - d01 * d21) / den, (d00 * d21 - d01 * d20) / den
        bary = np.clip([1 - wb - wc, wb, wc], 0, 1)
        W[i] = bary @ bW[list(tri)]
    return W


bvh_tris = {}
for key, test in REGIONS.items():
    ok = np.array([test(n) for n in dominant])
    bvh_tris[key] = btris[ok[btris].all(1)]


def smooth(W, edges, iters, lock=None):
    """Laplacian smoothing of skin weights over the mesh graph (keeps seams and folds together)."""
    deg = np.zeros(len(W))
    np.add.at(deg, edges[:, 0], 1)
    np.add.at(deg, edges[:, 1], 1)
    for _ in range(iters):
        acc = np.zeros_like(W)
        np.add.at(acc, edges[:, 0], W[edges[:, 1]])
        np.add.at(acc, edges[:, 1], W[edges[:, 0]])
        new = 0.5 * W + 0.5 * acc / np.maximum(deg, 1)[:, None]
        if lock is not None:
            new[lock] = W[lock]
        W = new
    return W / np.maximum(W.sum(1, keepdims=True), 1e-8)


def unskin(points, W):
    """Inverse LBS: posed world points -> rest world points."""
    q = np.c_[points, np.ones(len(points))] @ np.array(Ainv).T
    S = np.einsum("nb,bij->nij", W, skin)
    weak = np.abs(np.linalg.det(S[:, :3, :3])) < 0.35  # blends of very different rotations: use the main bone
    S[weak] = skin[W[weak].argmax(1)]
    r = np.einsum("nij,nj->ni", np.linalg.inv(S), q)
    return (r @ np.array(A).T)[:, :3]


def bind(ob, W, top=4):
    ob.vertex_groups.clear()
    groups = {}
    order = np.argsort(-W, 1)[:, :top]
    for i in range(len(W)):
        w = W[i, order[i]]
        w = w / max(w.sum(), 1e-8)
        for b, x in zip(order[i], w):
            if x > 1e-3:
                if b not in groups:
                    groups[b] = ob.vertex_groups.new(name=bones[b])
                groups[b].add([i], float(x), "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    ob.parent = arm
    ob.matrix_parent_inverse = arm.matrix_world.inverted()


def world_points(ob):
    return np.array([tuple(ob.matrix_world @ v.co) for v in ob.data.vertices])


def set_points(ob, pts):
    ob.matrix_world = Matrix.Identity(4)
    ob.data.vertices.foreach_set("co", pts.astype(np.float32).ravel())
    ob.data.update()


def mesh_edges(ob):
    return np.array([tuple(e.vertices) for e in ob.data.edges])


def material(name, color, rough, sheen=0.0, tex=None, normal=None, rough_tex=None):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Sheen Weight"].default_value = sheen
    bsdf.inputs["Sheen Roughness"].default_value = 0.6
    if tex:
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(tex)
        nt.links.new(n.outputs["Color"], bsdf.inputs["Base Color"])
    if rough_tex:
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(rough_tex)
        n.image.colorspace_settings.name = "Non-Color"
        nt.links.new(n.outputs["Color"], bsdf.inputs["Roughness"])
    if normal:
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(normal)
        n.image.colorspace_settings.name = "Non-Color"
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 0.8
        nt.links.new(n.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


# ---------------------------------------------------------------- hoodie
hood_objs = [o for o in imported(lambda: bpy.ops.import_scene.fbx(filepath=HOODIE)) if o.type == "MESH"]
SHIFT = Vector((-0.1, -1.616, -0.03))
pieces, region = [], []
for o in hood_objs:
    pts = world_points(o) * 100 + np.array(SHIFT)
    cx = pts[:, 0].mean()
    reg = "armL" if cx > 0.15 else "armR" if cx < -0.15 else "trunk"
    pieces.append((o, pts, reg))
for o, pts, reg in pieces:
    for k in list(o.keys()):
        del o[k]
    o.parent = None
    set_points(o, pts)
    attr = o.data.attributes.new("region", "INT", "POINT")
    attr.data.foreach_set("value", [("trunk", "armL", "armR").index(reg)] * len(pts))
bpy.ops.object.select_all(action="DESELECT")
for o, _, _ in pieces:
    o.select_set(True)
bpy.context.view_layer.objects.active = pieces[0][0]
bpy.ops.object.join()
hoodie = pieces[0][0]
hoodie.name = "Hero_Hoodie"
for o in [o for o in bpy.data.objects if o.type == "EMPTY"]:
    bpy.data.objects.remove(o)
# region per vertex follows the piece it came from (stored as an attribute: join reorders pieces)
codes = [0] * len(hoodie.data.vertices)
hoodie.data.attributes["region"].data.foreach_get("value", codes)
reg_v = [("trunk", "armL", "armR")[c] for c in codes]
hp = world_points(hoodie)
hW = transfer(hp, reg_v)
# weld seams for weighting: link coincident vertices of neighbouring pieces
kd = KDTree(len(hp))
for i, p in enumerate(hp):
    kd.insert(p, i)
kd.balance()
seam = [(i, j) for i, p in enumerate(hp) for (_, j, d) in kd.find_range(p, 0.004) if j > i]
edges = np.vstack([mesh_edges(hoodie), np.array(seam).reshape(-1, 2)])
hW = smooth(hW, edges, 25)
# the hood turns with the head (otherwise the head swings into the fabric): ramp in the head bone
hood = (hp[:, 2] > 1.5) & (np.abs(hp[:, 0]) < 0.2)
ramp = np.clip((hp[:, 2] - 1.53) / 0.12, 0, 1) ** 1.2 * 0.9 * hood
hW *= (1 - ramp)[:, None]
hW[:, bidx[P + "Head"]] += ramp
hW = smooth(hW, edges, 6)
set_points(hoodie, unskin(hp, hW))
bind(hoodie, hW)
hoodie.data.materials.clear()
hm = material("Hoodie", (0.02, 0.02, 0.022), 0.85, sheen=0.12, tex=HOODIE_TEX)
# the texture is a grey hoodie with an off-white print: keep the print, dye the cotton black
nt = hm.node_tree
img = next(n for n in nt.nodes if n.type == "TEX_IMAGE")
bw = nt.nodes.new("ShaderNodeRGBToBW")
mr = nt.nodes.new("ShaderNodeMapRange")
mr.interpolation_type = "SMOOTHSTEP"
mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.25, 0.5
mix = nt.nodes.new("ShaderNodeMix")
mix.data_type = "RGBA"
col_a, col_b = (i for i in mix.inputs if i.type == "RGBA")  # Mix has a socket per data type
col_a.default_value = (0.014, 0.014, 0.016, 1)
col_b.default_value = (0.62, 0.6, 0.55, 1)
nt.links.new(img.outputs["Color"], bw.inputs["Color"])
nt.links.new(bw.outputs["Val"], mr.inputs["Value"])
nt.links.new(mr.outputs["Result"], mix.inputs[0])
nt.links.new(next(o for o in mix.outputs if o.type == "RGBA"), nt.nodes["Principled BSDF"].inputs["Base Color"])
hoodie.data.materials.append(hm)

# ---------------------------------------------------------------- pants
pants = next(o for o in imported(lambda: bpy.ops.import_scene.fbx(filepath=PANTS)) if o.type == "MESH")
pants.name = "Hero_Pants"
mw = pants.matrix_world.copy()
pants.parent = None
bm = bmesh.new()
bm.from_mesh(pants.data)
bm.transform(mw)
# the waistband is hidden by the hoodie and would poke through its front: cut it off
bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 0.98], context="VERTS")
bm.to_mesh(pants.data)
bm.free()
pants.matrix_world = Matrix.Identity(4)
pp = world_points(pants)
reg_v = ["legL" if (p[2] < 0.85 and p[0] > 0) else "legR" if p[2] < 0.85 else "trunk" for p in pp]
pW = smooth(transfer(pp, reg_v), mesh_edges(pants), 15)
set_points(pants, unskin(pp, pW))
bind(pants, pW)
tex = lambda kind: os.path.join(PANTS_TEX, f"Pants Skinny LP_Denim_FRONT_2632_{kind}.png")
pants.data.materials.clear()
pants.data.materials.append(material("Pants", (0.03, 0.03, 0.03), 0.8, sheen=0.15, tex=tex("BaseColor"),
                                     normal=tex("Normal"), rough_tex=tex("Roughness")))

# ---------------------------------------------------------------- shoes (scan, one foot)
shoe = next(o for o in imported(lambda: bpy.ops.wm.obj_import(filepath=SHOE)) if o.type == "MESH")
bm = bmesh.new()
bm.from_mesh(shoe.data)
islands, seen = [], set()
for f in bm.faces:
    if f.index in seen:
        continue
    stack, isl = [f], []
    seen.add(f.index)
    while stack:
        g = stack.pop()
        isl.append(g)
        for e in g.edges:
            for h in e.link_faces:
                if h.index not in seen:
                    seen.add(h.index)
                    stack.append(h)
    islands.append(isl)
keep = max(islands, key=len)
bmesh.ops.delete(bm, geom=[f for isl in islands if isl is not keep for f in isl], context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.to_mesh(shoe.data)
bm.free()
sp = world_points(shoe)
# the scan lies with its opening towards -Y and the toe towards +X: stand it up, toe forward (-Y)
R = np.array(Matrix.Rotation(math.radians(-90), 3, "Z") @ Matrix.Rotation(math.radians(-90), 3, "X"))
sp = sp @ R.T
sp -= [(sp[:, 0].max() + sp[:, 0].min()) / 2, (sp[:, 1].max() + sp[:, 1].min()) / 2, sp[:, 2].min()]
sp *= 0.31 / (sp[:, 1].max() - sp[:, 1].min())
sole_z = bco[np.array([("Foot" in n or "Toe" in n) for n in dominant])][:, 2].min()
shoes = []
for side, sgn in (("Left", 1), ("Right", -1)):
    ob = shoe if side == "Left" else bpy.data.objects.new("shoe", shoe.data.copy())
    if ob is not shoe:
        scn.collection.objects.link(ob)
    ob.name = f"Hero_Shoe_{side}"
    # collar of the shoe right under the trouser hem, sole on the posed Y Bot sole
    leg = pp[(pp[:, 0] * sgn > 0) & (pp[:, 2] < 0.4)]
    hem = leg[leg[:, 2] < leg[:, 2].min() + 0.02][:, :2].mean(0)
    pts = sp * [sgn, 1, 1]
    collar = pts[pts[:, 2] > pts[:, 2].max() - 0.03][:, :2].mean(0)
    pts += [hem[0] - collar[0], hem[1] - collar[1] - 0.012, max(sole_z, 0.0) - 0.006]
    set_points(ob, pts)
    if sgn < 0:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(ob.data)
        bm.free()
    W = np.zeros((len(pts), len(bones)), np.float32)
    W[:, bidx[P + side + "Foot"]] = 1
    set_points(ob, unskin(pts, W))
    bind(ob, W)
    ob.data.materials.clear()
    ob.data.materials.append(bpy.data.materials.get("Shoe") or material("Shoe", (0.018, 0.018, 0.02), 0.62))
    shoes.append(ob)

# ---------------------------------------------------------------- body: gloves + balaclava
glove = material("Gloves", (0.012, 0.012, 0.013), 0.55, sheen=0.4)
mask = material("Balaclava", (0.01, 0.01, 0.011), 0.9, sheen=0.6)
eye_skin = material("Skin", (0.11, 0.072, 0.054), 0.5, sheen=0.1)


def keep_part(n, co):
    if "Hand" in n:
        return True
    if "ForeArm" in n:  # long cuff of the glove so no gap shows under the sleeve
        side = "Left" if "Left" in n else "Right"
        return (Vector(co) - (A @ arm.pose.bones[P + side + "Hand"].head)).length < 0.17
    return False


for ob in (surf, joints):
    co, _, W = posed_body(ob)
    dom = np.array(bones)[W.argmax(1)]
    keepv = np.array([keep_part(n, c) for n, c in zip(dom, co)])
    keepv &= ~(np.array([n.endswith(("Head", "HeadTop_End")) for n in dom]) & (co[:, 1] > 0.045))  # back of the head: hidden by the hood
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not keepv[v.index]], context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    head = A @ arm.data.bones[P + "Head"].head_local + Vector((0, 0, 0.09))
    names = {g.index: g.name for g in ob.vertex_groups}
    for v in ob.data.vertices:
        wh = sum(g.weight for g in v.groups if names[g.group].endswith(("Head", "HeadTop_End")))
        if wh > 0.5:  # rest pose == world here (arm hangs only in the pose), so scale in world space
            w = ob.matrix_world @ v.co
            w = head + (w - head) * 0.86 + Vector((0, -0.012, -0.01))
            v.co = ob.matrix_world.inverted() @ w
    ob.data.materials.clear()
    ob.data.materials.append(glove)
    ob.data.materials.append(mask)
    ob.data.materials.append(eye_skin)
    names = {g.index: g.name for g in ob.vertex_groups}
    for poly in ob.data.polygons:
        ws = {}
        for vi in poly.vertices:
            for g in ob.data.vertices[vi].groups:
                ws[names[g.group]] = ws.get(names[g.group], 0) + g.weight
        top = max(ws, key=ws.get) if ws else ""
        poly.material_index = 1 if top.endswith(("Head", "HeadTop_End", "Neck")) else 0
        c = ob.matrix_world @ poly.center
        if poly.material_index == 1 and 1.684 < c.z < 1.706 and c.y < -0.095 and abs(c.x) < 0.05:
            poly.material_index = 2  # eye slit of the balaclava
    ob.name = "Hero_Hands_Head" if ob is surf else "Hero_Joints"

# balaclava (Genesis 8 knit mask) scaled into the hood, with a face behind the eye opening
bal = next(o for o in imported(lambda: bpy.ops.import_scene.fbx(filepath=BALA)) if o.type == "MESH")
bal.name = "Hero_Balaclava"
for m in list(bal.modifiers):
    bal.modifiers.remove(m)
bm = bmesh.new()
bm.from_mesh(bal.data)
bm.transform(bal.matrix_world)
lo, hi = (np.array([v.co[:] for v in bm.verts]).min(0), np.array([v.co[:] for v in bm.verts]).max(0))
k = 0.146 / (hi[0] - lo[0])
bmesh.ops.transform(bm, verts=bm.verts, matrix=Matrix.Scale(k, 4))
lo, hi = lo * k, hi * k
top = 1.81
shift = Vector((-(lo[0] + hi[0]) / 2, -0.02 - (lo[1] + hi[1]) / 2, top - hi[2]))
bmesh.ops.translate(bm, verts=bm.verts, vec=shift)
rim = [v.co.copy() for e in bm.edges if e.is_boundary for v in e.verts]
zmin = min(v.co.z for v in bm.verts)
hole = sum((c for c in rim if c.z > zmin + 0.06), Vector()) / max(1, len([c for c in rim if c.z > zmin + 0.06]))
bm.to_mesh(bal.data)
bm.free()
bal.parent = None
bal.matrix_world = Matrix.Identity(4)
for ob in [o for o in bpy.data.objects if o.type == "ARMATURE" and o is not arm]:
    bpy.data.objects.remove(ob)
knit = material("Balaclava", (0.012, 0.012, 0.013), 0.9, sheen=0.45, tex=BALA_TEX)
bal.data.materials.clear()
bal.data.materials.append(knit)
for p in bal.data.polygons:
    p.material_index = 0
co = world_points(bal)
W = np.zeros((len(co), len(bones)), np.float32)
t = np.clip((co[:, 2] - 1.6) / 0.05, 0, 1)  # neck tube follows the neck, the rest the head
W[:, bidx[P + "Head"]] = t
W[:, bidx[P + "Neck"]] = 1 - t
bind(bal, W)

# face behind the opening: closed dark skin, rigid on the head
C = Vector((0.0, hole.y + 0.006 + 0.08, hole.z - 0.012))
me = bpy.data.meshes.new("face")
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=24, radius=1.0)
for v in bm.verts:
    v.co = C + Vector((v.co.x * 0.062, v.co.y * 0.08, v.co.z * 0.095))
bm.to_mesh(me)
bm.free()
head = bpy.data.objects.new("Hero_Face", me)
scn.collection.objects.link(head)
head.data.materials.append(eye_skin)
W = np.zeros((len(me.vertices), len(bones)), np.float32)
W[:, bidx[P + "Head"]] = 1
bind(head, W)  # head and neck are not posed in the fit pose: rest space == fit space here
eye_mat = material("Eyes", (0.015, 0.012, 0.01), 0.04)
eyes = [bal, head]
for sx in (-0.026, 0.026):
    front = C.y - 0.08 * math.sqrt(max(0.0, 1 - (sx / 0.062) ** 2 - ((hole.z - C.z) / 0.095) ** 2))
    me = bpy.data.meshes.new("eye")
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.0095,
                              matrix=Matrix.Translation((sx, front + 0.006, hole.z)))
    bm.to_mesh(me)
    bm.free()
    e = bpy.data.objects.new("Hero_Eye_L" if sx > 0 else "Hero_Eye_R", me)
    scn.collection.objects.link(e)
    e.data.materials.append(eye_mat)
    W = np.zeros((len(me.vertices), len(bones)), np.float32)
    W[:, bidx[P + "Head"]] = 1
    bind(e, W)
    eyes.append(e)

# ---------------------------------------------------------------- finish: rest pose + idle loop
for pb in arm.pose.bones:
    pb.matrix_basis.identity()
bpy.context.view_layer.update()


def aim(name, y_dir, z_hint):
    """Pose a bone (torso at rest) so its Y axis points along y_dir with its palm axis (+Z) towards z_hint;
    returns the local rotation, which then rides on whatever the idle does with the shoulder and spine."""
    pb = arm.pose.bones[P + name]
    y = Vector(y_dir).normalized()
    z = (Vector(z_hint) - y * Vector(z_hint).dot(y)).normalized()
    rot = Matrix((y.cross(z), y, z)).transposed()  # columns X, Y, Z
    head = A @ pb.head
    pb.matrix = Ainv @ (Matrix.Translation(head) @ rot.to_4x4()) @ Matrix.Scale(100, 4)
    bpy.context.view_layer.update()
    return pb.rotation_quaternion.copy()


def hold_pose(lift):
    """Right forearm out at the side, palm up; lift (0..1) raises the forearm a little."""
    up = math.radians(14) * lift
    d1 = Vector((-0.2, -0.16 - 0.1 * lift, -0.97)).normalized()          # elbow stays by the side
    d2 = Vector((-0.42, -0.86 * math.cos(up), 0.12 + 0.86 * math.sin(up))).normalized()  # forward and out
    d3 = Vector((d2.x, d2.y, -0.06)).normalized()  # flat open palm whatever the lift
    q = [aim("RightArm", d1, (0.6, 0, -0.8)),
         aim("RightForeArm", d2, (0.35, 0, 0.94)),   # twist split between forearm and wrist
         aim("RightHand", d3, (0, 0, 1))]
    for n in ("RightArm", "RightForeArm", "RightHand"):
        arm.pose.bones[P + n].matrix_basis.identity()
    return q


# armature scale is 0.01 and pb.matrix is in armature space: undo it in aim() via Scale(100)
q_low, q_high = hold_pose(0.0), hold_pose(1.0)
LOOP = f1 - f0  # the Mixamo idle closes on itself: frame f1 == frame f0
arm.animation_data.action = action
for f in range(f0, f1 + 1):
    w = 0.5 - 0.5 * math.cos(2 * math.pi * (f - f0) * 2 / LOOP)  # two gentle lifts per loop
    for n, a_, b_ in zip(("RightArm", "RightForeArm", "RightHand"), q_low, q_high):
        pb = arm.pose.bones[P + n]
        pb.rotation_quaternion = a_.slerp(b_, w)
        pb.keyframe_insert("rotation_quaternion", frame=f)
# open, relaxed fingers on the holding hand: drop the idle's finger curl (rest pose = straight fingers)
bag = action.layers[0].strips[0].channelbag(arm.animation_data.action_slot)
for fc in list(bag.fcurves):
    if f'"{P}RightHand' in fc.data_path and f'"{P}RightHand"' not in fc.data_path:
        bag.fcurves.remove(fc)
for pb in arm.pose.bones:
    if pb.name.startswith(P + "RightHand") and pb.name != P + "RightHand":
        pb.matrix_basis = Matrix.Rotation(math.radians(8), 4, "X")  # a hint of curl
scn.frame_start, scn.frame_end = f0, f1 - 1  # 420 frames; frame f1 would repeat frame f0

# ---------------------------------------------------------------- levitating emerald over the palm
me = bpy.data.meshes.new("emerald")
bm = bmesh.new()
bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.035, radius2=0.035, depth=0.03)
for sign in (1, -1):  # step-cut crown and pavilion: inset, lift, taper
    cap = [f for f in bm.faces if len(f.verts) == 8 and f.normal.z * sign > 0.9][0]
    bmesh.ops.inset_individual(bm, faces=[cap], thickness=0.01)
    ext = bmesh.ops.extrude_face_region(bm, geom=[cap])
    verts = [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=verts, vec=(0, 0, 0.008 * sign))
    c = sum((v.co for v in verts), Vector()) / len(verts)
    bmesh.ops.scale(bm, verts=verts, vec=(0.6, 0.6, 1), space=Matrix.Translation(-c))
bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.radians(90), 3, "X"))  # table faces the viewer
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(me)
bm.free()
gem = bpy.data.objects.new("Hero_Emerald", me)
scn.collection.objects.link(gem)
gm = material("Emerald", (0.043, 0.56, 0.31), 0.02)
b = gm.node_tree.nodes["Principled BSDF"]
b.inputs["IOR"].default_value = 1.58
b.inputs["Transmission Weight"].default_value = 1.0
b.inputs["Emission Color"].default_value = (0.1, 0.77, 0.54, 1)
b.inputs["Emission Strength"].default_value = 0.3
gem.data.materials.append(gm)
glow = bpy.data.objects.new("Hero_Emerald_Glow", bpy.data.lights.new("Hero_Emerald_Glow", "POINT"))
glow.data.energy, glow.data.color, glow.data.shadow_soft_size = 12, (0.15, 1.0, 0.55), 0.02
scn.collection.objects.link(glow)
for ob in (gem, glow):
    c = ob.constraints.new("COPY_LOCATION")
    c.target, c.subtarget, c.head_tail, c.use_offset = arm, P + "RightHand", 0.6, True
    # loop-safe motion (simple expressions, no Python needed): 4 bobs and 2 turns per 420-frame loop
    d = ob.driver_add("location", 2).driver
    d.type, d.expression = "SCRIPTED", "0.09 + 0.012*sin((frame-1)*0.0598399)"
gem.rotation_euler = (0, 0, 0)
gem.scale = (1.4, 1.4, 1.4)  # reads better in the wide shot
d = gem.driver_add("rotation_euler", 2).driver
d.type, d.expression = "SCRIPTED", "(frame-1)*0.0299199"

scn.render.fps = 24
col = bpy.data.collections.new("Hero")
scn.collection.children.link(col)
for ob in [arm, hoodie, pants, surf, joints, *shoes, *eyes, gem, glow]:
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    col.objects.link(ob)
for ob in list(bpy.data.objects):
    if ob.name not in col.objects:
        bpy.data.objects.remove(ob)
for ob in col.objects:
    if ob.type == "MESH":
        for p in ob.data.polygons:
            p.use_smooth = True
bpy.ops.outliner.orphans_purge(do_recursive=True)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print("saved", OUT, f0, f1)
