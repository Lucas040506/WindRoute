import unreal
from pathlib import Path
root=Path(unreal.Paths.project_dir()).resolve()
for name in ('canyon_music','ring_approach','ring_pass','ring_missed','power_restored'):
    task=unreal.AssetImportTask()
    task.filename=str(root/'Assets'/'Audio'/'Integrated'/(name+'.wav'))
    task.destination_path='/Game/WindRoute/Audio'
    task.destination_name=name
    task.automated=True
    task.replace_existing=True
    task.save=True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths=task.imported_object_paths
    if not paths: raise RuntimeError('Audio import failed: '+name)
    sound=unreal.EditorAssetLibrary.load_asset(paths[0])
    if name=='canyon_music': sound.set_editor_property('looping',True)
    if not unreal.EditorAssetLibrary.save_loaded_asset(sound,only_if_is_dirty=False): raise RuntimeError('Audio save failed: '+name)
    unreal.log('AUDIO_READY: '+paths[0])
