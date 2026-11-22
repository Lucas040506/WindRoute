using UnrealBuildTool;
using System.Collections.Generic;
public class WindRouteTarget : TargetRules
{
    public WindRouteTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("WindRoute");
    }
}
