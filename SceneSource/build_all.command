#!/bin/bash
# One-click build on macOS: Blender source + FBX, then the UE 5.8 level. Writes only inside this folder.
set -e
cd "$(dirname "$0")"
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
UE="/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
echo "== Blender ($("$BLENDER" --version | head -1))"
"$BLENDER" -b -P Scripts/blender_build_v2.py
echo "== UE 5.8: build level (editor opens, runs the script, then you can close it)"
"$UE" "$PWD/UE/GliderCanyonV2/GliderCanyonV2.uproject" -ExecutePythonScript="$PWD/Scripts/ue58_build_v2.py" -log
