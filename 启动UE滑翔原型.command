#!/bin/zsh
set -e
ROOT="${0:A:h}"
UE_EDITOR="${UE_EDITOR:-}"
if [[ -z "$UE_EDITOR" ]]; then
  for CANDIDATE in "$HOME/Unreal/UE_5.8/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor" "/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"; do
    if [[ -x "$CANDIDATE" ]]; then UE_EDITOR="$CANDIDATE"; break; fi
  done
fi
if [[ ! -x "$UE_EDITOR" ]]; then echo '未找到 UE 5.8 编辑器。请设置 UE_EDITOR 为 UnrealEditor 可执行文件路径。'; exit 1; fi
"${UE_EDITOR%/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor}/Build/BatchFiles/Mac/Build.sh" WindRouteEditor Mac Development "$ROOT/WindRoute.uproject" -WaitMutex
SERVICE_PID=''
if [[ -x "$ROOT/.venv/bin/python" ]] && ! lsof -nP -iTCP:8896 -sTCP:LISTEN >/dev/null 2>&1; then
  "$ROOT/启动肌电服务.command" &
  SERVICE_PID=$!
fi
cleanup() { if [[ -n "$SERVICE_PID" ]]; then kill "$SERVICE_PID" 2>/dev/null || true; fi; }
trap cleanup EXIT
"$UE_EDITOR" "$ROOT/WindRoute.uproject" -game -windowed -ResX=1280 -ResY=720 -nosplash
