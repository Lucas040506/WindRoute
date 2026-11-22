#include "FlightPawn.h"
#include "ControlMath.h"
#include "CanyonRoute.h"
#include "SemgBridgeComponent.h"
#include "Camera/CameraComponent.h"
#include "Components/InputComponent.h"
#include "Components/AudioComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "UObject/ConstructorHelpers.h"
#include "Materials/MaterialInterface.h"
#include "EngineUtils.h"

namespace {
constexpr float WindZoneDistances[] = {850.f,1010.f,1170.f,1330.f};
constexpr int WindRibbonCount = 12;
constexpr float MaxBankDegrees = 50.f;
constexpr float MaxRingBonus = 6.f;
constexpr int RingSides = 6;
FVector RoutePoint(float d) {
 const int N=UE_ARRAY_COUNT(RouteSamples); int lo=0,hi=N-1;
 while(lo+1<hi){int m=(lo+hi)/2; if(RouteSamples[m].D<=d) lo=m; else hi=m;}
 const auto& a=RouteSamples[lo]; const auto& b=RouteSamples[hi];
 float t=FMath::Clamp((d-a.D)/FMath::Max(.001f,b.D-a.D),0.f,1.f);
 return FMath::Lerp(FVector(a.X,a.Y,a.Z),FVector(b.X,b.Y,b.Z),t);
}
float RouteProgress(const FVector& P, float Previous, float MaxAdvance) {
 float best=Previous, bestSq=TNumericLimits<float>::Max();
 for(int i=0;i<UE_ARRAY_COUNT(RouteSamples)-1;++i) {
   const auto& a=RouteSamples[i]; const auto& b=RouteSamples[i+1];
   if(b.D<Previous-30.f || a.D>Previous+100.f) continue;
   const FVector2D A(a.X,a.Y), B(b.X,b.Y), Q(P.X,P.Y), AB=B-A;
   const float t=FMath::Clamp(FVector2D::DotProduct(Q-A,AB)/FMath::Max(1.f,AB.SizeSquared()),0.f,1.f);
   const float sq=(Q-(A+AB*t)).SizeSquared();
   if(sq<bestSq){bestSq=sq;best=FMath::Lerp(a.D,b.D,t);}
 }
 return FMath::Clamp(best,Previous,FMath::Min(WindRouteControl::RouteLengthMeters,Previous+MaxAdvance));
}
FVector RouteRight(float d) { FVector f=(RoutePoint(FMath::Min(d+5.f,WindRouteControl::RouteLengthMeters))-RoutePoint(FMath::Max(d-5.f,0.f))).GetSafeNormal(); return FVector(-f.Y,f.X,0).GetSafeNormal(); }
}
AFlightPawn::AFlightPawn()
{
    PrimaryActorTick.bCanEverTick = true;
    AutoPossessPlayer = EAutoReceiveInput::Player0;
    Pivot = CreateDefaultSubobject<USceneComponent>(TEXT("Pivot")); RootComponent = Pivot;
    Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Fuselage")); Body->SetupAttachment(Pivot);
    Wing = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Wings")); Wing->SetupAttachment(Pivot);
    Tail = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Tailplane")); Tail->SetupAttachment(Pivot);
    Fin = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Tailfin")); Fin->SetupAttachment(Pivot);
    CanyonRings=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("CanyonRings")); CanyonRings->SetupAttachment(Pivot); CanyonRings->SetAbsolute(true,true,true); CanyonRings->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    CanyonRings->SetCastShadow(false);
    WindRibbons=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("InteractiveWindRibbons")); WindRibbons->SetupAttachment(Pivot);
    WindRibbons->SetAbsolute(true,true,true); WindRibbons->SetCollisionEnabled(ECollisionEnabled::NoCollision); WindRibbons->SetCastShadow(false);
    WingTrails=CreateDefaultSubobject<UInstancedStaticMeshComponent>(TEXT("WingTrails")); WingTrails->SetupAttachment(Pivot); WingTrails->SetAbsolute(true,true,true);
    WingTrails->SetCollisionEnabled(ECollisionEnabled::NoCollision); WingTrails->SetCastShadow(false);
    WindAudio=CreateDefaultSubobject<UAudioComponent>(TEXT("WindAudio")); WindAudio->SetupAttachment(Pivot);
    WindAudio->bAutoActivate=false; WindAudio->bAllowSpatialization=false;
    MusicAudio=CreateDefaultSubobject<UAudioComponent>(TEXT("MusicAudio")); MusicAudio->SetupAttachment(Pivot);
    MusicAudio->bAutoActivate=false; MusicAudio->bAllowSpatialization=false;
    static ConstructorHelpers::FObjectFinder<USoundBase> WindAsset(TEXT("/Game/WindRoute/Audio/glide_wind.glide_wind"));
    static ConstructorHelpers::FObjectFinder<USoundBase> RingAsset(TEXT("/Game/WindRoute/Audio/ring_pass.ring_pass"));
    static ConstructorHelpers::FObjectFinder<USoundBase> MusicAsset(TEXT("/Game/WindRoute/Audio/canyon_music.canyon_music"));
    static ConstructorHelpers::FObjectFinder<USoundBase> ApproachAsset(TEXT("/Game/WindRoute/Audio/ring_approach.ring_approach"));
    static ConstructorHelpers::FObjectFinder<USoundBase> MissAsset(TEXT("/Game/WindRoute/Audio/ring_missed.ring_missed"));
    static ConstructorHelpers::FObjectFinder<USoundBase> RestoreAsset(TEXT("/Game/WindRoute/Audio/power_restored.power_restored"));
    static ConstructorHelpers::FObjectFinder<USoundBase> SweepAsset(TEXT("/Game/WindRoute/Audio/wind_sweep.wind_sweep"));
    if(SweepAsset.Succeeded()) WindSweepSound=SweepAsset.Object;
    if(MusicAsset.Succeeded()) MusicAudio->SetSound(MusicAsset.Object);
    if(ApproachAsset.Succeeded()) ApproachSound=ApproachAsset.Object;
    if(MissAsset.Succeeded()) MissSound=MissAsset.Object;
    if(RestoreAsset.Succeeded()) RestoreSound=RestoreAsset.Object;
    if (WindAsset.Succeeded()) WindAudio->SetSound(WindAsset.Object);
    if (RingAsset.Succeeded()) RingSound=RingAsset.Object;
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> GliderMat(TEXT("/Game/WindRoute/Materials/M_Glider.M_Glider"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> AccentMat(TEXT("/Game/WindRoute/Materials/M_Accent.M_Accent"));
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Cube(TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (Cube.Succeeded()) { CanyonRings->SetStaticMesh(Cube.Object); WindRibbons->SetStaticMesh(Cube.Object); Body->SetStaticMesh(Cube.Object); Wing->SetStaticMesh(Cube.Object); Tail->SetStaticMesh(Cube.Object); Fin->SetStaticMesh(Cube.Object); WingTrails->SetStaticMesh(Cube.Object); }
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> RingGlowMat(TEXT("/Game/WindRoute/Materials/M_RingGlow.M_RingGlow"));
    if(RingGlowMat.Succeeded()) CanyonRings->SetMaterial(0,RingGlowMat.Object);
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> WindRibbonMat(TEXT("/Game/WindRoute/Materials/M_Water.M_Water"));
    if(WindRibbonMat.Succeeded()) WindRibbons->SetMaterial(0,WindRibbonMat.Object);
    if (GliderMat.Succeeded()) { Wing->SetMaterial(0,GliderMat.Object); Tail->SetMaterial(0,GliderMat.Object); WingTrails->SetMaterial(0,GliderMat.Object); }
    if (AccentMat.Succeeded()) { Body->SetMaterial(0,AccentMat.Object); Fin->SetMaterial(0,AccentMat.Object); }
    Body->SetRelativeScale3D(FVector(1.3f,.24f,.18f));
    Wing->SetRelativeScale3D(FVector(.38f,4.2f,.035f));
    Tail->SetRelativeLocation(FVector(-58,0,8)); Tail->SetRelativeScale3D(FVector(.25f,1.4f,.04f));
    Fin->SetRelativeLocation(FVector(-58,0,20)); Fin->SetRelativeScale3D(FVector(.25f,.05f,.35f));
    for (auto* Mesh : {Body.Get(),Wing.Get(),Tail.Get(),Fin.Get()}) Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("CameraBoom")); SpringArm->SetupAttachment(Pivot);
    SpringArm->TargetArmLength=1050; SpringArm->SetRelativeLocation(FVector(0,0,250)); SpringArm->SetRelativeRotation(FRotator(-10,0,0));
    SpringArm->bDoCollisionTest=false; SpringArm->bEnableCameraLag=true; SpringArm->CameraLagSpeed=5;
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("Camera")); Camera->SetupAttachment(SpringArm,USpringArmComponent::SocketName); Camera->FieldOfView=58;
    Camera->PostProcessSettings.bOverride_BloomIntensity=true; Camera->PostProcessSettings.BloomIntensity=.8f;
    Emg=CreateDefaultSubobject<USemgBridgeComponent>(TEXT("SemgBridge"));
}
void AFlightPawn::BeginPlay()
{
    Super::BeginPlay();
    for(TActorIterator<AActor> It(GetWorld()); It; ++It) if(It->ActorHasTag(TEXT("OptionalRing"))) It->SetActorHiddenInGame(true);
    CanyonRings->ClearInstances();
    for(int i=0;i<WindRouteControl::GateCount*RingSides;++i)
        CanyonRings->AddInstance(FTransform(FRotator::ZeroRotator,FVector(0,0,-1000000),FVector(.001f)),true);
    WindRibbons->ClearInstances();
    for(int i=0;i<UE_ARRAY_COUNT(WindZoneDistances)*WindRibbonCount;++i)
        WindRibbons->AddInstance(FTransform(FRotator::ZeroRotator,FVector(0,0,-10000),FVector(.001f)),true);
    UpdateWindRibbons(0.f);
    ResetRoute();
    bPausedForSignal=true;
    // Optional local inspection point; normal play always starts at the beginning.
    if(FParse::Param(FCommandLine::Get(),TEXT("GrassPreview"))) {
        DistanceMeters=1000.f; GatesAttempted=12; FlightYaw=(RoutePoint(1005.f)-RoutePoint(995.f)).Rotation().Yaw;
        SetActorLocation(RoutePoint(DistanceMeters)); SetActorRotation(FRotator(0.f,FlightYaw,0.f)); RefreshRingVisuals(); ResetTrails();
    }
    WindAudio->SetVolumeMultiplier(0.f);
    if (WindAudio->Sound) WindAudio->Play();
}
void AFlightPawn::UpdateWind(float Dt)
{
    const bool bFlying=!bFinished && !bCalibrationScreen && !bPausedForSignal && !bResumeRequested;
    const float Target=bFlying && !bSoundMuted ? SoundVolume*(.68f+.12f*FMath::Abs(Steering)+(BoostTime>0 || WindZoneTime>0?.12f:0.f)) : 0.f;
    WindCurrentVolume=FMath::FInterpTo(WindCurrentVolume,Target,Dt,2.0f);
    WindAudio->SetVolumeMultiplier(WindCurrentVolume);
    WindAudio->SetPitchMultiplier((bLowPower?.92f:1.f)+.08f*FMath::Abs(Steering));
    if(bFlying && MusicAudio->Sound && !MusicAudio->IsPlaying()) { MusicAudio->SetVolumeMultiplier(0.f); MusicAudio->Play(); }
    const float MusicTarget=bFlying && !bSoundMuted ? SoundVolume*(bLowPower?.42f:.62f) : 0.f;
    MusicCurrentVolume=FMath::FInterpTo(MusicCurrentVolume,MusicTarget,Dt,1.2f);
    MusicAudio->SetVolumeMultiplier(MusicCurrentVolume);
}
void AFlightPawn::ToggleSound() { bSoundMuted=!bSoundMuted; }
void AFlightPawn::Louder() { SoundVolume=FMath::Min(1.f,SoundVolume+.1f); }
void AFlightPawn::Quieter() { SoundVolume=FMath::Max(0.f,SoundVolume-.1f); }
void AFlightPawn::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    Input->BindAxis(TEXT("GliderSteer"),this,&AFlightPawn::Steer);



    Input->BindAction(TEXT("ToggleSound"),IE_Pressed,this,&AFlightPawn::ToggleSound);
    Input->BindAction(TEXT("SoundDown"),IE_Pressed,this,&AFlightPawn::Quieter);
    Input->BindAction(TEXT("SoundUp"),IE_Pressed,this,&AFlightPawn::Louder);
    Input->BindAction(TEXT("ToggleDetails"), IE_Pressed, this, &AFlightPawn::ToggleDetails);
    Input->BindAction(TEXT("SensitivityDown"), IE_Pressed, this, &AFlightPawn::DecreaseSensitivity);
    Input->BindAction(TEXT("SensitivityUp"), IE_Pressed, this, &AFlightPawn::IncreaseSensitivity);
    Input->BindAction(TEXT("NextPort"), IE_Pressed, this, &AFlightPawn::NextPort);
    Input->BindAction(TEXT("ConnectDevice"), IE_Pressed, this, &AFlightPawn::ConnectSelectedDevice);
    Input->BindAction(TEXT("Calibrate"), IE_Pressed, this, &AFlightPawn::OpenCalibration);
    Input->BindAction(TEXT("StartCalibration"), IE_Pressed, this, &AFlightPawn::StartCalibration);
    Input->BindAction(TEXT("CloseCalibration"), IE_Pressed, this, &AFlightPawn::CloseCalibration);
    Input->BindAction(TEXT("UseSimulator"), IE_Pressed, this, &AFlightPawn::SwitchToSimulator);
    Input->BindAction(TEXT("ToggleEmg"), IE_Pressed, this, &AFlightPawn::ToggleEmg);
    Input->BindAction(TEXT("ResumeFlight"), IE_Pressed, this, &AFlightPawn::ResumeFlight);
    Input->BindAction(TEXT("RestartFlight"), IE_Pressed, this, &AFlightPawn::RestartFlight);
    Input->BindAction(TEXT("SimLeft"),IE_Pressed,this,&AFlightPawn::SimulatorLeftOn);
    Input->BindAction(TEXT("SimLeft"),IE_Released,this,&AFlightPawn::SimulatorLeftOff);
    Input->BindAction(TEXT("SimRight"),IE_Pressed,this,&AFlightPawn::SimulatorRightOn);
    Input->BindAction(TEXT("SimRight"),IE_Released,this,&AFlightPawn::SimulatorRightOff);
}
void AFlightPawn::ResetRoute()
{
    SetActorLocation(RoutePoint(0));
    RouteOffset=0; BoostTime=0; RingSpeedBonus=0; RingBoostGrace=0; WindZoneTime=0; WindZoneFeedbackTime=0; WindZonesVisited.Init(false,UE_ARRAY_COUNT(WindZoneDistances)); bApproachPlayed=false; bLowPower=false; PowerHeightLoss=0.f; CollectedRings.Init(false,WindRouteControl::GateCount);
    GatesPassed=0; GatesAttempted=0; GateFeedbackTime=0; ConsecutiveGates=0; SignalPauseCount=0; RefreshRingVisuals();
    BestStreak=0; LeftSteeringTime=0; RightSteeringTime=0;
    DistanceMeters=0; GuideRatio=0; CurrentStreak=0; GuidedTime=0; EligibleTime=0;
    Steering=0; LateralSpeed=0; Lift=0; Dive=0; HeightOffset=0; Gesture={}; bDiveArmed=false; FlightSpeed=WindRouteControl::FlightSpeedMetersPerSecond; VerticalSpeed=0; bLiftActive=false; bFinished=false; ResetTrails();
    FlightYaw=(RoutePoint(5)-RoutePoint(0)).Rotation().Yaw;
    SetActorRotation(FRotator(0,FlightYaw,0));
    Wing->SetRelativeRotation(FRotator::ZeroRotator); Body->SetRelativeRotation(FRotator::ZeroRotator); Tail->SetRelativeRotation(FRotator::ZeroRotator); Fin->SetRelativeRotation(FRotator::ZeroRotator);
}
void AFlightPawn::RestartFlight()
{
    if (bCalibrationScreen) return;
    ResetRoute();
    if (bUsingEmg) { bPausedForSignal=true; ResumeFlight(); }
}
void AFlightPawn::ResetTrails()
{
    LeftTrailPoints.Reset(); RightTrailPoints.Reset(); TrailClock=0;
    WingTrails->ClearInstances();
}
void AFlightPawn::UpdateTrails(float DeltaTime)
{
    TrailClock+=DeltaTime;
    if (TrailClock<.06f) return;
    TrailClock=0;
    const FVector P=GetActorLocation();
    const float Tilt=FMath::DegreesToRadians(Steering*MaxBankDegrees);
    const FVector Tip=GetActorRotation().RotateVector(FVector(0,200.f*FMath::Cos(Tilt),-200.f*FMath::Sin(Tilt)));
    LeftTrailPoints.Insert(P-Tip,0); RightTrailPoints.Insert(P+Tip,0);
    constexpr int Count=18;
    if (LeftTrailPoints.Num()>Count+1) LeftTrailPoints.SetNum(Count+1);
    if (RightTrailPoints.Num()>Count+1) RightTrailPoints.SetNum(Count+1);
    if (WingTrails->GetInstanceCount()!=2*Count)
    {
        WingTrails->ClearInstances();
        for(int I=0;I<2*Count;++I) WingTrails->AddInstance(FTransform(FRotator::ZeroRotator,FVector(0,0,-10000),FVector(.001f)));
    }
    for(int Side=0;Side<2;++Side) for(int I=0;I<Count;++I)
    {
        const auto& Points=Side==0?LeftTrailPoints:RightTrailPoints;
        FTransform Xform(FRotator::ZeroRotator,FVector(0,0,-10000),FVector(.001f));
        if (Points.IsValidIndex(I+1))
        {
            const FVector A=Points[I], B=Points[I+1], Delta=A-B;
            const float Width=FMath::Lerp(2.f,.4f,static_cast<float>(I)/Count);
            Xform=FTransform(Delta.Rotation(),(A+B)*.5f,FVector(Delta.Size()/100.f,Width/100.f,Width/100.f));
        }
        WingTrails->UpdateInstanceTransform(Side*Count+I,Xform,true,Side==1 && I==Count-1,true);
    }
}
void AFlightPawn::RefreshRingVisuals()
{
    for(int i=0;i<WindRouteControl::GateCount;++i) {
        const bool visible=i>=GatesAttempted && i<GatesAttempted+3;
        const float d=WindRouteControl::GateDistance(i);
        const FVector center=RoutePoint(d);
        const FVector forward=(RoutePoint(FMath::Min(d+5.f,WindRouteControl::RouteLengthMeters))-RoutePoint(FMath::Max(d-5.f,0.f))).GetSafeNormal();
        const FVector right=RouteRight(d);
        const FVector up=FVector::CrossProduct(forward,right).GetSafeNormal();
        for(int j=0;j<RingSides;++j) {
            FTransform xf(FRotator::ZeroRotator,FVector(0,0,-1000000),FVector(.001f));
            if(visible) {
                const float a=2.f*PI*j/RingSides+PI/6.f, b=2.f*PI*(j+1)/RingSides+PI/6.f;
                const FVector p1=center+(right*FMath::Cos(a)+up*FMath::Sin(a))*650.f;
                const FVector p2=center+(right*FMath::Cos(b)+up*FMath::Sin(b))*650.f;
                const FVector delta=p2-p1;
                xf=FTransform(delta.Rotation(),(p1+p2)*.5f,FVector(delta.Size()/100.f,.65f,.65f));
            }
            const bool dirty=(i==WindRouteControl::GateCount-1 && j==RingSides-1);
            CanyonRings->UpdateInstanceTransform(i*RingSides+j,xf,true,dirty,true);
        }
    }
}
void AFlightPawn::UpdateWindRibbons(float Dt)
{
    WindRibbonAge+=Dt; WindRibbonClock+=Dt;
    if(Dt>0 && WindRibbonClock<.08f) return;
    WindRibbonClock=0;
    for(int zone=0;zone<UE_ARRAY_COUNT(WindZoneDistances);++zone) {
        const float d=WindZoneDistances[zone]; const float side=zone%2==0?-900.f:900.f;
        const FVector center=RoutePoint(d)+RouteRight(d)*side;
        const FVector forward=(RoutePoint(d+5.f)-RoutePoint(d-5.f)).GetSafeNormal();
        const FVector right=RouteRight(d);
        for(int j=0;j<WindRibbonCount;++j) {
            const float phase=(float)j/WindRibbonCount*2.f*PI+WindRibbonAge*.55f;
            const float axial=FMath::Fmod(j*170.f+WindRibbonAge*250.f,1900.f)-950.f;
            const FVector location=center+forward*axial+right*(FMath::Cos(phase)*500.f)+FVector(0,0,FMath::Sin(phase)*350.f);
            const bool dirty=zone==UE_ARRAY_COUNT(WindZoneDistances)-1 && j==WindRibbonCount-1;
            WindRibbons->UpdateInstanceTransform(zone*WindRibbonCount+j,FTransform(forward.Rotation(),location,FVector(2.f,.16f,.16f)),true,dirty,true);
        }
    }
}
void AFlightPawn::Steer(float Value) { KeyboardAxis = FMath::Clamp(Value,-1.f,1.f); }
void AFlightPawn::LiftInput(float Value) { KeyboardLift=FMath::Clamp(Value,0.f,1.f); }
void AFlightPawn::DiveInput(float Value) { KeyboardDive=FMath::Clamp(Value,0.f,1.f); }
void AFlightPawn::ToggleFlightMode()
{
    if (bCalibrationScreen || bFinished) return;
    bGlideMode=!bGlideMode;
    HeightOffset=GetActorLocation().Z-1300.f;
    FlightSpeed=WindRouteControl::FlightSpeedMetersPerSecond;
    VerticalSpeed=0.f;
}
void AFlightPawn::NextPort() { if (Emg->AvailablePorts.Num()>0) SelectedPortIndex=(SelectedPortIndex+1)%Emg->AvailablePorts.Num(); else Emg->RequestPorts(); }
void AFlightPawn::ConnectSelectedDevice()
{
    if (!Emg->AvailablePorts.IsValidIndex(SelectedPortIndex)) { Emg->RequestPorts(); return; }
    bResumeRequested=false; bUsingEmg=true; bPausedForSignal=true; Emg->ConnectDevice(Emg->AvailablePorts[SelectedPortIndex]);
}
void AFlightPawn::OpenCalibration() { ResetRoute(); bResumeRequested=false; bCalibrationScreen=true; bUsingEmg=true; bPausedForSignal=true; }
void AFlightPawn::StartCalibration() { if (bCalibrationScreen && !Emg->bSimulated && Emg->HasRecentSamples() && Emg->CalibrationPhase.IsEmpty() && !Emg->bCalibrationPending) { bUsingEmg=true; bPausedForSignal=true; Emg->RequestCalibration(); } }
void AFlightPawn::CloseCalibration() { if (!bCalibrationScreen) return; if (!Emg->CalibrationPhase.IsEmpty() || Emg->bCalibrationPending) Emg->CancelCalibration(); bCalibrationScreen=false; bPausedForSignal=true; }
void AFlightPawn::SwitchToSimulator() { bUsingEmg=true; bPausedForSignal=true; Emg->UseSimulator(); }
void AFlightPawn::IncreaseSensitivity() { Sensitivity=FMath::Min(2.f,Sensitivity+.1f); }
void AFlightPawn::DecreaseSensitivity() { Sensitivity=FMath::Max(.5f,Sensitivity-.1f); }
void AFlightPawn::ToggleDetails() { bShowDetails=!bShowDetails; }
void AFlightPawn::ToggleEmg() { SetUseEmg(!bUsingEmg); }
void AFlightPawn::SetUseEmg(bool bEnable)
{
    if (!bEnable) { bUsingEmg=false; bPausedForSignal=false; bResumeRequested=false; return; }
    bUsingEmg=true;
    // A new session starts paused until a valid, fresh, relaxed signal arrives.
    bPausedForSignal=true; ResumeFlight();
}
void AFlightPawn::ResumeFlight()
{
    if (!bUsingEmg) { if (bFinished) ResetRoute(); bPausedForSignal=false; bCalibrationScreen=false; return; }
    // R is an explicit request: wait for a sustained release instead of silently ignoring it.
    bPausedForSignal=true; bResumeRequested=true; ReleaseHoldTime=0;
}
void AFlightPawn::SimulatorLeftOn() { SimulatorLeft=55; SendSimulator(); }
void AFlightPawn::SimulatorLeftOff() { SimulatorLeft=0; SendSimulator(); }
void AFlightPawn::SimulatorRightOn() { SimulatorRight=55; SendSimulator(); }
void AFlightPawn::SimulatorRightOff() { SimulatorRight=0; SendSimulator(); }
void AFlightPawn::SendSimulator() { Emg->SetSimulatedLevels(SimulatorLeft,SimulatorRight); }
float AFlightPawn::GuidePosition(float D) { return WindRouteControl::Guide(D); }

