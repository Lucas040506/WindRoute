"""GliderCanyon v2 -> UE 5.8 level (run inside the editor of UE/GliderCanyonV2/GliderCanyonV2.uproject).

  "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor" \
      UE/GliderCanyonV2/GliderCanyonV2.uproject -ExecutePythonScript="$PWD/Scripts/ue58_build_v2.py"

Creates only /Game/GliderCanyon_v2/... :
  Meshes/*      static meshes from FBX/ (trees get auto LODs), T_LowPolyPalette_v2, M_Ring_Fade
  Maps/L_GliderCanyon_v2   terrain (play/near/far), HISM foliage per prototype with cull distances,
                           rocks/outcrops HISM, 9 optional rings (overlap only), FlightSpline, warm sun,
                           SkyAtmosphere, SkyLight, height fog, glider + CineCamera driven by LS_Flythrough (auto play)
"""
import unreal, os, csv, math

try:
    ROOT = '/Users/lucas/HKUST_TLE/ISDN5230/canyon_delivery/GliderCanyon_v2'
except NameError:
    ROOT = os.path.expanduser("~/Documents/GliderCanyon_UE58/GliderCanyon_v2")
FBX = os.path.join(ROOT, "FBX"); DATA = os.path.join(ROOT, "Data")
DEST = "/Game/GliderCanyon_v2"; MESH = DEST + "/Meshes"; MAP = DEST + "/Maps/L_GliderCanyon_v2"; SEQ = DEST + "/Cinematics/LS_Flythrough"
assert os.path.isdir(FBX), "Run Scripts/blender_build_v2.py first"
tools = unreal.AssetToolsHelpers.get_asset_tools()
eal = unreal.EditorAssetLibrary
log = lambda m: unreal.log("GliderCanyon v2: " + m)

# ---------------------------------------------------------------- 1) import
def import_fbx(name):
    ui = unreal.FbxImportUI()
    ui.import_mesh = True; ui.import_as_skeletal = False; ui.import_animations = False
    ui.import_materials = True; ui.import_textures = True
    sd = ui.static_mesh_import_data
    sd.combine_meshes = True; sd.generate_lightmap_u_vs = False
    sd.auto_generate_collision = False
    sd.normal_import_method = unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    t = unreal.AssetImportTask(); t.filename = os.path.join(FBX, name + ".fbx")
    t.destination_path = MESH; t.destination_name = name; t.automated = True; t.replace_existing = True; t.save = True; t.options = ui
    tools.import_asset_tasks([t])
    return unreal.load_asset(f"{MESH}/{name}")


names = sorted(f[:-4] for f in os.listdir(FBX) if f.endswith(".fbx"))
mesh = {n: import_fbx(n) for n in names}
log(f"imported {len(mesh)} meshes")

for a in eal.list_assets(MESH, recursive=True):
    o = unreal.load_asset(a)
    if isinstance(o, unreal.Texture2D):
        o.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
        o.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        eal.save_loaded_asset(o); palette_tex = o

# auto LODs for pines (LOD1 50 %, LOD2 25 %) - reduces cost of the 2.4k near-field trees
sms = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
opts = unreal.StaticMeshReductionOptions()
opts.auto_compute_lod_screen_size = False
opts.reduction_settings = [unreal.StaticMeshReductionSettings(1.0, 1.0), unreal.StaticMeshReductionSettings(0.5, 0.25),
                           unreal.StaticMeshReductionSettings(0.25, 0.08)]
for n, m in mesh.items():
    if n.startswith("SM_Pine") and not n.startswith("SM_PineFar"):
        try:
            sms.set_lods(m, opts); eal.save_loaded_asset(m)
        except Exception as e:
            unreal.log_warning(f"LOD generation failed for {n}: {e}")

