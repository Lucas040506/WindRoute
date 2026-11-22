#!/bin/bash
# Real-hardware performance test on this Mac: plays LS_Flythrough (auto-play, ~59 s) in a packaged-like -game window
# and records UE's CSV profiler (frame/game/render/GPU time) for two presets. Results -> PerfResults/.
cd "$(dirname "$0")"
UE="/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor.app/Contents/MacOS/UnrealEditor"
PROJ="$PWD/UE/GliderCanyonV2/GliderCanyonV2.uproject"
MAP="/Game/GliderCanyon_v2/Maps/L_GliderCanyon_v2"
mkdir -p PerfResults
{ sw_vers; sysctl -n machdep.cpu.brand_string; sysctl -n hw.memsize | awk '{print $1/1073741824 " GB RAM"}';
  system_profiler SPDisplaysDataType | grep -E "Chipset|Resolution|Cores" ; } > PerfResults/system_info.txt
launch () {  # $1 = max seconds, rest = UE args; kills the game if it does not exit by itself
  local t=$1; shift
  "$UE" "$PROJ" "$MAP" "$@" >/dev/null 2>&1 & local pid=$!
  for ((i=0; i<t; i++)); do kill -0 $pid 2>/dev/null || return 0; sleep 1; done
  kill $pid 2>/dev/null; sleep 2; kill -9 $pid 2>/dev/null; return 0
}
run () {  # $1 = preset name, $2 = extra console vars
  echo "== preset $1"
  rm -rf UE/GliderCanyonV2/Saved/Profiling/CSV
  # warm-up pass (shader/PSO compile) is not measured
  launch 90 -game -windowed -ResX=1920 -ResY=1080 -nosound -NoVSync -ExecCmds="t.MaxFPS 0,$2"
  launch 150 -game -windowed -ResX=1920 -ResY=1080 -nosound -NoVSync -ExecCmds="t.MaxFPS 0,$2" \
       -csvCaptureFrames=3000 -csvGpuStats -csvExitOnCompletion
  f=$(ls -t UE/GliderCanyonV2/Saved/Profiling/CSV/*.csv 2>/dev/null | head -1)
  if [ -n "$f" ]; then cp "$f" "PerfResults/perf_$1.csv"; python3 Scripts/summarize_perf_csv.py "PerfResults/perf_$1.csv" | tee "PerfResults/summary_$1.txt"
  else echo "no CSV produced for $1 (see UE/GliderCanyonV2/Saved/Logs)"; fi
}
run High ""
run Performance "r.DynamicGlobalIlluminationMethod 0,r.ReflectionMethod 2,r.Shadow.Virtual.Enable 0,sg.ShadowQuality 2,r.ScreenPercentage 75"
