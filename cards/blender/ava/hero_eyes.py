"""Hero face rework: glowing emerald eyes, skin in the eye slit goes to shadow, black knitted balaclava.

Run inside a scene that has the hero (Hero_Eye_L/R, Hero_Face, Hero_Balaclava, Hero_Hands_Head).
"""
import bpy

D = bpy.data


def principled(m):
    return next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


# eyes: dark glass ball, emerald iris glow brightest in the middle (facing the viewer)
eyes = D.materials.new("Hero_Eyes_Glow")
nt = eyes.node_tree
b = principled(eyes)
b.inputs["Base Color"].default_value = (0.0, 0.02, 0.01, 1)
b.inputs["Roughness"].default_value = 0.05
b.inputs["Emission Color"].default_value = (0.05, 1.0, 0.3, 1)
lw = nt.nodes.new("ShaderNodeLayerWeight")
lw.inputs["Blend"].default_value = 0.35
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.0, (5, 5, 5, 1)
ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.75, (2.5, 2.5, 2.5, 1)
nt.links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], b.inputs["Emission Strength"])
for n in ("Hero_Eye_L", "Hero_Eye_R"):
    me = D.objects[n].data
    me.materials.clear()
    me.materials.append(eyes)

# skin around the eyes: almost black, so the slit reads as shadow with two lights in it
for m in D.materials:
    if m.name.startswith("Skin"):
        sk = principled(m)
        sk.inputs["Base Color"].default_value = (0.012, 0.010, 0.010, 1)
        sk.inputs["Roughness"].default_value = 0.6

# balaclava: black rib knit (wave bump) with a little fuzz sheen
for m in D.materials:
    if m.name.startswith("Balaclava"):
        nt = m.node_tree
        p = principled(m)
        for l in list(p.inputs["Base Color"].links):
            nt.links.remove(l)
        p.inputs["Base Color"].default_value = (0.018, 0.018, 0.02, 1)
        p.inputs["Roughness"].default_value = 0.85
        p.inputs["Sheen Weight"].default_value = 0.6
        p.inputs["Sheen Roughness"].default_value = 0.4
        p.inputs["Sheen Tint"].default_value = (0.6, 0.7, 0.65, 1)
        tc = nt.nodes.new("ShaderNodeTexCoord")
        wave = nt.nodes.new("ShaderNodeTexWave")
        wave.wave_type, wave.bands_direction = "BANDS", "X"
        wave.inputs["Scale"].default_value = 260
        wave.inputs["Distortion"].default_value = 2.0
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 900
        mix = nt.nodes.new("ShaderNodeMath")
        mix.operation = "MULTIPLY_ADD"
        mix.inputs[1].default_value = 0.8
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.35
        bump.inputs["Distance"].default_value = 0.002
        nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
        nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
        nt.links.new(wave.outputs["Fac"], mix.inputs[0])
        nt.links.new(noise.outputs["Fac"], mix.inputs[2])
        nt.links.new(mix.outputs[0], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], p.inputs["Normal"])
print("hero eyes done")
