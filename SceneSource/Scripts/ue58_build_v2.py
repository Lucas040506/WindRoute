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
    ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
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
    sd.auto_generate_collision = name.startswith("SM_Terrain") or name.startswith("SM_StartPad")
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

# ring material: palette colour + emissive, dithered fade when the camera is closer than ~4 m
mel = unreal.MaterialEditingLibrary
ring_mat = eal.load_asset(MESH + "/M_Ring_Fade") if eal.does_asset_exist(MESH + "/M_Ring_Fade") else \
    tools.create_asset("M_Ring_Fade", MESH, unreal.Material, unreal.MaterialFactoryNew())
ring_mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
ts = mel.create_material_expression(ring_mat, unreal.MaterialExpressionTextureSample, -600, 0)
ts.set_editor_property("texture", palette_tex)
ts.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_COLOR)
mel.connect_material_property(ts, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
em = mel.create_material_expression(ring_mat, unreal.MaterialExpressionMultiply, -300, 150)
em.set_editor_property("const_b", 2.0)
mel.connect_material_expressions(ts, "RGB", em, "A"); mel.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
pd = mel.create_material_expression(ring_mat, unreal.MaterialExpressionPixelDepth, -900, 300)
sub = mel.create_material_expression(ring_mat, unreal.MaterialExpressionSubtract, -700, 300); sub.set_editor_property("const_b", 250.0)
div = mel.create_material_expression(ring_mat, unreal.MaterialExpressionDivide, -550, 300); div.set_editor_property("const_b", 300.0)
sat = mel.create_material_expression(ring_mat, unreal.MaterialExpressionSaturate, -400, 300)
dit = mel.create_material_expression(ring_mat, unreal.MaterialExpressionDitherTemporalAA, -250, 300)
mel.connect_material_expressions(pd, "", sub, "A"); mel.connect_material_expressions(sub, "", div, "A")
mel.connect_material_expressions(div, "", sat, ""); mel.connect_material_expressions(sat, "", dit, "Alpha")
mel.connect_material_property(dit, "", unreal.MaterialProperty.MP_OPACITY_MASK)
mel.recompile_material(ring_mat); eal.save_loaded_asset(ring_mat)
mesh["SM_Ring"].set_material(0, ring_mat); eal.save_loaded_asset(mesh["SM_Ring"])

# ---------------------------------------------------------------- 2) level
les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
les.new_level(MAP)
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
            smc.set_collision_profile_name("OverlapAllDynamic"); smc.set_generate_overlap_events(True)
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

# spline (every 10 m)
smp = list(csv.DictReader(open(os.path.join(DATA, "FlightSpline_v2_samples_1m.csv"))))
spline_actor = eas.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0)); spline_actor.set_actor_label("FlightSpline_v2")
spl = add_component(spline_actor, unreal.SplineComponent)
spl.set_spline_points([unreal.Vector(float(r["UE_X_cm"]), float(r["UE_Y_cm"]), float(r["UE_Z_cm"])) for r in smp[::10]],
                      unreal.SplineCoordinateSpace.WORLD, True)
log(f"spline length {spl.get_spline_length() / 100:.0f} m")

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

# ---------------------------------------------------------------- 3) glider + camera sequence (auto-play, used by perf test)
glider = eas.spawn_actor_from_object(mesh["SM_Glider_Placeholder"], unreal.Vector(0, 0, 0)); glider.set_actor_label("Glider")
glider.get_component_by_class(unreal.StaticMeshComponent).set_mobility(unreal.ComponentMobility.MOVABLE)
cam = eas.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(0, 0, 0)); cam.set_actor_label("ChaseCam")
cc = cam.get_cine_camera_component()
cc.set_editor_property("current_focal_length", 18.3)   # 66 deg horizontal on the default 23.76 mm filmback
cc.focus_settings.focus_method = unreal.CameraFocusMethod.DISABLE

rows = list(csv.DictReader(open(os.path.join(DATA, "Flythrough_Track_UE.csv"))))
seq = eal.load_asset(SEQ) if eal.does_asset_exist(SEQ) else tools.create_asset("LS_Flythrough", DEST + "/Cinematics", unreal.LevelSequence, unreal.LevelSequenceFactoryNew())
seq.set_display_rate(unreal.FrameRate(30, 1)); seq.set_tick_resolution(unreal.FrameRate(30, 1))
seq.set_playback_start(0); seq.set_playback_end(len(rows))


def key_transform(binding, cols):
    tr = binding.add_track(unreal.MovieScene3DTransformTrack)
    sec = tr.add_section(); sec.set_range(0, len(rows))
    ch = sec.get_all_channels()   # loc x,y,z, rot x(roll),y(pitch),z(yaw), scale x,y,z
    for i, r in enumerate(rows):
        if i % 2:
            continue
        p = [float(r[cols + k]) for k in ("_X_cm", "_Y_cm", "_Z_cm")]
        fwd = unreal.Vector(*[float(r[cols + k]) for k in ("_FwdX", "_FwdY", "_FwdZ")])
        up = unreal.Vector(*[float(r[cols + k]) for k in ("_UpX", "_UpY", "_UpZ")])
        rot = unreal.MathLibrary.make_rot_from_xz(fwd, up)
        fn = unreal.FrameNumber(i)
        for c, v in zip(ch[:6], (p[0], p[1], p[2], rot.roll, rot.pitch, rot.yaw)):
            c.add_key(fn, v)


gb = seq.add_possessable(glider); key_transform(gb, "G")
cb = seq.add_possessable(cam); key_transform(cb, "C")
cut = seq.add_track(unreal.MovieSceneCameraCutTrack); cs_ = cut.add_section(); cs_.set_range(0, len(rows))
try:
    cs_.set_camera_binding_id(seq.make_binding_id(cb, unreal.MovieSceneObjectBindingSpace.LOCAL))
except Exception:
    cs_.set_camera_binding_id(cb.get_binding_id())
eal.save_loaded_asset(seq)
lsa = eas.spawn_actor_from_class(unreal.LevelSequenceActor, unreal.Vector(0, 0, 0)); lsa.set_actor_label("LS_Flythrough_AutoPlay")
lsa.set_sequence(seq)
ps = lsa.get_editor_property("playback_settings"); ps.set_editor_property("auto_play", True)
lp = unreal.MovieSceneSequenceLoopCount(); lp.set_editor_property("value", 0); ps.set_editor_property("loop_count", lp)
lsa.set_editor_property("playback_settings", ps)
les.save_current_level(); unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
log("level saved: " + MAP)
