import unreal
base='/Game/Jayant_Chakradhari_Assets/Free_Grass'
for n in ('12','20','23'):
 m=unreal.load_asset(base+'/Textured_Meshes/Grass_Meshes/SM_Grass_'+n)
 unreal.log('FAB_GRASS_MESH '+n+' '+str(m.get_bounds())+' material='+str(m.get_material(0).get_path_name() if m.get_material(0) else 'None'))
 mat=unreal.load_asset(base+'/Materials/Grass/MI_Grass_'+n)
 unreal.log('FAB_GRASS_MAT '+n+' scalars='+str(unreal.MaterialEditingLibrary.get_scalar_parameter_names(mat))+' vectors='+str(unreal.MaterialEditingLibrary.get_vector_parameter_names(mat)))
unreal.log('FAB_GRASS_INSPECT_DONE')
