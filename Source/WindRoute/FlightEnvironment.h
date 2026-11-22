#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "FlightEnvironment.generated.h"

UCLASS()
class WINDROUTE_API AFlightEnvironment : public AActor
{
    GENERATED_BODY()
public:
    AFlightEnvironment();
    virtual void BeginPlay() override;
private:
    UPROPERTY() TObjectPtr<class USceneComponent> SceneRoot;
    UPROPERTY() TObjectPtr<class UProceduralMeshComponent> Terrain;
    UPROPERTY() TObjectPtr<class UProceduralMeshComponent> River;
    UPROPERTY() TObjectPtr<class UProceduralMeshComponent> GateMesh;
    UPROPERTY() TObjectPtr<class UProceduralMeshComponent> MountainMesh;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> Rocks;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> Ground;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> Banks;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> Trunks;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> Hills;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> Trees;
    UPROPERTY() TObjectPtr<class UInstancedStaticMeshComponent> Guide;
    UPROPERTY() TObjectPtr<class UDirectionalLightComponent> Sun;
    UPROPERTY() TObjectPtr<class USkyLightComponent> Sky;
    UPROPERTY() TObjectPtr<class USkyAtmosphereComponent> Atmosphere;
    UPROPERTY() TObjectPtr<class UExponentialHeightFogComponent> Fog;
};
