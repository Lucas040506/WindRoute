#pragma once
#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "FlightHUD.generated.h"
UCLASS()
class WINDROUTE_API AFlightHUD : public AHUD
{
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
    virtual void NotifyHitBoxClick(FName BoxName) override;
private:
    UPROPERTY() TObjectPtr<class UFont> MenuChineseFont;
    TArray<float> LeftHistory, RightHistory;
    double LastHistoryTime = 0.0;
    float DisplayLeft = 0.f, DisplayRight = 0.f;
    bool bPreviousLive = false, bPreviousSimulated = true;
};
