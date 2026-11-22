#include "WindRouteGameMode.h"
#include "FlightPawn.h"
#include "FlightHUD.h"
#include "FlightEnvironment.h"
#include "Engine/World.h"
AWindRouteGameMode::AWindRouteGameMode() { DefaultPawnClass=AFlightPawn::StaticClass();HUDClass=AFlightHUD::StaticClass(); }
void AWindRouteGameMode::BeginPlay()
{
    Super::BeginPlay();
    // Scene is provided by the imported canyon level.
}
