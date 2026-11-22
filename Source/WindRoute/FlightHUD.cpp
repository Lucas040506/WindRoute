#include "FlightHUD.h"
#include "FlightPawn.h"
#include "ControlMath.h"
#include "SemgBridgeComponent.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "GameFramework/PlayerController.h"

void AFlightHUD::DrawHUD()
{
    Super::DrawHUD();
    const auto* P=GetOwningPlayerController()?Cast<AFlightPawn>(GetOwningPlayerController()->GetPawn()):nullptr;
    if (!P || !Canvas || !GEngine) return;
    const auto* E=P->Emg.Get();
    UFont* Font=GEngine->GetMediumFont();
    const FLinearColor White=FLinearColor::White, Accent=FLinearColor::Yellow;
    if (P->bCalibrationScreen)
    {
        const float W=Canvas->ClipX, H=Canvas->ClipY;
        const float Scale=FMath::Clamp(W/1280.f,.65f,1.35f);
        const float X=W*.08f, Y=H*.09f;
        DrawRect(FLinearColor(.012f,.025f,.045f,.98f),0,0,W,H);
        DrawText(TEXT("MUSCLE SIGNAL CALIBRATION"),White,X,Y,Font,1.8f*Scale,false);
        DrawText(TEXT("CH2 = LEFT HAND       CH1 = RIGHT HAND"),FLinearColor(.45f,.85f,.90f),X,Y+55*Scale,Font,1.05f*Scale,false);
        FString Heading, Subheading;
        if (!E->CalibrationPhase.IsEmpty())
        {
            Heading=TEXT("RELAX BOTH HANDS"); Subheading=TEXT("Keep your arms still and breathe normally");
            if (E->CalibrationPhase==TEXT("prep_left")) { Heading=TEXT("GET READY: LEFT HAND"); Subheading=TEXT("Keep the right hand relaxed"); }
            else if (E->CalibrationPhase==TEXT("left")) { Heading=TEXT("GENTLY HOLD LEFT HAND"); Subheading=TEXT("Keep the right hand relaxed"); }
            else if (E->CalibrationPhase==TEXT("prep_right")) { Heading=TEXT("GET READY: RIGHT HAND"); Subheading=TEXT("Relax the left hand"); }
            else if (E->CalibrationPhase==TEXT("right")) { Heading=TEXT("GENTLY HOLD RIGHT HAND"); Subheading=TEXT("Keep the left hand relaxed"); }
            else if (E->CalibrationPhase==TEXT("release")) { Heading=TEXT("RELAX BOTH HANDS"); Subheading=TEXT("Almost finished"); }
            DrawText(FString::Printf(TEXT("STEP %d OF 6"),E->CalibrationStep),White,X,Y+125*Scale,Font,1.2f*Scale,false);
            DrawText(Heading,Accent,X,Y+185*Scale,Font,2.0f*Scale,false);
            DrawText(Subheading,White,X,Y+245*Scale,Font,1.1f*Scale,false);
            const float BarW=W*.8f;
            DrawRect(FLinearColor(.13f,.20f,.25f,1),X,Y+315*Scale,BarW,18*Scale);
            DrawRect(FLinearColor(.30f,.85f,.70f,1),X,Y+315*Scale,BarW*E->CalibrationProgress,18*Scale);
            DrawText(TEXT("X: cancel"),White,X,Y+390*Scale,Font,1.0f*Scale,false);
        }
        else if (E->bCalibrationPending)
        {
            DrawText(TEXT("STARTING..."),Accent,X,Y+185*Scale,Font,2.0f*Scale,false);
        }
        else if (E->bCalibrationFailed)
        {
            DrawText(TEXT("CALIBRATION DID NOT PASS"),Accent,X,Y+160*Scale,Font,1.7f*Scale,false);
            DrawText(TEXT("Check electrode contact and relax before trying again."),White,X,Y+225*Scale,Font,1.05f*Scale,false);
            DrawText(TEXT("SPACE: retry      X: exit"),White,X,Y+310*Scale,Font,1.2f*Scale,false);
        }
        else if (E->HasFreshSignal() && !E->bSimulated && E->bCalibrated)
        {
            DrawText(TEXT("CALIBRATION COMPLETE"),FLinearColor(.3f,1.f,.65f),X,Y+160*Scale,Font,1.9f*Scale,false);
            DrawText(P->bResumeRequested?TEXT("Waiting: relax both hands for 0.5 seconds."):TEXT("Press R, then relax both hands to begin."),White,X,Y+230*Scale,Font,1.1f*Scale,false);
            DrawText(FString::Printf(TEXT("Left %.0f%%    Right %.0f%%     (both below 10%% to start)"),E->LeftLevel,E->RightLevel),White,X,Y+270*Scale,Font,1.0f*Scale,false);
            DrawText(TEXT("SPACE: calibrate again      X: exit"),White,X,Y+310*Scale,Font,1.05f*Scale,false);
        }
        else
        {
            DrawText(TEXT("GET READY"),Accent,X,Y+155*Scale,Font,1.9f*Scale,false);
            DrawText(TEXT("Place both electrodes and sit comfortably."),White,X,Y+220*Scale,Font,1.1f*Scale,false);
            DrawText(TEXT("Follow the large instructions for about 16 seconds."),White,X,Y+265*Scale,Font,1.1f*Scale,false);
            if (E->bSimulated || !E->HasRecentSamples()) DrawText(TEXT("Device not ready: exit and press D to connect."),Accent,X,Y+320*Scale,Font,1.0f*Scale,false);
            else DrawText(TEXT("SPACE: start calibration      X: exit"),White,X,Y+325*Scale,Font,1.2f*Scale,false);
        }
        // Show pre-calibration AC RMS in device counts; fixed logarithmic display, never a percentage.
        const float MeterY=H-150.f*Scale, MeterW=W*.64f, MeterH=19.f*Scale;
        const bool bLive=E->HasRecentSamples() && !E->bSimulated;
        DrawText(bLive ? TEXT("LIVE SIGNAL (device counts, log display)") : TEXT("LIVE SIGNAL UNAVAILABLE - check device"),bLive?White:Accent,X,MeterY-32*Scale,Font,.85f*Scale,false);
        const auto DrawMeter=[&](const TCHAR* Label, float Value, float RowY, const FLinearColor& Color)
        {
            const float Fill=bLive?FMath::Clamp(FMath::LogX(10.f,1.f+Value)/3.f,0.f,1.f):0.f;
            DrawText(Label,White,X,RowY,Font,.95f*Scale,false);
            const float BarX=X+165.f*Scale;
            DrawRect(FLinearColor(.13f,.20f,.25f,1),BarX,RowY+3*Scale,MeterW,MeterH);
            DrawRect(Color,BarX,RowY+3*Scale,MeterW*Fill,MeterH);
            const FString Count=bLive?FString::Printf(TEXT("%.1f"),Value):TEXT("--");
            DrawText(Count,White,BarX+MeterW+15*Scale,RowY,Font,.9f*Scale,false);
        };
        DrawMeter(TEXT("LEFT / CH2"),E->LeftRmsCounts,MeterY,FLinearColor(.25f,.8f,.95f));
        DrawMeter(TEXT("RIGHT / CH1"),E->RightRmsCounts,MeterY+42.f*Scale,FLinearColor(.95f,.65f,.25f));
        return;
    }
    if (P->bFinished)
    {
        const float W=Canvas->ClipX, H=Canvas->ClipY;
        const float S=FMath::Clamp(W/1280.f,.7f,1.35f);
        const float X=W*.20f, Y=H*.15f;
        DrawRect(FLinearColor(.015f,.035f,.065f,.94f),X,Y,W*.60f,H*.70f);
        DrawText(TEXT("FLIGHT COMPLETE"),White,X+35*S,Y+28*S,Font,1.8f*S,false);
        DrawText(FString::Printf(TEXT("Rings                 %d / %d"),P->GatesPassed,WindRouteControl::GateCount),Accent,X+35*S,Y+100*S,Font,1.2f*S,false);
        DrawText(FString::Printf(TEXT("On guide path         %.0f%%"),P->GuideRatio*100.f),White,X+35*S,Y+150*S,Font,1.0f*S,false);
        DrawText(FString::Printf(TEXT("Longest path hold     %.1f s"),P->BestStreak),White,X+35*S,Y+195*S,Font,1.0f*S,false);
        DrawText(FString::Printf(TEXT("Steer time  L %.1f s   R %.1f s"),P->LeftSteeringTime,P->RightSteeringTime),White,X+35*S,Y+240*S,Font,1.0f*S,false);
        DrawText(FString::Printf(TEXT("Signal pauses         %d"),P->SignalPauseCount),White,X+35*S,Y+285*S,Font,1.0f*S,false);
        DrawText(P->bResumeRequested?TEXT("Relax both hands to start again"):TEXT("R: fly again    B: mute / unmute"),Accent,X+35*S,Y+360*S,Font,1.0f*S,false);
        return;
    }
    if (P->GateFeedbackTime>0 && !P->bPausedForSignal)
    {
        const float X=Canvas->ClipX*.43f, Y=Canvas->ClipY*.25f;
        DrawText(FString::Printf(TEXT("RING +1    x%d"),P->ConsecutiveGates),Accent,X,Y,Font,1.0f,false);
    }
    if (P->WindZoneFeedbackTime>0 && !P->bPausedForSignal)
        DrawText(TEXT("WIND CURRENT  + SPEED"),Accent,Canvas->ClipX*.40f,Canvas->ClipY*.31f,Font,1.0f,false);
    const int32 Remaining=FMath::CeilToInt(FMath::Max(0.f, WindRouteControl::RouteLengthMeters-P->DistanceMeters)/FMath::Max(1.f,P->FlightSpeed));
    if (!P->bShowDetails)
    {
        DrawRect(FLinearColor(.015f,.035f,.065f,.72f),12,12,410,130);
        DrawText(FString::Printf(TEXT("ETA %02d:%02d    RINGS %d / %d"),Remaining/60,Remaining%60,P->GatesPassed,WindRouteControl::GateCount),White,25,23,Font,.9f,false);
        const TCHAR* Status=P->bFinished?TEXT("FINISHED - R to restart"):
            P->bResumeRequested?TEXT("WAIT - relax both hands"):
            P->bPausedForSignal?(P->bUsingEmg?TEXT("PAUSED - press H for details"):TEXT("PRESS R TO START")):
            P->bLowPower?TEXT("RING MISSED - LOSING POWER"):
            P->GateFeedbackTime>0?TEXT("RING PASSED!"):

            P->bUsingEmg?TEXT("EMG ACTIVE"):TEXT("KEYBOARD MODE");
        DrawText(Status, P->bPausedForSignal||P->bFinished||P->bLowPower?Accent:White,25,55,Font,.7f,false);
        DrawText(FString::Printf(TEXT("%s | %.1f m/s | height %.1f m"),TEXT("FREE STEERING / AUTO HEIGHT"),P->FlightSpeed,P->GetActorLocation().Z/100.f),White,25,82,Font,.65f,false);
        DrawText(TEXT("H: controls  |  B: sound on/off"),White,25,107,Font,.6f,false);
        return;
    }
    DrawRect(FLinearColor(.015f,.035f,.065f,.88f),12,12,650,320);
    DrawText(TEXT("WIND ROUTE - EMG PROTOTYPE"),White,25,22,Font,.9f,false);
    DrawText(FString::Printf(TEXT("ETA %02d:%02d   Rings %d/%d   Guide %.0f%%  %s %.1f m/s"),Remaining/60,Remaining%60,P->GatesPassed,WindRouteControl::GateCount,P->GuideRatio*100.f,TEXT("FREE STEERING / AUTO HEIGHT"),P->FlightSpeed),White,25,50,Font,.7f,false);
    DrawText(TEXT("Left/Right: steer | E: EMG | R: resume | T: restart"),White,25,75,Font,.65f,false);
    DrawText(TEXT("P: port | D: connect | C: calibrate | M: simulator | H: hide"),White,25,99,Font,.65f,false);
    FString Port=E->AvailablePorts.IsValidIndex(P->SelectedPortIndex)?E->AvailablePorts[P->SelectedPortIndex]:TEXT("No ports (P to refresh)");
    DrawText(FString::Printf(TEXT("Selected: %s"),*Port),White,25,127,Font,.65f,false);
    const TCHAR* Source=E->bSourceChangePending?TEXT("switching"):E->bSimulated?TEXT("SIMULATOR"):TEXT("DEVICE");
    const TCHAR* Signal=E->HasRecentSamples()?TEXT("receiving"):TEXT("no fresh samples");
    DrawText(FString::Printf(TEXT("Source: %s | Signal: %s | Calibration: %s"),Source,Signal,E->bCalibrated?TEXT("ready"):TEXT("required")),White,25,152,Font,.65f,false);
    if (!E->CalibrationPhase.IsEmpty())
    {
        const float PanelW=FMath::Min(900.f,Canvas->ClipX-40.f);
        const float X=(Canvas->ClipX-PanelW)*.5f;
        const float Y=Canvas->ClipY*.55f;
        DrawRect(FLinearColor(.01f,.025f,.045f,.96f),X,Y,PanelW,150.f);
        FString Instruction=TEXT("Relax both sides");
        if (E->CalibrationPhase==TEXT("prep_left")) Instruction=TEXT("Prepare LEFT contraction");
        else if (E->CalibrationPhase==TEXT("left")) Instruction=TEXT("Gently hold LEFT only");
        else if (E->CalibrationPhase==TEXT("prep_right")) Instruction=TEXT("Relax; prepare RIGHT contraction");
        else if (E->CalibrationPhase==TEXT("right")) Instruction=TEXT("Gently hold RIGHT only");
        DrawText(FString::Printf(TEXT("CALIBRATION %d / 6"),E->CalibrationStep),White,X+24,Y+15,Font,1.1f,false);
        DrawText(Instruction,Accent,X+24,Y+52,Font,1.6f,false);
        DrawRect(FLinearColor(.15f,.2f,.25f,1.f),X+24,Y+118,PanelW-48,12.f);
        DrawRect(FLinearColor(.3f,.9f,.7f,1.f),X+24,Y+118,(PanelW-48)*E->CalibrationProgress,12.f);
    }
    else if (E->bCalibrationPending) DrawText(TEXT("Starting calibration..."),Accent,25,181,Font,.7f,false);
    else if (E->bCalibrationFailed) DrawText(TEXT("Calibration failed - check electrodes and press C"),Accent,25,181,Font,.7f,false);
    else if (P->bResumeRequested) DrawText(TEXT("WAITING: relax both hands to start the next run"),Accent,25,181,Font,.7f,false);
    else if (P->bFinished) DrawText(TEXT("ROUTE COMPLETE - Press R, then relax both hands"),Accent,25,181,Font,.7f,false);
    else if (P->bPausedForSignal)
    {
        const TCHAR* Reason=!E->HasRecentSamples()?TEXT("NO LIVE DEVICE SIGNAL - press D to reconnect"):
            !E->bCalibrated?TEXT("CALIBRATION REQUIRED - press C"):
            (E->LeftLevel>=10 || E->RightLevel>=10)?TEXT("Press R, then relax both hands to resume"):
            TEXT("READY - press R to resume");
        DrawText(Reason,Accent,25,181,Font,.7f,false);
    }
    else DrawText(TEXT("F/J: simulate channels (simulator only)"),White,25,181,Font,.65f,false);
    if (E->bCalibrated) DrawText(FString::Printf(TEXT("Mode: %s | Left %.0f%%  Right %.0f%%"),P->bUsingEmg?TEXT("EMG"):TEXT("Keyboard"),E->LeftLevel,E->RightLevel),White,25,210,Font,.7f,false);
    else DrawText(TEXT("Attach electrodes before pressing C to calibrate."),White,25,210,Font,.65f,false);
    const float Input=FMath::Clamp(E->GetSteering()*P->Sensitivity,-1.f,1.f);
    const TCHAR* Direction=Input<-.001f?TEXT("LEFT"):Input>.001f?TEXT("RIGHT"):TEXT("NEUTRAL");
    DrawText(FString::Printf(TEXT("EMG steering: %s %.0f%% | %s"),Direction,FMath::Abs(Input)*100,P->bUsingEmg?TEXT("EMG MODE"):TEXT("KEYBOARD MODE")),White,25,239,Font,.65f,false);
    DrawText(FString::Printf(TEXT("Sensitivity %.1fx [ / ]  |  Sound %s %.0f%%  B / 9 / 0"),P->Sensitivity,P->bSoundMuted?TEXT("OFF"):TEXT("ON"),P->SoundVolume*100.f),White,25,264,Font,.65f,false);
    DrawText(FString::Printf(TEXT("Frame %.1f ms (average) | signal pauses %d"),P->FrameTimeMs,P->SignalPauseCount),White,25,290,Font,.65f,false);
}
