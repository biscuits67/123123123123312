"""Hologram above the shop sill (Blade-Runner style), replacing the rates board.

    blender -b IN.blend -P holo_build.py -- OUT.blend [REVEAL]

Projector puck on the sill with a mint light cone in the haze; extruded hologram text with a
see-through emission shader: scanlines that crawl upwards, flicker, a bright build-up edge.
REVEAL (0..1) sets a static reveal height for concept stills."""
import math
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
OUT = args[0]
REVEAL = float(args[1]) if len(args) > 1 else 1.0
D, scn = bpy.data, bpy.context.scene
SILL = Vector((-52.05, -73.45, 1.375))
MINT = (0.08, 1.0, 0.5, 1)

D.objects["rates_board"].hide_render = True
D.objects["rates_board"].hide_viewport = True

# ---------------------------------------------------------------- projector puck + light cone
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.32, depth=0.06, location=SILL + Vector((0, 0, 0.03)))
puck = bpy.context.object
puck.name = "Holo_Projector"
pm = D.materials.new("Holo_Projector")
b = pm.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.02, 0.025, 0.025, 1)
b.inputs["Metallic"].default_value, b.inputs["Roughness"].default_value = 0.9, 0.25
puck.data.materials.append(pm)
bpy.ops.mesh.primitive_torus_add(major_radius=0.25, minor_radius=0.012, location=SILL + Vector((0, 0, 0.062)))
ring = bpy.context.object
ring.name = "Holo_Projector_Ring"
rm = D.materials.new("Holo_Ring")
rb = rm.node_tree.nodes["Principled BSDF"]
rb.inputs["Emission Color"].default_value = MINT
rb.inputs["Emission Strength"].default_value = 25
ring.data.materials.append(rm)
cone = D.objects.new("Holo_Beam", D.lights.new("Holo_Beam", "SPOT"))
cone.data.energy, cone.data.color = 450, MINT[:3]
cone.data.spot_size, cone.data.spot_blend, cone.data.shadow_soft_size = math.radians(48), 0.35, 0.2
cone.location = SILL + Vector((0, 0, 0.07))
cone.rotation_euler = Vector((0, 0, 1)).to_track_quat("-Z", "Y").to_euler()
cone.visible_camera = False
scn.collection.objects.link(cone)

# visible beam: an open cone of faint light rising from the puck (fades towards the top)
bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=0.24, radius2=1.9, depth=2.2, end_fill_type="NOTHING",
                                location=SILL + Vector((0, 0, 0.06 + 1.1)))
