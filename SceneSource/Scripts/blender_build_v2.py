"""GliderCanyon v2: build the Blender source file and UE-ready FBX files.

  /Applications/Blender.app/Contents/MacOS/Blender -b -P Scripts/blender_build_v2.py

Outputs (inside this GliderCanyon_v2 folder only):
  Blender/GliderCanyon_v2.blend   collections Terrain / Trees_Play / Trees_Far / Rocks / Outcrops / Rings / Route,
                                   instances are linked duplicates (shared mesh data), glider follows the route with
                                   the v2 time table, chase camera, sun + sky
  FBX/<asset>.fbx                 one FBX per terrain layer and per prototype (pivot at origin)
"""
import bpy, os, csv, math
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT_BLEND = os.path.join(ROOT, "Blender", "GliderCanyon_v2.blend")
OUT_FBX = os.path.join(ROOT, "FBX")
os.makedirs(os.path.dirname(OUT_BLEND), exist_ok=True); os.makedirs(OUT_FBX, exist_ok=True)
FPS = 30
samples = list(csv.DictReader(open(os.path.join(ROOT, "Data", "FlightSpline_v2_samples_1m.csv"))))
DUR = float(samples[-1]["Time_s"]); LEN = float(samples[-1]["S_m"])

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.render.fps = FPS; scn.frame_start = 1; scn.frame_end = int(round(DUR * FPS))


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


objs = import_glb(os.path.join(ROOT, "GliderCanyon_v2_Scene.glb"))
for mat in bpy.data.materials:
    if mat.use_nodes:
        for nd in mat.node_tree.nodes:
            if nd.type == "TEX_IMAGE":
                nd.interpolation = "Closest"

# collections -------------------------------------------------------------------------
def coll(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in scn.collection.children:
        scn.collection.children.link(c)
    return c


rules = [("SM_Terrain", "Terrain"), ("SM_PineFar", "Trees_Far"), ("SM_Pine", "Trees_Play"), ("Ring_", "Rings"),
         ("SM_Rock", "Rocks"), ("SM_StartPad", "Terrain"), ("SM_FlightPath_Guide", "Route"), ("SM_Glider", "Route")]
for o in objs:
    if o.type != "MESH":
        continue
    target = next((c for p, c in rules if o.name.startswith(p)), "Misc")
    if target == "Rocks" and max(o.scale) > 8:
        target = "Outcrops"
    for c in list(o.users_collection):
        c.objects.unlink(o)
    coll(target).objects.link(o)
bpy.data.collections["Route"].hide_render = False

# route curve + timed glider ---------------------------------------------------------------
cu = bpy.data.curves.new("FlightPath_v2", "CURVE"); cu.dimensions = "3D"
sp = cu.splines.new("POLY"); sp.points.add(len(samples) - 1)
for p, r in zip(sp.points, samples):
    p.co = (float(r["Blender_x_m"]), float(r["Blender_y_m"]), float(r["Blender_z_m"]), 1.0)
path = bpy.data.objects.new("FlightPath_v2", cu); coll("Route").objects.link(path)
glider = bpy.data.objects.get("SM_Glider_Placeholder")
if glider:
    glider.location = (0, 0, 0)
    c = glider.constraints.new("FOLLOW_PATH"); c.target = path; c.use_curve_follow = True; c.use_fixed_location = True
    c.forward_axis = "FORWARD_X"; c.up_axis = "UP_Z"
    k = 0
    for r in samples[::20]:                       # key every 20 m with the real (variable-speed) time
        c.offset_factor = float(r["S_m"]) / LEN
        c.keyframe_insert("offset_factor", frame=1 + float(r["Time_s"]) * FPS)
    for fc in glider.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    cam_data = bpy.data.cameras.new("ChaseCam"); cam_data.lens_unit = "FOV"; cam_data.angle = math.radians(66); cam_data.clip_end = 20000
    cam = bpy.data.objects.new("ChaseCam", cam_data); coll("Route").objects.link(cam)
    cam.parent = glider; cam.location = (-11, 0, 3); cam.rotation_euler = (math.radians(84), 0, math.radians(-90))
    scn.camera = cam

sun_dir = Vector((-0.52, -0.55, 0.66)).normalized()
ld = bpy.data.lights.new("Sun_Warm", "SUN"); ld.energy = 4.2; ld.color = (1.0, 0.88, 0.74); ld.angle = math.radians(2)
lo = bpy.data.objects.new("Sun_Warm", ld); scn.collection.objects.link(lo); lo.rotation_euler = sun_dir.to_track_quat("Z", "Y").to_euler()
w = bpy.data.worlds.new("SoftSky"); scn.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.66, 0.88, 1.0)
w.node_tree.nodes["Background"].inputs[1].default_value = 0.9
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
    try:
        scn.render.engine = eng; break
    except TypeError:
        pass
scn.render.resolution_x, scn.render.resolution_y = 1920, 1080
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

# FBX per asset (pivot at origin) -----------------------------------------------------------
KW = dict(use_selection=True, object_types={"MESH"}, apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
          axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE", add_leaf_bones=False, path_mode="COPY", bake_anim=False)
assets = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "Meshes_GLB")) if f.endswith(".glb"))
for name in assets:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ms = [o for o in import_glb(os.path.join(ROOT, "Meshes_GLB", name + ".glb")) if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in ms:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ms[0]
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT_FBX, name + ".fbx"), **KW)
print("GliderCanyon v2: wrote", OUT_BLEND, "and", len(assets), "FBX files")
