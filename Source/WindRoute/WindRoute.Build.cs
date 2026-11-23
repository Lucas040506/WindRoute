using UnrealBuildTool;
public class WindRoute : ModuleRules
{
    public WindRoute(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PrivateDependencyModuleNames.AddRange(new[] { "RenderCore", "SlateCore" });
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "Json", "WebSockets", "ProceduralMeshComponent" });
    }
}
