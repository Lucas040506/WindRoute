#include "FlightEnvironment.h"
#include "FlightPawn.h"
#include "ControlMath.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/SkyAtmosphereComponent.h"
#include "Engine/StaticMesh.h"
#include "KismetProceduralMeshLibrary.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
float RiverCenter(float X) { return 300.f*FMath::Sin(X/11500.f)+160.f*FMath::Sin(X/5100.f); }
float TerrainHeight(float X,float Y)
{
    const float D=FMath::Abs(Y-RiverCenter(X));
    const float Rise=FMath::Max(0.f,D-1350.f);
    return -360.f + .095f*Rise + .000015f*Rise*Rise
        + (1.f-FMath::Exp(-Rise/600.f))*(150.f*FMath::Sin(X/4800.f+Y/1900.f)+70.f*FMath::Sin(X/1700.f-Y/2300.f));
}
void SetMesh(UProceduralMeshComponent* Mesh, const TArray<FVector>& Vertices, const TArray<int32>& Triangles, const TArray<FVector2D>& UVs)
{
    TArray<FVector> Normals; TArray<FProcMeshTangent> Tangents;
    UKismetProceduralMeshLibrary::CalculateTangentsForMesh(Vertices,Triangles,UVs,Normals,Tangents);
    TArray<FColor> Colors;
    Mesh->CreateMeshSection(0,Vertices,Triangles,Normals,UVs,Colors,Tangents,false);
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}
}

