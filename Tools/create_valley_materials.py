"""Create the original placeholder palette as editable Unreal materials."""
import unreal

ROOT = '/Game/WindRoute/Materials'
COLORS = {
    'M_Water': (0.035, 0.22, 0.26),
    'M_Grass': (0.24, 0.36, 0.22),
    'M_Cliff': (0.32, 0.39, 0.34),
    'M_Canyon': (0.52, 0.19, 0.065),
    'M_Tree': (0.12, 0.26, 0.20),
    'M_Trunk': (0.25, 0.19, 0.14),
    'M_Guide': (1.0, 0.62, 0.18),
    'M_Glider': (0.84, 0.80, 0.64),
    'M_Accent': (0.62, 0.17, 0.12),
}
tools = unreal.AssetToolsHelpers.get_asset_tools()
for name, color in COLORS.items():
    path = ROOT + '/' + name
    mat = unreal.EditorAssetLibrary.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if not mat:
        mat = tools.create_asset(name, ROOT, unreal.Material, unreal.MaterialFactoryNew())
        if not mat:
            raise RuntimeError('Could not create ' + path)
        expression = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
        expression.set_editor_property('constant', unreal.LinearColor(*color, 1.0))
        unreal.MaterialEditingLibrary.connect_material_property(expression, '', unreal.MaterialProperty.MP_BASE_COLOR)
        rough = unreal.MaterialEditingLibrary.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 140)
        rough.set_editor_property('r', 0.3 if name == 'M_Water' else 0.85)
        unreal.MaterialEditingLibrary.connect_material_property(rough, '', unreal.MaterialProperty.MP_ROUGHNESS)
        if name == 'M_Guide':
            unreal.MaterialEditingLibrary.connect_material_property(expression, '', unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        unreal.MaterialEditingLibrary.recompile_material(mat)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    unreal.MaterialEditingLibrary.recompile_material(mat)
    if not unreal.EditorAssetLibrary.save_loaded_asset(mat, only_if_is_dirty=False):
        raise RuntimeError('Could not save ' + path)
    unreal.log('WINDROUTE_MATERIAL_READY: ' + path)
