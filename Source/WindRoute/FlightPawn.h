#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "ControlMath.h"
#include "FlightPawn.generated.h"

class UCameraComponent;
class USpringArmComponent;
class UStaticMeshComponent;
class USemgBridgeComponent;

UCLASS()
class WINDROUTE_API AFlightPawn : public APawn
{
    GENERATED_BODY()
public:
    AFlightPawn();
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="sEMG") TObjectPtr<USemgBridgeComponent> Emg;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float DistanceMeters = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float Steering = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float Lift = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float Dive = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bDiveArmed = false;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bGlideMode = true;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float FlightSpeed = 8.f;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float VerticalSpeed = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float FrameTimeMs = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bLiftActive = false;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float Sensitivity = 1.f;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float GuideRatio = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") int32 GatesPassed = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") int32 GatesAttempted = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float GateFeedbackTime = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bLowPower = false;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float WindZoneFeedbackTime = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float PowerHeightLoss = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bShowDetails = false;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float CurrentStreak = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float BestStreak = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float LeftSteeringTime = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") float RightSteeringTime = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") int32 ConsecutiveGates = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") int32 SignalPauseCount = 0;
    UPROPERTY(BlueprintReadOnly, Category="Audio") bool bSoundMuted = false;
    UPROPERTY(BlueprintReadOnly, Category="Audio") float SoundVolume = .7f;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bCalibrationScreen = false;
    UPROPERTY(BlueprintReadOnly, Category="Flight") int32 SelectedPortIndex = 0;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bResumeRequested = false;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bFinished = false;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bUsingEmg = false;
    UPROPERTY(BlueprintReadOnly, Category="Flight") bool bPausedForSignal = false;
    UFUNCTION(BlueprintCallable, Category="Flight") void SetUseEmg(bool bEnable);
    UFUNCTION(BlueprintCallable, Category="Flight") void ResumeFlight();
    UFUNCTION(BlueprintPure, Category="Flight") static float GuidePosition(float Distance);
private:
    UPROPERTY() TObjectPtr<USceneComponent> Pivot;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Body;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Wing;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Tail;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Fin;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> WingTrails;
    TArray<FVector> LeftTrailPoints, RightTrailPoints;
    float TrailClock = 0.f;
    void UpdateTrails(float DeltaTime);
    void ResetTrails();
    UPROPERTY() TObjectPtr<class UAudioComponent> WindAudio;
    UPROPERTY() TObjectPtr<class USoundBase> RingSound;
    UPROPERTY() TObjectPtr<class USoundBase> ApproachSound;
    UPROPERTY() TObjectPtr<class USoundBase> WindSweepSound;
    UPROPERTY() TObjectPtr<class USoundBase> MissSound;
    UPROPERTY() TObjectPtr<class USoundBase> RestoreSound;
    UPROPERTY() TObjectPtr<class UAudioComponent> MusicAudio;
    float MusicCurrentVolume = 0.f;
    bool bApproachPlayed = false;
    float WindCurrentVolume = 0.f;
    void ToggleSound();
    void Louder();
    void Quieter();
    void UpdateWind(float DeltaTime);
    UPROPERTY() TObjectPtr<USpringArmComponent> SpringArm;
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
    float KeyboardAxis = 0, LateralSpeed = 0, GuidedTime = 0, EligibleTime = 0, ReleaseHoldTime = 0;
    float SimulatorLeft = 0, SimulatorRight = 0;
    float RouteOffset = 0, BoostTime = 0;
    float RingSpeedBonus = 0.f, RingBoostGrace = 0.f;
    void RefreshRingVisuals();
    float FlightYaw = 0;
    TArray<bool> CollectedRings;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> CanyonRings;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> WindRibbons;
    TArray<bool> WindZonesVisited;
    float WindZoneTime = 0.f, WindRibbonClock = 0.f, WindRibbonAge = 0.f;
    void UpdateWindRibbons(float DeltaTime);
    float KeyboardLift = 0, KeyboardDive = 0, HeightOffset = 0;
    WindRouteControl::GestureState Gesture;
    void LiftInput(float Value);
    void DiveInput(float Value);
    void ToggleFlightMode();
    void Steer(float Value);
    void ToggleEmg();
    void ToggleDetails();
    void IncreaseSensitivity();
    void DecreaseSensitivity();
    void NextPort();
    void ConnectSelectedDevice();
    void OpenCalibration();
    void StartCalibration();
    void CloseCalibration();
    void SwitchToSimulator();
    void RestartFlight();
    void ResetRoute();
    void SimulatorLeftOn();
    void SimulatorLeftOff();
    void SimulatorRightOn();
    void SimulatorRightOff();
    void SendSimulator();
};
