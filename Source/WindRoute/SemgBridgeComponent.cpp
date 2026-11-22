#include "SemgBridgeComponent.h"
#include "ControlMath.h"
#include "WebSocketsModule.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "HAL/PlatformTime.h"

USemgBridgeComponent::USemgBridgeComponent() { PrimaryComponentTick.bCanEverTick = true; }
void USemgBridgeComponent::BeginPlay() { Super::BeginPlay(); Connect(); }
void USemgBridgeComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    if (Socket.IsValid()) { Socket->OnMessage().RemoveAll(this); Socket->OnConnected().RemoveAll(this); Socket->OnClosed().RemoveAll(this); Socket->OnConnectionError().RemoveAll(this); Socket->Close(); Socket.Reset(); }
    Super::EndPlay(Reason);
}
void USemgBridgeComponent::TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* TickFunction)
{
    Super::TickComponent(DeltaTime, TickType, TickFunction);
    if (!bConnected && FPlatformTime::Seconds() - LastConnectAttempt > 3.0) Connect();
}
void USemgBridgeComponent::Connect()
{
    LastConnectAttempt = FPlatformTime::Seconds();
    if (Socket.IsValid()) { Socket->OnMessage().RemoveAll(this); Socket->OnConnected().RemoveAll(this); Socket->OnClosed().RemoveAll(this); Socket->OnConnectionError().RemoveAll(this); Socket->Close(); Socket.Reset(); }
    Socket = FWebSocketsModule::Get().CreateWebSocket(TEXT("ws://127.0.0.1:8896"));
    Socket->OnConnected().AddUObject(this, &USemgBridgeComponent::OnConnected);
    Socket->OnClosed().AddUObject(this, &USemgBridgeComponent::OnClosed);
    Socket->OnConnectionError().AddUObject(this, &USemgBridgeComponent::OnError);
    Socket->OnMessage().AddUObject(this, &USemgBridgeComponent::OnMessage);
    Socket->Connect();
}
void USemgBridgeComponent::OnConnected() { bConnected = true; Status = TEXT("服务已连接，等待信号"); RequestPorts(); }
void USemgBridgeComponent::OnClosed(int32, const FString&, bool) { bConnected = false; bSignalOk = false; Status = TEXT("肌电服务已断开"); }
void USemgBridgeComponent::OnError(const FString& Error) { bConnected = false; bSignalOk = false; Status = Error; }
void USemgBridgeComponent::OnMessage(const FString& Message)
{
    TSharedPtr<FJsonObject> Json;
    const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Message);
    if (!FJsonSerializer::Deserialize(Reader, Json) || !Json.IsValid()) return;
    FString Type; Json->TryGetStringField(TEXT("type"), Type);
    if (Type == TEXT("device_lost")) { bCalibrationPending=false; bSignalOk = false; bCalibrated=false; bRequiresReconnect=true; LastSampleTime=0; Status = TEXT("设备信号中断，请重新连接和校准"); return; }
    if (Type == TEXT("source_changed")) { bCalibrationPending=false; bCalibrationFailed=false; bSourceChangePending=false; LastSampleTime=0; LastSampleValue=-1; return; }
    if (Type == TEXT("error")) { bCalibrationPending=false; bSourceChangePending=false; bRequiresReconnect=true; Json->TryGetStringField(TEXT("message"), Status); return; }
    if (Type == TEXT("calibrated")) { bool Ok=false; Json->TryGetBoolField(TEXT("ok"), Ok); bCalibrationFailed=!Ok; bCalibrationPending=false; return; }
    if (Type == TEXT("hello") || Type == TEXT("ports"))
    {
        const TArray<TSharedPtr<FJsonValue>>* Ports = nullptr;
        if (Json->TryGetArrayField(TEXT("ports"), Ports))
        {
            AvailablePorts.Reset();
            for (const auto& Value : *Ports) { const auto Item = Value->AsObject(); FString Path; if (Item.IsValid() && Item->TryGetStringField(TEXT("device"), Path)) AvailablePorts.Add(Path); }
        }
    }
    if (Type != TEXT("state") && Type != TEXT("hello")) return;
    Json->TryGetBoolField(TEXT("signal_ok"), bSignalOk);
    Json->TryGetBoolField(TEXT("calibrated"), bCalibrated);
    Json->TryGetBoolField(TEXT("simulated"), bSimulated);
    Json->TryGetStringField(TEXT("status"), Status);
    Json->TryGetStringField(TEXT("source_name"), SourceName);
    CalibrationPhase.Empty(); CalibrationProgress=0; CalibrationStep=0;
    const TSharedPtr<FJsonObject>* Cal = nullptr;
    if (Json->TryGetObjectField(TEXT("calibration"), Cal) && Cal && Cal->IsValid())
    {
        (*Cal)->TryGetStringField(TEXT("phase"), CalibrationPhase);
        bCalibrationPending=false;
        double Progress=0, Step=0; (*Cal)->TryGetNumberField(TEXT("progress"), Progress); (*Cal)->TryGetNumberField(TEXT("step"), Step);
        CalibrationProgress=FMath::Clamp(static_cast<float>(Progress),0.f,1.f); CalibrationStep=static_cast<int32>(Step);
    }
    double Sample = -1;
    if (Json->TryGetNumberField(TEXT("sample_t"), Sample) && Sample != LastSampleValue) { LastSampleValue = Sample; LastSampleTime = FPlatformTime::Seconds(); }
    const TArray<TSharedPtr<FJsonValue>>* Rms = nullptr;
    if (Json->TryGetArrayField(TEXT("rms_counts"), Rms) && Rms->Num() >= 2) { LeftRmsCounts=FMath::Max(0.0, (*Rms)[0]->AsNumber()); RightRmsCounts=FMath::Max(0.0, (*Rms)[1]->AsNumber()); }
    const TArray<TSharedPtr<FJsonValue>>* Levels = nullptr;
    if (Json->TryGetArrayField(TEXT("levels"), Levels) && Levels->Num() >= 2) { LeftLevel = (*Levels)[0]->AsNumber(); RightLevel = (*Levels)[1]->AsNumber(); }
}
bool USemgBridgeComponent::HasRecentSamples() const { return bConnected && bSignalOk && !bSourceChangePending && !bRequiresReconnect && LastSampleTime > 0 && FPlatformTime::Seconds()-LastSampleTime < StaleSeconds; }
bool USemgBridgeComponent::HasFreshSignal() const { return HasRecentSamples() && bCalibrated && !bCalibrationPending && CalibrationPhase.IsEmpty(); }
float USemgBridgeComponent::GetSteering() const
{
    if (!HasFreshSignal()) return 0;
    return WindRouteControl::Steering(LeftLevel, RightLevel);
}
void USemgBridgeComponent::SendJson(const TSharedRef<FJsonObject>& Data)
{
    if (!Socket.IsValid() || !bConnected) return;
    FString Message; const auto Writer=TJsonWriterFactory<>::Create(&Message); FJsonSerializer::Serialize(Data, Writer); Socket->Send(Message);
}
void USemgBridgeComponent::RequestPorts() { auto J=MakeShared<FJsonObject>(); J->SetStringField(TEXT("type"),TEXT("ports")); SendJson(J); }
void USemgBridgeComponent::ConnectDevice(const FString& SerialPath) { if (SerialPath.IsEmpty() || !bConnected) return; bSignalOk=false; bCalibrated=false; bSourceChangePending=true; bRequiresReconnect=false; LastSampleTime=0; auto J=MakeShared<FJsonObject>(); J->SetStringField(TEXT("type"),TEXT("source")); J->SetStringField(TEXT("source"),TEXT("device")); J->SetStringField(TEXT("path"),SerialPath); SendJson(J); }
void USemgBridgeComponent::UseSimulator() { if (!bConnected) return; bSignalOk=false; bCalibrated=false; bSourceChangePending=true; bRequiresReconnect=false; LastSampleTime=0; auto J=MakeShared<FJsonObject>(); J->SetStringField(TEXT("type"),TEXT("source")); J->SetStringField(TEXT("source"),TEXT("simulate")); SendJson(J); }
void USemgBridgeComponent::RequestCalibration() { if (bSimulated || !HasRecentSamples() || !CalibrationPhase.IsEmpty()) return; bCalibrated=false; bCalibrationPending=true; bCalibrationFailed=false; auto J=MakeShared<FJsonObject>(); J->SetStringField(TEXT("type"),TEXT("calibrate")); SendJson(J); }
void USemgBridgeComponent::CancelCalibration() { if (!bConnected) return; bCalibrationPending=false; bCalibrated=false; auto J=MakeShared<FJsonObject>(); J->SetStringField(TEXT("type"),TEXT("cancel_calibration")); SendJson(J); }
void USemgBridgeComponent::SetSimulatedLevels(float Left,float Right)
{
    if (!bSimulated || !HasFreshSignal()) return;
    auto J=MakeShared<FJsonObject>(); J->SetStringField(TEXT("type"),TEXT("sim")); TArray<TSharedPtr<FJsonValue>> Values;
    Values.Add(MakeShared<FJsonValueNumber>(FMath::Clamp(Left,0.f,100.f))); Values.Add(MakeShared<FJsonValueNumber>(FMath::Clamp(Right,0.f,100.f))); J->SetArrayField(TEXT("levels"),Values); SendJson(J);
}
