#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "WindRouteGameMode.generated.h"
UCLASS()
class WINDROUTE_API AWindRouteGameMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    AWindRouteGameMode();
    virtual void BeginPlay() override;
};