beam = bpy.context.object
beam.name = "Holo_Beam_Volume"
bm = D.materials.new("Holo_Beam")
nt = bm.node_tree
nt.nodes.remove(nt.nodes["Principled BSDF"])
tc = nt.nodes.new("ShaderNodeTexCoord")
sz = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(tc.outputs["Generated"], sz.inputs["Vector"])
fade = nt.nodes.new("ShaderNodeMapRange")
fade.inputs["To Min"].default_value, fade.inputs["To Max"].default_value = 0.22, 0.0
nt.links.new(sz.outputs["Z"], fade.inputs["Value"])
lw = nt.nodes.new("ShaderNodeLayerWeight")
lw.inputs["Blend"].default_value = 0.35
soft = nt.nodes.new("ShaderNodeMath"); soft.operation = "MULTIPLY"
nt.links.new(fade.outputs["Result"], soft.inputs[0]); nt.links.new(lw.outputs["Facing"], soft.inputs[1])
inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
nt.links.new(lw.outputs["Facing"], inv.inputs[1])
soft2 = nt.nodes.new("ShaderNodeMath"); soft2.operation = "MULTIPLY"
nt.links.new(fade.outputs["Result"], soft2.inputs[0]); nt.links.new(inv.outputs[0], soft2.inputs[1])
em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = MINT; em.inputs["Strength"].default_value = 1.2
tr = nt.nodes.new("ShaderNodeBsdfTransparent")
mx = nt.nodes.new("ShaderNodeMixShader")
nt.links.new(soft2.outputs[0], mx.inputs["Fac"]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
beam.data.materials.append(bm)
beam.visible_shadow = False

# ---------------------------------------------------------------- hologram material
def holo_material():
    m = D.materials.new("Hologram")
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    N.remove(N["Principled BSDF"])
    out = N["Material Output"]
    coord = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ")
    L.new(coord.outputs["Object"], sep.inputs["Vector"])
    # scanlines crawling up: fract((z + t) * density)
    t = N.new("ShaderNodeValue")
    t.name = "time"
    drv = t.outputs[0].driver_add("default_value").driver
    drv.expression = "frame/250*1.5"
    add = N.new("ShaderNodeMath"); add.operation = "ADD"
    L.new(sep.outputs["Y"], add.inputs[0]); L.new(t.outputs[0], add.inputs[1])
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 90
    L.new(add.outputs[0], mul.inputs[0])
    sin = N.new("ShaderNodeMath"); sin.operation = "SINE"
    L.new(mul.outputs[0], sin.inputs[0])
    lines = N.new("ShaderNodeMapRange")
    lines.inputs["From Min"].default_value, lines.inputs["From Max"].default_value = -1, 1
    lines.inputs["To Min"].default_value, lines.inputs["To Max"].default_value = 0.35, 1.0
    L.new(sin.outputs[0], lines.inputs["Value"])
    # reveal from the bottom (object Z normalised to 0..1 by the text height)
    rev = N.new("ShaderNodeValue"); rev.name = "reveal"; rev.outputs[0].default_value = REVEAL
    zn = N.new("ShaderNodeMapRange"); zn.name = "zspan"
    L.new(sep.outputs["Y"], zn.inputs["Value"])
    cmp = N.new("ShaderNodeMath"); cmp.operation = "LESS_THAN"
    L.new(zn.outputs["Result"], cmp.inputs[0]); L.new(rev.outputs[0], cmp.inputs[1])
    edge = N.new("ShaderNodeMath"); edge.operation = "COMPARE"; edge.inputs[2].default_value = 0.03
    L.new(zn.outputs["Result"], edge.inputs[0]); L.new(rev.outputs[0], edge.inputs[1])
    vis = N.new("ShaderNodeMath"); vis.operation = "MULTIPLY"
    L.new(lines.outputs["Result"], vis.inputs[0]); L.new(cmp.outputs[0], vis.inputs[1])
    vis2 = N.new("ShaderNodeMath"); vis2.operation = "ADD"; vis2.use_clamp = True
    L.new(vis.outputs[0], vis2.inputs[0]); L.new(edge.outputs[0], vis2.inputs[1])
    em = N.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = MINT
    strength = N.new("ShaderNodeMath"); strength.operation = "MULTIPLY"; strength.inputs[1].default_value = 2.2
    L.new(vis2.outputs[0], strength.inputs[0]); L.new(strength.outputs[0], em.inputs["Strength"])
    tr = N.new("ShaderNodeBsdfTransparent")
    mix = N.new("ShaderNodeMixShader")
    alpha = N.new("ShaderNodeMath"); alpha.operation = "MULTIPLY"; alpha.inputs[1].default_value = 0.85
    L.new(vis2.outputs[0], alpha.inputs[0])
    L.new(alpha.outputs[0], mix.inputs["Fac"]); L.new(tr.outputs[0], mix.inputs[1]); L.new(em.outputs[0], mix.inputs[2])
    L.new(mix.outputs[0], out.inputs["Surface"])
    return m


def holo_text(body, size, z, extrude, mat, name):
    cu = D.curves.new(name, "FONT")
    cu.body = body
    cu.font = D.fonts.load("/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf", check_existing=True)
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.size, cu.extrude = size, extrude
    ob = D.objects.new(name, cu)
    scn.collection.objects.link(ob)
    ob.location = Vector((SILL.x, SILL.y, z))
    ob.rotation_euler = (math.radians(90), 0, math.radians(-90))   # face the street like the EMERALD sign
    ob.data.materials.append(mat)
    return ob


mat = holo_material()
big = holo_text("75%", 1.55, 2.62, 0.06, mat, "Holo_Value")
sub = holo_text("ЛУЧШИЙ ПРОЦЕНТ", 0.3, 1.82, 0.02, mat, "Holo_Label")
# reveal span in the text's local Y (up on the sign) (text centred on its origin): bottom -> top of both lines
zn = mat.node_tree.nodes["zspan"]
zn.inputs["From Min"].default_value, zn.inputs["From Max"].default_value = -0.6, 0.6
for ob in (big, sub):
    ob.data.font.pack() if ob.data.font.filepath and not ob.data.font.packed_file else None
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=False)
print("saved", OUT)