void AFlightPawn::Tick(float Dt)
{
    Super::Tick(Dt);
    FrameTimeMs=FMath::FInterpTo(FrameTimeMs,Dt*1000.f,Dt,2.f);
    UpdateWind(Dt);
    if (bResumeRequested)
    {
        if (!Emg->HasFreshSignal()) { bResumeRequested=false; bPausedForSignal=true; ReleaseHoldTime=0; }
        else
        {
            ReleaseHoldTime=(Emg->LeftLevel<10 && Emg->RightLevel<10)?ReleaseHoldTime+Dt:0.f;
            if (ReleaseHoldTime>=.5f)
            {
                if (bFinished) ResetRoute();
                bResumeRequested=false; bPausedForSignal=false; bCalibrationScreen=false;
            }
        }
    }
    if (bFinished || bCalibrationScreen) return;
    if (bUsingEmg && !Emg->HasFreshSignal()) { if (!bPausedForSignal) ++SignalPauseCount; bPausedForSignal=true; }
    if (bPausedForSignal) { Steering=0; LateralSpeed=0; Lift=0; Dive=0; Gesture={}; bDiveArmed=false; bLiftActive=false; return; }
    const float Target=bUsingEmg ? FMath::Clamp(Emg->GetSteering()*Sensitivity,-1.f,1.f) : KeyboardAxis;
    Steering=FMath::FInterpConstantTo(Steering,Target,Dt,3.f);
    LateralSpeed=FMath::FInterpConstantTo(LateralSpeed,Steering*400.f,Dt,600.f);
    GateFeedbackTime=FMath::Max(0.f,GateFeedbackTime-Dt);
    Lift=0.f; Dive=0.f; bLiftActive=false; bDiveArmed=false;
    const FVector OldPosition=GetActorLocation();
    BoostTime=FMath::Max(0.f,BoostTime-Dt);
    RingBoostGrace=FMath::Max(0.f,RingBoostGrace-Dt);
    if(RingBoostGrace<=0.f) RingSpeedBonus=FMath::Max(0.f,RingSpeedBonus-.8f*Dt);
    WindZoneTime=FMath::Max(0.f,WindZoneTime-Dt); WindZoneFeedbackTime=FMath::Max(0.f,WindZoneFeedbackTime-Dt);
    UpdateWindRibbons(Dt);
    const float TargetSpeed=bLowPower ? 16.f : FMath::Min(WindRouteControl::FlightSpeedMetersPerSecond+MaxRingBonus,WindRouteControl::FlightSpeedMetersPerSecond+RingSpeedBonus+(WindZoneTime>0?2.f:0.f));
    FlightSpeed=FMath::FInterpTo(FlightSpeed,TargetSpeed,Dt,.5f);
    PowerHeightLoss=FMath::FInterpConstantTo(PowerHeightLoss,bLowPower?500.f:0.f,Dt,bLowPower?45.f:100.f);
    // Horizontal heading is exclusively controlled by the player; no route-driven yaw.
    FlightYaw=FMath::UnwindDegrees(FlightYaw+Steering*28.f*Dt);
    const FVector Forward=FRotator(0,FlightYaw,0).Vector();
    FVector P=OldPosition+Forward*(FlightSpeed*100.f*Dt);
    DistanceMeters=RouteProgress(P,DistanceMeters,FlightSpeed*Dt*1.5f);
    P.Z=RoutePoint(DistanceMeters).Z-PowerHeightLoss;
    SetActorLocation(P);
    const float Pitch=(RoutePoint(FMath::Min(DistanceMeters+12.f,WindRouteControl::RouteLengthMeters))-RoutePoint(FMath::Max(DistanceMeters-3.f,0.f))).Rotation().Pitch;
    SetActorRotation(FRotator(FMath::FInterpTo(GetActorRotation().Pitch,Pitch,Dt,2.5f),FlightYaw,0));
    RouteOffset=FVector::DotProduct(P-RoutePoint(DistanceMeters),RouteRight(DistanceMeters));
    // Resolve the next ring when the aircraft crosses its plane in the forward direction.
    // A miss starts a gentle descent; a later successful ring restores power smoothly.
    if(GatesAttempted<WindRouteControl::GateCount) {
        const int i=GatesAttempted;
        const float d=WindRouteControl::GateDistance(i);
        const FVector center=RoutePoint(d);
        const FVector normal=(RoutePoint(d+5.f)-RoutePoint(d-5.f)).GetSafeNormal();
        if(!bApproachPlayed && FVector::Dist(P,center)<3000.f && FVector::DotProduct(P-center,normal)<0.f) {
            bApproachPlayed=true;
            if(ApproachSound && !bSoundMuted) UGameplayStatics::PlaySound2D(this,ApproachSound,SoundVolume*.9f);
            if(WindSweepSound && !bSoundMuted) UGameplayStatics::PlaySound2D(this,WindSweepSound,SoundVolume*.38f,1.15f);
        }
        const float a=FVector::DotProduct(OldPosition-center,normal), b=FVector::DotProduct(P-center,normal);
        if(a<0.f && b>=0.f && b-a>0.001f) {
            const FVector hit=FMath::Lerp(OldPosition,P,FMath::Clamp(-a/(b-a),0.f,1.f));
            if((hit-center).Size()<=650.f) {
                const bool bWasLowPower=bLowPower;
                CollectedRings[i]=true; ++GatesPassed; ++ConsecutiveGates; GateFeedbackTime=1.8f; BoostTime=2.f; RingSpeedBonus=FMath::Min(MaxRingBonus,RingSpeedBonus+1.5f); RingBoostGrace=5.f; bLowPower=false;
                if(RingSound && !bSoundMuted) UGameplayStatics::PlaySound2D(this,RingSound,SoundVolume*1.2f,1.f+.04f*FMath::Min(ConsecutiveGates-1,4));
                if(WindSweepSound && !bSoundMuted) UGameplayStatics::PlaySound2D(this,WindSweepSound,SoundVolume*.85f,1.3f);
                if(bWasLowPower && RestoreSound && !bSoundMuted) UGameplayStatics::PlaySound2D(this,RestoreSound,SoundVolume*.45f);
            } else { bLowPower=true; BoostTime=0.f; RingSpeedBonus=0.f; RingBoostGrace=0.f; GateFeedbackTime=0.f; ConsecutiveGates=0;
                if(MissSound && !bSoundMuted) UGameplayStatics::PlaySound2D(this,MissSound,SoundVolume*.55f);
            }
            bApproachPlayed=false; ++GatesAttempted; RefreshRingVisuals();
        }
    }
    for(int i=0;i<UE_ARRAY_COUNT(WindZoneDistances);++i) {
        if(WindZonesVisited[i]) continue;
        const float d=WindZoneDistances[i]; const float side=i%2==0?-900.f:900.f;
        const FVector center=RoutePoint(d)+RouteRight(d)*side;
        if(FVector::DistSquared(P,center)<FMath::Square(1200.f)) {
            WindZonesVisited[i]=true; WindZoneTime=2.5f; WindZoneFeedbackTime=2.f;
            if(WindSweepSound && !bSoundMuted) UGameplayStatics::PlaySound2D(this,WindSweepSound,SoundVolume*.85f,1.05f);
        }
    }
    if (DistanceMeters>=WindRouteControl::RouteLengthMeters) { bFinished=true; LateralSpeed=0; }
    // In Unreal, positive roll lowers the right wing (+Y), matching rightward steering.
    for (auto* Mesh : {Wing.Get(),Body.Get(),Tail.Get(),Fin.Get()}) Mesh->SetRelativeRotation(FRotator(Lift*12.f-Dive*12.f,0,Steering*MaxBankDegrees));
    SpringArm->SetRelativeRotation(FMath::RInterpTo(SpringArm->GetRelativeRotation(),FRotator(-10.f,0.f,Steering*18.f),Dt,3.f));
    UpdateTrails(Dt);
    Camera->SetFieldOfView(FMath::FInterpTo(Camera->FieldOfView,58.f+(GateFeedbackTime>0?1.5f:0.f),Dt,3.f));
    if (Steering<-.08f) LeftSteeringTime+=Dt; else if (Steering>.08f) RightSteeringTime+=Dt;
    if (DistanceMeters>=18 && DistanceMeters<=WindRouteControl::RouteLengthMeters-5.f)
    {
        EligibleTime+=Dt;
        if (FMath::Abs(RouteOffset)<=300.f) { GuidedTime+=Dt; CurrentStreak+=Dt; }
        else CurrentStreak=0;
        GuideRatio=GuidedTime/FMath::Max(.01f,EligibleTime);
        BestStreak=FMath::Max(BestStreak,CurrentStreak);
    }
}