AFlightEnvironment::AFlightEnvironment()
{
    PrimaryActorTick.bCanEverTick=false;
    SceneRoot=CreateDefaultSubobject<USceneComponent>(TEXT("Root")); RootComponent=SceneRoot;
    Terrain=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("Terrain")); Terrain->SetupAttachment(SceneRoot);
    River=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("River")); River->SetupAttachment(SceneRoot);
    GateMesh=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("GuidanceRings")); GateMesh->SetupAttachment(SceneRoot);
    MountainMesh=CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("FacetedMountains")); MountainMesh->SetupAttachment(SceneRoot);
    Rocks=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Rocks")); Rocks->SetupAttachment(SceneRoot);
    Ground=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Water")); Ground->SetupAttachment(SceneRoot);
    Banks=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Banks")); Banks->SetupAttachment(SceneRoot);
    Hills=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Mountains")); Hills->SetupAttachment(SceneRoot);
    Trees=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Trees")); Trees->SetupAttachment(SceneRoot);
    Trunks=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Trunks")); Trunks->SetupAttachment(SceneRoot);
    Guide=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("Guide")); Guide->SetupAttachment(SceneRoot);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cone(TEXT("/Engine/BasicShapes/Cone.Cone"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(TEXT("/Engine/BasicShapes/Sphere.Sphere"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> WaterMat(TEXT("/Game/WindRoute/Materials/M_Water.M_Water"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> GrassMat(TEXT("/Game/WindRoute/Materials/M_Grass.M_Grass"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> CliffMat(TEXT("/Game/WindRoute/Materials/M_Cliff.M_Cliff"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> TreeMat(TEXT("/Game/WindRoute/Materials/M_Tree.M_Tree"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> TrunkMat(TEXT("/Game/WindRoute/Materials/M_Trunk.M_Trunk"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> GuideMat(TEXT("/Game/WindRoute/Materials/M_Guide.M_Guide"));
    if(Cube.Succeeded()) Trunks->SetStaticMesh(Cube.Object);
    if(Cone.Succeeded()) { Hills->SetStaticMesh(Cone.Object); Trees->SetStaticMesh(Cone.Object); }
    if(Sphere.Succeeded()) { Guide->SetStaticMesh(Sphere.Object); Rocks->SetStaticMesh(Sphere.Object); }
    if(WaterMat.Succeeded()) River->SetMaterial(0,WaterMat.Object);
    if(GrassMat.Succeeded()) Terrain->SetMaterial(0,GrassMat.Object);
    if(CliffMat.Succeeded()) { MountainMesh->SetMaterial(0,CliffMat.Object); Rocks->SetMaterial(0,CliffMat.Object); }
    if(TreeMat.Succeeded()) Trees->SetMaterial(0,TreeMat.Object);
    if(TrunkMat.Succeeded()) Trunks->SetMaterial(0,TrunkMat.Object);
    if(GuideMat.Succeeded()) { Guide->SetMaterial(0,GuideMat.Object); GateMesh->SetMaterial(0,GuideMat.Object); }
    for (auto* Mesh : {Ground.Get(),Banks.Get(),Hills.Get(),Trees.Get(),Trunks.Get(),Rocks.Get(),Guide.Get()}) Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Trees->SetCastShadow(false); Trunks->SetCastShadow(false);
    Sun=CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("Sun")); Sun->SetupAttachment(SceneRoot);
    Sun->SetAtmosphereSunLight(true); Sun->SetMobility(EComponentMobility::Movable);
    Sun->SetRelativeRotation(FRotator(-35,30,0)); Sun->SetIntensity(3.f); Sun->SetLightColor(FLinearColor(1.f,.86f,.72f));
    Atmosphere=CreateDefaultSubobject<USkyAtmosphereComponent>(TEXT("Atmosphere")); Atmosphere->SetupAttachment(SceneRoot);
    Sky=CreateDefaultSubobject<USkyLightComponent>(TEXT("Sky")); Sky->SetupAttachment(SceneRoot); Sky->SetMobility(EComponentMobility::Movable); Sky->SetIntensity(.9f);
    Fog=CreateDefaultSubobject<UExponentialHeightFogComponent>(TEXT("ValleyFog")); Fog->SetupAttachment(SceneRoot);
    Fog->SetFogDensity(.0012f); Fog->SetFogInscatteringColor(FLinearColor(.48f,.64f,.68f));
}
void AFlightEnvironment::BeginPlay()
{
    Super::BeginPlay();
    // A single gently undulating terrain mesh: the banks rise away from the river.
    constexpr int Rows=230, Cols=21;
    TArray<FVector> V; TArray<FVector2D> UV; TArray<int32> T;
    for(int X=0;X<Rows;++X) for(int Y=0;Y<Cols;++Y)
    {
        const float PX=-2000.f+X*600.f, PY=(Y-10)*800.f;
        V.Add(FVector(PX,PY,TerrainHeight(PX,PY))); UV.Add(FVector2D(X/10.f,Y/10.f));
    }
    for(int X=0;X<Rows-1;++X) for(int Y=0;Y<Cols-1;++Y)
    {
        const int A=X*Cols+Y,B=A+Cols;
        T.Append({A,A+1,B,A+1,B+1,B});
    }
    SetMesh(Terrain,V,T,UV);
    V.Reset(); UV.Reset(); T.Reset();
    for(int X=0;X<Rows;++X)
    {
        const float PX=-2000.f+X*600.f, C=RiverCenter(PX);
        V.Add(FVector(PX,C-1200.f,-350.f)); V.Add(FVector(PX,C+1200.f,-350.f));
        UV.Add(FVector2D(X/10.f,0)); UV.Add(FVector2D(X/10.f,1));
        if(X<Rows-1) { const int A=X*2; T.Append({A,A+1,A+2,A+1,A+3,A+2}); }
    }
    SetMesh(River,V,T,UV);
    FRandomStream Random(5230);
    // Individual jagged, flat-shaded peaks with varied footprints and offset summits.
    V.Reset(); UV.Reset(); T.Reset();
    const auto AddFace=[&](const FVector& A,const FVector& B,const FVector& C)
    {
        const int Base=V.Num(); V.Append({A,B,C});
        UV.Append({FVector2D(0,0),FVector2D(1,0),FVector2D(.5f,1)});
        T.Append({Base,Base+1,Base+2});
    };
    constexpr int Sides=7;
    for(int Row=0;Row<51;++Row) for(int Side : {-1,1})
    {
        const float X=Row*2500.f+Random.FRandRange(-700.f,700.f), Y=Side*Random.FRandRange(7000.f,8800.f);
        const float GroundZ=TerrainHeight(X,Y)-180.f, H=Random.FRandRange(1800.f,3200.f);
        const float RadiusX=Random.FRandRange(1100.f,1900.f), RadiusY=Random.FRandRange(1200.f,2100.f);
        const FVector Peak(X+Random.FRandRange(-400,400),Y+Random.FRandRange(-400,400),GroundZ+H);
        FVector Base[Sides], Shoulder[Sides];
        for(int I=0;I<Sides;++I)
        {
            const float Angle=2*PI*I/Sides, R=Random.FRandRange(.8f,1.2f);
            Base[I]=FVector(X+RadiusX*R*FMath::Cos(Angle),Y+RadiusY*R*FMath::Sin(Angle),GroundZ+Random.FRandRange(-120,100));
            Shoulder[I]=FVector(X+RadiusX*R*.52f*FMath::Cos(Angle)+Random.FRandRange(-120,120),Y+RadiusY*R*.52f*FMath::Sin(Angle)+Random.FRandRange(-120,120),GroundZ+H*Random.FRandRange(.38f,.62f));
        }
        for(int I=0;I<Sides;++I)
        {
            const int J=(I+1)%Sides;
            AddFace(Base[I],Shoulder[I],Base[J]); AddFace(Base[J],Shoulder[I],Shoulder[J]); AddFace(Shoulder[I],Peak,Shoulder[J]);
        }
    }
    SetMesh(MountainMesh,V,T,UV);
    for(int Row=0;Row<160;++Row) for(int Side : {-1,1}) for(int N=0;N<3;++N)
    {
        const float X=Row*780.f+Random.FRandRange(-250,250), Y=RiverCenter(X)+Side*Random.FRandRange(1900,6500);
        const float Z=TerrainHeight(X,Y), S=Random.FRandRange(.7f,1.35f);
        Trunks->AddInstance(FTransform(FRotator::ZeroRotator,FVector(X,Y,Z+85*S),FVector(.20f*S,.20f*S,1.7f*S)));
        for(int Layer=0;Layer<2;++Layer)
            Trees->AddInstance(FTransform(FRotator(0,Random.FRandRange(0,360),0),FVector(X,Y,Z+(210+Layer*80)*S),FVector((2.0f-Layer*.35f)*S,(2.0f-Layer*.35f)*S,2.4f*S)));
        if(N==0) Rocks->AddInstance(FTransform(FRotator(0,Random.FRandRange(0,360),0),FVector(X+160,Y+130,Z+35),FVector(.8f,1.1f,.55f)));
    }
    // Optional luminous rings are centered on the same guide curve used for scoring.
    V.Reset(); UV.Reset(); T.Reset();
    constexpr int Major=32, Minor=6;
    for(int Gate=0;Gate<WindRouteControl::GateCount;++Gate)
    {
        const float D=WindRouteControl::GateDistance(Gate), X=D*100.f, Y=AFlightPawn::GuidePosition(D)*100.f;
        const float Angle=FMath::Atan(WindRouteControl::CanyonSlope(D));
        const int Base=V.Num();
        for(int A=0;A<=Major;++A) for(int B=0;B<=Minor;++B)
        {
            const float U=2*PI*A/Major, W=2*PI*B/Minor, Radius=230.f+8.f*FMath::Cos(W);
            const float Along=8.f*FMath::Sin(W), Across=Radius*FMath::Cos(U);
            V.Add(FVector(X+Along*FMath::Cos(Angle)-Across*FMath::Sin(Angle),Y+Along*FMath::Sin(Angle)+Across*FMath::Cos(Angle),WindRouteControl::GateHeight(Gate)+Radius*FMath::Sin(U)));
            UV.Add(FVector2D(static_cast<float>(A)/Major,static_cast<float>(B)/Minor));
        }
        for(int A=0;A<Major;++A) for(int B=0;B<Minor;++B)
        {
            const int P=Base+A*(Minor+1)+B, Q=P+Minor+1;
            T.Append({P,Q,P+1,P+1,Q,Q+1});
        }
    }
    SetMesh(GateMesh,V,T,UV);
    for(int I=0;4.f+I*6.f<=WindRouteControl::RouteLengthMeters;++I)
    {
        const float D=4.f+I*6.f;
        Guide->AddInstance(FTransform(FRotator::ZeroRotator,FVector(D*100.f,AFlightPawn::GuidePosition(D)*100.f,1200.f),FVector(.16f)));
    }
    Sky->RecaptureSky();
}
