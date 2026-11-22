import unreal
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
for name in ('glide_wind','wind_sweep'):
 t=unreal.AssetImportTask();t.filename=str(root/'Assets'/'Audio'/'Integrated'/(name+'.wav'));t.destination_path='/Game/WindRoute/Audio';t.destination_name=name;t.automated=True;t.replace_existing=True;t.save=True
 unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t]);paths=t.imported_object_paths
 if not paths:raise RuntimeError('Import failed '+name)
 asset=unreal.EditorAssetLibrary.load_asset(paths[0]);
 if name=='glide_wind':asset.set_editor_property('looping',True)
 if not unreal.EditorAssetLibrary.save_loaded_asset(asset,only_if_is_dirty=False):raise RuntimeError('Save failed '+name)
 unreal.log('WIND_AUDIO_READY '+paths[0])
