# WindRoute：肌电滑翔游戏

Unreal Engine 5 C++ 滑翔游戏与双通道肌电桥接服务的迁移源码。此快照为取消 Petalwake 参考低空航线和草浪后的版本。包含游戏场景、资产、音乐、航线、源码、肌电桥接与地貌源素材；不包含 Unreal Engine、第三方开发工具、本机缓存或个人肌电记录。

## 环境

- Unreal Engine **5.8.4**；需自行通过 Epic Games 安装。
- macOS：与该 UE 版本兼容的 Xcode 和命令行工具。Windows：兼容的 Visual Studio C++ 工作负载。本快照来自 macOS，Windows 尚未验证。
- 使用肌电设备时需要 Python 3.11 或更新版本及 `requirements.txt` 中的依赖。
- UE 和 Fab 草地素材不附带额外转授权；协作者应按相应许可获得使用权，公开分享前须核实素材许可。

## macOS 快速启动

1. 克隆本仓库或解压完整项目，安装 UE 5.8.4 与 Xcode，打开一次 Xcode 完成首次设置。
2. 双击 `启动UE滑翔原型.command`。脚本编译编辑器模块并启动游戏；第一次编译和加载可能较慢。默认搜索 `~/Unreal/UE_5.8` 和 `/Users/Shared/Epic Games/UE_5.8`。如果安装在其他位置，请在终端设置环境变量 `UE_EDITOR` 为 `UnrealEditor.app/Contents/MacOS/UnrealEditor` 的完整路径，然后从同一终端执行脚本。
3. 键盘测试不需要肌电服务。需要肌电时，在项目目录执行：

   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

   之后启动游戏会自动启动桥接服务；也可单独双击 `启动肌电服务.command`。8896 端口已占用时不会重复启动，请确认占用者是本项目的服务。

## Windows 迁移

安装 UE 5.8.4、Visual Studio C++ 工作负载及 Python。打开 `WindRoute.uproject`，按提示生成和编译项目模块。肌电服务可在项目目录通过 PowerShell 启动：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m backend.server --ws-port 8896 --swap-device-channels --data-root .
```

然后从 UE 编辑器运行游戏，或用 UE 的 `UnrealEditor.exe` 打开本项目并传入 `-game`。Windows 的设备驱动、串口名称、构建与渲染需要在目标机器实测。

## 控制与肌电

- 默认键盘左右方向键转向；R 开始或恢复，T 重开，E 切换肌电／键盘，H 显示操作详情。
- 连接设备后，在游戏中用 P 选择串口、D 连接，按 C 打开校准界面、空格开始；依提示操作，校准完成后 R 恢复。
- 本机接线约定 CH2 为左手、CH1 为右手，服务参数 `--swap-device-channels` 对应这一配置。设备或接线改变时须重新确认映射并重新校准。
- 桥接使用本机 `127.0.0.1:8896` WebSocket。`sessions/` 为本地采集输出，已被 Git 忽略；请勿上传肌电记录。

## 仓库内容

`Content/`、`Config/`、`Source/` 为 UE 工程；`backend/` 为肌电桥接；`Assets/`、`SceneSource/` 为素材和峡谷地貌源文件；`AudioReview/`、`RouteReview/` 保存制作和审核资料。`Tools/` 包含制作时的历史工具，其中部分仍有原电脑绝对路径或依赖本机应用，仅供参考，运行游戏不需要它们。UE 构建缓存、虚拟环境与运行记录均不入库。

场景使用 Fab 草地素材。当前 UE 日志中已有一个旧贴图路径缺失提示；现有画面仍可运行，但在新设备上应检查草地外观，必要时从有授权的 Fab 资源修复引用。
