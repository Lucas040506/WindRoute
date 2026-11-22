#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "IWebSocket.h"
#include "SemgBridgeComponent.generated.h"

/** Local-only sEMG bridge. Hardware mode never falls back to simulation. */
UCLASS(ClassGroup=(Input), meta=(BlueprintSpawnableComponent))
class WINDROUTE_API USemgBridgeComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    USemgBridgeComponent();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction) override;

    UFUNCTION(BlueprintPure, Category="sEMG") bool HasFreshSignal() const;
    UFUNCTION(BlueprintPure, Category="sEMG") bool HasRecentSamples() const;
    UFUNCTION(BlueprintPure, Category="sEMG") float GetSteering() const;
    UFUNCTION(BlueprintCallable, Category="sEMG") void RequestPorts();
    UFUNCTION(BlueprintCallable, Category="sEMG") void ConnectDevice(const FString& SerialPath);
    UFUNCTION(BlueprintCallable, Category="sEMG") void UseSimulator();
    UFUNCTION(BlueprintCallable, Category="sEMG") void RequestCalibration();
    UFUNCTION(BlueprintCallable, Category="sEMG") void CancelCalibration();
    UFUNCTION(BlueprintCallable, Category="sEMG") void SetSimulatedLevels(float Left, float Right);

    UPROPERTY(BlueprintReadOnly, Category="sEMG") bool bConnected = false;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") bool bCalibrated = false;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") bool bSignalOk = false;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") bool bSimulated = true;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") float LeftLevel = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") float RightLevel = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") float LeftRmsCounts = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") float RightRmsCounts = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") FString Status;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") FString SourceName;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") FString CalibrationPhase;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") float CalibrationProgress = 0.f;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") int32 CalibrationStep = 0;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") bool bSourceChangePending = false;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") bool bCalibrationPending = false;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") bool bCalibrationFailed = false;
    UPROPERTY(BlueprintReadOnly, Category="sEMG") TArray<FString> AvailablePorts;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="sEMG") float StaleSeconds = .65f;
private:
    TSharedPtr<IWebSocket> Socket;
    bool bRequiresReconnect = false;
    double LastSampleTime = 0;
    double LastSampleValue = -1;
    double LastConnectAttempt = 0;
    void Connect();
    void SendJson(const TSharedRef<class FJsonObject>& Data);
    void OnMessage(const FString& Message);
    void OnConnected();
    void OnClosed(int32 Code, const FString& Reason, bool bClean);
    void OnError(const FString& Error);
};
