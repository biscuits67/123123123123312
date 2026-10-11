"""Give the hero real hands: cut Remy's (Mixamo) hands out, refit them bone by bone onto Hero_Rig,
skin them to the same bones, dress them as black leather gloves and mask the mannequin hands.

exec()'d by build_ava.py after the hero is in the scene; needs REMY_FBX, rig, D (and P = "mixamorig:").
"""
import bpy
from mathutils import Matrix, Vector

HAND_KEYS = ("Hand",)                   # LeftHand*, RightHand* and all finger bones
REACH = 0.075                           # m of forearm kept above the wrist (goes under the sleeve)

before = set(D.objects)
bpy.ops.import_scene.fbx(filepath=REMY_FBX)
remy_objs = [o for o in D.objects if o not in before]
r_arm = next(o for o in remy_objs if o.type == "ARMATURE")
body = next(o for o in remy_objs if o.type == "MESH" and o.name.startswith("Body"))
bpy.context.view_layer.update()

r_bones, h_bones = r_arm.data.bones, rig.data.bones
r_inv = r_arm.matrix_world.inverted()


def is_hand(name):
    return name.startswith(P) and any(k in name for k in HAND_KEYS) and "ForeArm" not in name


# per-bone rest maps Remy armature space -> hero armature space, scaled by the hand-length ratio
scale = {}
for side in ("Left", "Right"):
    a = h_bones[P + side + "Hand"]
    b = r_bones[P + side + "Hand"]
    mid_h = h_bones[P + side + "HandMiddle1"].head_local - a.head_local
    mid_r = r_bones[P + side + "HandMiddle1"].head_local - b.head_local
    scale[side] = mid_h.length / mid_r.length
MAP = {}
for b in r_bones:
    if b.name in h_bones:
        side = "Left" if "Left" in b.name else "Right"
        s = scale[side]
        hb = h_bones[b.name]
        MAP[b.name] = (hb.matrix_local @ Matrix.Scale(s, 4) @ b.matrix_local.inverted())

# vertices: hand-weighted, plus the forearm close to the wrist
groups = {g.index: g.name for g in body.vertex_groups}
me = body.data
keep = set()
vw = {}
for v in me.vertices:
    ws = {groups[g.group]: g.weight for g in v.groups if g.weight > 0.001}
    hand_w = sum(w for n, w in ws.items() if is_hand(n))
    p_arm = r_inv @ (body.matrix_world @ v.co)
    near = False
    for side in ("Left", "Right"):
        hb = r_bones[P + side + "Hand"]
        if ws.get(P + side + "ForeArm", 0) > 0.2 and (p_arm - hb.head_local).length * r_arm.scale[0] < REACH:
            near = True
    if hand_w > 0.3 or near:
        keep.add(v.index)
        vw[v.index] = (p_arm, ws)
faces = [list(p.vertices) for p in me.polygons if all(i in keep for i in p.vertices)]
order = sorted(keep)
remap = {old: new for new, old in enumerate(order)}
coords, weights = [], []
for i in order:
    p_arm, ws = vw[i]
    tot = sum(w for n, w in ws.items() if n in MAP) or 1.0
    q = Vector()
    for n, w in ws.items():
        if n in MAP:
            q += (MAP[n] @ p_arm) * (w / tot)
    coords.append(q)
    weights.append({n: w / tot for n, w in ws.items() if n in MAP})
uv_src = me.uv_layers.active.data if me.uv_layers else None
gm = D.meshes.new("Hero_Gloves")
gm.from_pydata(coords, [], [[remap[i] for i in f] for f in faces])
if uv_src:
    uvl = gm.uv_layers.new(name="UVMap")
    li = 0
    for p in me.polygons:
        if all(i in keep for i in p.vertices):
            for k in range(p.loop_total):
                uvl.data[li].uv = uv_src[p.loop_start + k].uv
                li += 1
for p in gm.polygons:
    p.use_smooth = True
gloves = D.objects.new("Hero_Gloves", gm)
hero_coll.objects.link(gloves)
gloves.parent = rig
gloves.matrix_parent_inverse = Matrix.Identity(4)
gloves.matrix_world = rig.matrix_world
for i, ws in enumerate(weights):
    for n, w in ws.items():
        vg = gloves.vertex_groups.get(n) or gloves.vertex_groups.new(name=n)
        vg.add([i], w, "REPLACE")
mod = gloves.modifiers.new("Armature", "ARMATURE")
mod.object = rig
sub = gloves.modifiers.new("Subsurf", "SUBSURF")
sub.levels = sub.render_levels = 1

# black leather, with Remy's skin normal map for knuckles and creases
glove_mat = D.materials.new("Glove_Leather")
nt_g = glove_mat.node_tree
pb_g = next(n for n in nt_g.nodes if n.type == "BSDF_PRINCIPLED")
pb_g.inputs["Base Color"].default_value = (0.012, 0.012, 0.013, 1)
pb_g.inputs["Roughness"].default_value = 0.36
pb_g.inputs["Coat Weight"].default_value = 0.15
pb_g.inputs["Coat Roughness"].default_value = 0.25
nimg = D.images.get("Remy_Body_Normal")
if nimg:
    nimg.colorspace_settings.name = "Non-Color"
    if not nimg.packed_file:
        nimg.pack()
    tx = nt_g.nodes.new("ShaderNodeTexImage")
    tx.image = nimg
    nm = nt_g.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.8
    nt_g.links.new(tx.outputs["Color"], nm.inputs["Color"])
    nt_g.links.new(nm.outputs["Normal"], pb_g.inputs["Normal"])
gm.materials.append(glove_mat)

# hide the mannequin hands (and their joint balls) under a mask
for name in ("Hero_Hands_Head", "Hero_Joints"):
    ob = D.objects[name]
    for m in [m for m in ob.modifiers if m.name.startswith("Glove_")]:
        ob.modifiers.remove(m)
    hg = {g.index: g.name for g in ob.vertex_groups}
    mask_vg = ob.vertex_groups.new(name="Mannequin_Hands")
    for v in ob.data.vertices:
        hw = sum(g.weight for g in v.groups if is_hand(hg.get(g.group, "")))
        if hw > 0.2:
            mask_vg.add([v.index], 1.0, "REPLACE")
    mk = ob.modifiers.new("Hide_Mannequin_Hands", "MASK")
    mk.vertex_group = mask_vg.name
    mk.invert_vertex_group = True

for o in remy_objs:
    D.objects.remove(o)
print("remy hands:", len(coords), "verts,", len(faces), "faces, scale", {k: round(v, 3) for k, v in scale.items()})
