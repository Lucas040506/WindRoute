using UnrealBuildTool;
public class WindRoute : ModuleRules
{
    public WindRoute(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore", "Json", "WebSockets", "ProceduralMeshComponent" });
    }
}
