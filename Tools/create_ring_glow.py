import unreal
path='/Game/WindRoute/Materials/M_RingGlow'
lib=unreal.EditorAssetLibrary;tools=unreal.AssetToolsHelpers.get_asset_tools()
mat=lib.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset('M_RingGlow','/Game/WindRoute/Materials',unreal.Material,unreal.MaterialFactoryNew())
mel=unreal.MaterialEditingLibrary
expr=mel.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-300,0)
expr.set_editor_property('constant',unreal.LinearColor(5.0,4.5,2.9,1.0))
mel.connect_material_property(expr,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mat.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
mat.set_editor_property('used_with_instanced_static_meshes',True)
mel.recompile_material(mat)
if not lib.save_loaded_asset(mat,only_if_is_dirty=False):raise RuntimeError('ring material save failed')
unreal.log('RING_GLOW_READY')
