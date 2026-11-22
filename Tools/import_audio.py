import unreal
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
for name in ('wind_loop','ring_chime'):
    destination='/Game/WindRoute/Audio'
    task=unreal.AssetImportTask()
    task.set_editor_property('filename',str(root/'Assets'/'Audio'/(name+'.wav')))
    task.set_editor_property('destination_path',destination)
    task.set_editor_property('destination_name',name)
    task.set_editor_property('automated',True)
    task.set_editor_property('replace_existing',True)
    task.set_editor_property('save',True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths=task.get_editor_property('imported_object_paths')
    if not paths: raise RuntimeError('Audio import failed: '+name)
    sound=unreal.EditorAssetLibrary.load_asset(paths[0])
    if name=='wind_loop':
        sound.set_editor_property('looping',True)
        if not unreal.EditorAssetLibrary.save_loaded_asset(sound,only_if_is_dirty=False): raise RuntimeError('Wind save failed')
    unreal.log('WINDROUTE_AUDIO_READY: '+paths[0])