# Import shared palette explicitly; exported FBX meshes carry UV coordinates.
t = unreal.AssetImportTask(); t.filename = os.path.join(ROOT, "Textures", "T_LowPolyPalette_v2.png"); t.destination_path = MESH; t.destination_name = "T_CanyonPalette"; t.automated = True; t.replace_existing = True; t.save = True
tools.import_asset_tasks([t])
palette_tex = unreal.load_asset(MESH + "/T_CanyonPalette")
mel = unreal.MaterialEditingLibrary
mat = eal.load_asset(MESH + "/M_CanyonPalette") if eal.does_asset_exist(MESH + "/M_CanyonPalette") else tools.create_asset("M_CanyonPalette", MESH, unreal.Material, unreal.MaterialFactoryNew())
ts = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -400, 0); ts.set_editor_property("texture", palette_tex)
mel.connect_material_property(ts, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
mel.recompile_material(mat); eal.save_loaded_asset(mat)
for n,m in mesh.items():
    if m:
        m.set_material(0,mat)
        eal.save_loaded_asset(m)

# ---------------------------------------------------------------- 2) level
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assert les.load_level(MAP), "Cannot load target level"
sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
BFL = unreal.SubobjectDataBlueprintFunctionLibrary


def add_component(actor, cls):
    root = sds.k2_gather_subobject_data_for_instance(actor)[0]
    h, _ = sds.add_new_subobject(unreal.AddNewSubobjectParams(parent_handle=root, new_class=cls, blueprint_context=None))
    return BFL.get_object(BFL.get_data(h))


for n in ("SM_Terrain_Play", "SM_Terrain_Near", "SM_Terrain_Far", "SM_StartPad"):
    a = eas.spawn_actor_from_object(mesh[n], unreal.Vector(0, 0, 0)); a.set_actor_label(n)
g = eas.spawn_actor_from_object(mesh["SM_FlightPath_Guide"], unreal.Vector(0, 0, 0))
g.set_actor_label("FlightPath_Guide (editor only)"); g.set_actor_hidden_in_game(True)

# instances -> one HISM per prototype/layer
groups = {}
for r in csv.DictReader(open(os.path.join(DATA, "Instances_UE.csv"))):
    groups.setdefault((r["Proto"], r["Layer"]), []).append(r)
for (proto, layer), rows in groups.items():
    if layer == "ring":
        for r in rows:
            a = eas.spawn_actor_from_object(mesh[proto], unreal.Vector(float(r["X_cm"]), float(r["Y_cm"]), float(r["Z_cm"])),
                                            unreal.Rotator(roll=0.0, pitch=float(r["Pitch"]), yaw=float(r["Yaw"])))
            a.set_actor_label(r["Name"]); a.tags = ["OptionalRing"]
            smc = a.get_component_by_class(unreal.StaticMeshComponent)
            smc.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        continue
    holder = eas.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0)); holder.set_actor_label(f"HISM_{proto}_{layer}")
    h = add_component(holder, unreal.HierarchicalInstancedStaticMeshComponent)
    h.set_static_mesh(mesh[proto])
    cs, ce = int(rows[0]["CullStart_cm"]), int(rows[0]["CullEnd_cm"])
    h.set_cull_distances(cs, ce)
    h.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION if proto.startswith("SM_Pine") else unreal.CollisionEnabled.QUERY_ONLY)
    h.set_editor_property("cast_dynamic_shadow", layer != "near")
    xf = [unreal.Transform(unreal.Vector(float(r["X_cm"]), float(r["Y_cm"]), float(r["Z_cm"])),
                           unreal.Rotator(roll=0.0, pitch=float(r["Pitch"]), yaw=float(r["Yaw"])),
                           unreal.Vector(float(r["SX"]), float(r["SY"]), float(r["SZ"]))) for r in rows]
    h.add_instances(xf, False, True)
    log(f"{proto}/{layer}: {len(xf)} instances, cull {cs/100:.0f}-{ce/100:.0f} m")

# light / sky / fog: warm low sun, soft sky, distance fog that starts beyond ~450 m
sx, sy, sz = 0.52, -0.55, -0.66   # light travel direction in UE frame (Y mirrored)
sun = eas.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 60000),
                                 unreal.Rotator(roll=0, pitch=math.degrees(math.asin(sz / math.sqrt(sx*sx+sy*sy+sz*sz))), yaw=math.degrees(math.atan2(sy, sx))))
sun.set_actor_label("Sun_Warm")
lc = sun.get_component_by_class(unreal.DirectionalLightComponent)
lc.set_editor_property("intensity", 8.0); lc.set_editor_property("light_color", unreal.Color(r=255, g=226, b=190, a=255))
lc.set_editor_property("atmosphere_sun_light", True); lc.set_editor_property("dynamic_shadow_distance_movable_light", 180000.0)
eas.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0)).set_actor_label("SkyAtmosphere")
sky = eas.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 40000)); sky.set_actor_label("SkyLight")
sky.get_component_by_class(unreal.SkyLightComponent).set_editor_property("real_time_capture", True)
fog = eas.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0)); fog.set_actor_label("DistanceFog")
fc = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
fc.set_editor_property("fog_density", 0.006); fc.set_editor_property("fog_height_falloff", 0.05)
fc.set_editor_property("start_distance", 45000.0)
fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(0.66, 0.70, 0.90, 1.0))

les.save_current_level(); unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
log("level saved")
