#include "FlightHUD.h"
#include "FlightPawn.h"
#include "ControlMath.h"
#include "SemgBridgeComponent.h"
#include "Engine/Canvas.h"
#include "CanvasItem.h"
#include "Engine/Font.h"
#include "Misc/Paths.h"
#include "GlobalRenderResources.h"
#include "Engine/Engine.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformTime.h"

namespace
{
const FName MenuButtons[] = {TEXT("Play"), TEXT("Training"), TEXT("Calibration")};

FLinearColor TrainingColor(int32 Segment)
{
    if (Segment == 0) return FLinearColor(.14f,.94f,1.f);
    if (Segment == 2) return FLinearColor(1.f,.68f,.22f);
    return FLinearColor(.85f,.94f,1.f);
}

void DrawRoundedRect(UCanvas& Canvas, float X, float Y, float Width, float Height,
                     float Radius, const FLinearColor& Color)
{
    if (Width <= 0.f || Height <= 0.f) return;
    const float R = FMath::Min3(Radius, Width * .5f, Height * .5f);
    const FVector2D Center(X + Width * .5f, Y + Height * .5f);
    const FVector2D Corners[] = {{X + Width - R, Y + Height - R}, {X + R, Y + Height - R},
                                 {X + R, Y + R}, {X + Width - R, Y + R}};
    constexpr int32 Steps = 5;
    TArray<FCanvasUVTri> Triangles;
    Triangles.Reserve(4 * (Steps + 1));
    const auto Point = [&](int32 Corner, int32 Step)
    {
        const float Angle = (Corner + float(Step) / Steps) * UE_HALF_PI;
        return Corners[Corner] + FVector2D(FMath::Cos(Angle), FMath::Sin(Angle)) * R;
    };
    FVector2D Previous = Point(3, Steps);
    for (int32 Corner = 0; Corner < 4; ++Corner)
    {
        for (int32 Step = 0; Step <= Steps; ++Step)
        {
            const FVector2D Next = Point(Corner, Step);
            FCanvasUVTri& Tri = Triangles.AddDefaulted_GetRef();
            Tri.V0_Pos = Center;
            Tri.V1_Pos = Previous;
            Tri.V2_Pos = Next;
            Tri.V0_UV = Tri.V1_UV = Tri.V2_UV = FVector2D::ZeroVector;
            Tri.V0_Color = Tri.V1_Color = Tri.V2_Color = Color;
            Previous = Next;
        }
    }
    FCanvasTriangleItem Item(Triangles, GWhiteTexture);
    Item.BlendMode = SE_BLEND_Translucent;
    Canvas.DrawItem(Item);
}
}

void AFlightHUD::NotifyHitBoxClick(FName BoxName)
{
    Super::NotifyHitBoxClick(BoxName);
    if (auto* PC = GetOwningPlayerController())
        if (auto* Pawn = Cast<AFlightPawn>(PC->GetPawn()))
            for (int32 Index = 0; Index < UE_ARRAY_COUNT(MenuButtons); ++Index)
                if (BoxName == MenuButtons[Index]) Pawn->SelectMenu(Index);
}

void AFlightHUD::DrawHUD()
{
    Super::DrawHUD();
    const auto* P=GetOwningPlayerController()?Cast<AFlightPawn>(GetOwningPlayerController()->GetPawn()):nullptr;
    if (!P || !Canvas || !GEngine) return;
    const auto* E=P->Emg.Get();
    UFont* Font=GEngine->GetMediumFont();
    const FLinearColor White=FLinearColor::White, Accent=FLinearColor::Yellow;
    if (P->bMainMenu && !P->bCalibrationScreen)
    {
        const float W = Canvas->ClipX, H = Canvas->ClipY;
        const float S = FMath::Min(W / 1280.f, H / 720.f);
        const float Center = W * .5f;
        if (!MenuChineseFont)
        {
            MenuChineseFont = NewObject<UFont>(this);
            MenuChineseFont->FontCacheType = EFontCacheType::Runtime;
            MenuChineseFont->GetMutableInternalCompositeFont() = FCompositeFont(
                TEXT("Regular"), FPaths::EngineContentDir() / TEXT("Slate/Fonts/DroidSansFallback.ttf"),
                EFontHinting::Default, EFontLoadingPolicy::LazyLoad);
        }
        const auto CenterText = [&](const TCHAR* Label, float Y, float Size, UFont* Face, const FLinearColor& Color)
        {
            float TW = 0.f, TH = 0.f;
            GetTextSize(Label, TW, TH, Face, Size*S);
            DrawText(Label, Color, Center-TW*.5f, Y, Face, Size*S, false);
        };
        DrawRect(FLinearColor(.008f,.022f,.038f,.30f), 0, 0, W, H);
        CenterText(TEXT("SEMG Glider Travel"), H*.16f, 2.8f, Font, White);
        DrawLine(Center - 34*S, H*.28f, Center + 34*S, H*.28f, FLinearColor(.14f,.92f,.98f), 2*S);

        const TCHAR* Labels[] = {TEXT("游玩模式"), TEXT("肌肉训练模式"), TEXT("肌电信号校准")};
        const float ButtonWidth = 420.f * S, ButtonHeight = 66.f * S;
        const float X = Center - ButtonWidth * .5f;
        float CursorX = 0.f, CursorY = 0.f;
        const bool bCursor = GetOwningPlayerController()->GetMousePosition(CursorX, CursorY);
        for (int32 Index = 0; Index < UE_ARRAY_COUNT(MenuButtons); ++Index)
        {
            const float Y = H * .36f + Index * 83.f * S;
            const bool bFocused = Index == P->MenuSelection;
            const bool bHovered = bCursor && CursorX >= X && CursorX <= X + ButtonWidth &&
                                  CursorY >= Y && CursorY <= Y + ButtonHeight;
            const FLinearColor Border = bFocused || bHovered ? FLinearColor(.12f,.9f,.96f)
                                                               : FLinearColor(.45f,.57f,.65f,.70f);
            const float Edge = (bFocused || bHovered ? 2.f : 1.f) * S;
            DrawRoundedRect(*Canvas, X, Y + 3*S, ButtonWidth, ButtonHeight, 14*S, FLinearColor(0,0,0,.24f));
            DrawRoundedRect(*Canvas, X, Y, ButtonWidth, ButtonHeight, 14*S, Border);
            DrawRoundedRect(*Canvas, X+Edge, Y+Edge, ButtonWidth-2*Edge, ButtonHeight-2*Edge,
                            13*S, FLinearColor(.018f,.038f,.062f,.94f));
            CenterText(Labels[Index], Y + 17*S, 1.55f, MenuChineseFont, White);
            AddHitBox({X, Y}, {ButtonWidth, ButtonHeight}, MenuButtons[Index], true);
        }
        CenterText(TEXT("UP / DOWN   /   ENTER"), H*.79f, .8f, Font,
                     FLinearColor(.88f,.94f,.98f));
        return;
    }
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
            DrawText(P->bMainMenu?TEXT("Calibration is ready for your next flight."):P->bResumeRequested?TEXT("Waiting: relax both hands for 0.5 seconds."):TEXT("Press R, then relax both hands to begin."),White,X,Y+230*Scale,Font,1.1f*Scale,false);
            DrawText(FString::Printf(TEXT("Left %.0f%%    Right %.0f%%     (both below 10%% to start)"),E->LeftLevel,E->RightLevel),White,X,Y+270*Scale,Font,1.0f*Scale,false);
            DrawText(P->bMainMenu ? TEXT("R: return to menu   SPACE: recalibrate") : TEXT("SPACE: calibrate again      X: exit"),White,X,Y+310*Scale,Font,1.05f*Scale,false);
        }
        else
        {
            DrawText(TEXT("GET READY"),Accent,X,Y+155*Scale,Font,1.9f*Scale,false);
            DrawText(TEXT("Place both electrodes and sit comfortably."),White,X,Y+220*Scale,Font,1.1f*Scale,false);
            DrawText(TEXT("Follow the large instructions for about 16 seconds."),White,X,Y+265*Scale,Font,1.1f*Scale,false);
            if (E->bSimulated || !E->HasRecentSamples()) DrawText(TEXT("P: select serial port   D: connect   X: exit"),Accent,X,Y+320*Scale,Font,1.0f*Scale,false);
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
    if (P->bFinished && P->bTraining)
    {
        const float W = Canvas->ClipX, H = Canvas->ClipY;
        const float S = FMath::Min(W / 1280.f, H / 720.f);
        const float X = W * .5f - 312*S, Y = H * .5f - 174*S;
        DrawRoundedRect(*Canvas, X, Y, 624*S, 348*S, 16*S, FLinearColor(.016f,.033f,.056f,.95f));
        DrawText(TEXT("TRAINING COMPLETE"), White, X+30*S, Y+23*S, Font, 1.6f*S, false);
        DrawText(FString::Printf(TEXT("RINGS  %d / %d   |   SIGNAL PAUSES  %d"),
                                P->GatesPassed, P->GetGateCount(), P->SignalPauseCount),
                 White, X+30*S, Y+69*S, Font, .9f*S, false);
        DrawText(TEXT("ACTION"), White, X+30*S, Y+111*S, Font, .8f*S, false);
        DrawText(TEXT("IN CORRIDOR"), White, X+258*S, Y+111*S, Font, .8f*S, false);
        DrawText(TEXT("STEERING MATCH"), White, X+423*S, Y+111*S, Font, .8f*S, false);
        const auto& Results = P->GetTrainingResults();
        for (int32 I = 0; I < Results.Num(); ++I)
        {
            const auto& Row = Results[I];
            const float LineY = Y + (146 + I * 34)*S;
            DrawText(FString::Printf(TEXT("%d   %s"), I+1, WindRouteTraining::SegmentNames[I]),
                     TrainingColor(I), X+30*S, LineY, Font, .9f*S, false);
            DrawText(FString::Printf(TEXT("%.0f%%"), 100.f * Row.InsideSeconds / FMath::Max(Row.Seconds, .001f)),
                     White, X+258*S, LineY, Font, .9f*S, false);
            DrawText(FString::Printf(TEXT("%.1f / %.1f s"), Row.SteeringMatchSeconds, Row.Seconds),
                     White, X+423*S, LineY, Font, .9f*S, false);
        }
        DrawText(P->bResumeRequested ? TEXT("Relax both hands to restart") : TEXT("R  FLY AGAIN     BACKSPACE  MAIN MENU"),
                 Accent, X+30*S, Y+303*S, Font, .9f*S, false);
        return;
    }
    if (P->bFinished)
    {
        const float W=Canvas->ClipX, H=Canvas->ClipY;
        const float S=FMath::Clamp(W/1280.f,.7f,1.35f);
        const float X=W*.20f, Y=H*.15f;
        DrawRect(FLinearColor(.015f,.035f,.065f,.94f),X,Y,W*.60f,H*.70f);
        DrawText(TEXT("FLIGHT COMPLETE"),White,X+35*S,Y+28*S,Font,1.8f*S,false);
        DrawText(FString::Printf(TEXT("Rings                 %d / %d"),P->GatesPassed,P->GetGateCount()),Accent,X+35*S,Y+100*S,Font,1.2f*S,false);
        DrawText(FString::Printf(TEXT("On guide path         %.0f%%"),P->GuideRatio*100.f),White,X+35*S,Y+150*S,Font,1.0f*S,false);
        DrawText(FString::Printf(TEXT("Longest path hold     %.1f s"),P->BestStreak),White,X+35*S,Y+195*S,Font,1.0f*S,false);
        DrawText(FString::Printf(TEXT("Steer time  L %.1f s   R %.1f s"),P->LeftSteeringTime,P->RightSteeringTime),White,X+35*S,Y+240*S,Font,1.0f*S,false);
        DrawText(FString::Printf(TEXT("Signal pauses         %d"),P->SignalPauseCount),White,X+35*S,Y+285*S,Font,1.0f*S,false);
        DrawText(P->bResumeRequested?TEXT("Relax both hands to start again"):TEXT("R: fly again    BACKSPACE: main menu    B: sound"),Accent,X+35*S,Y+360*S,Font,1.0f*S,false);
        return;
    }
    if (P->bTraining)
    {
        const int32 Stage = P->GetTrainingSegment();
        const float Start = P->DistanceMeters;
        const bool bLeadIn = Start < WindRouteTraining::LeadIn;
        const bool bRecovery = WindRouteTraining::IsRecovery(Stage);
        const float SecondsLeft = (WindRouteTraining::SegmentEnds[Stage] - Start) / WindRouteTraining::Speed;
        const TCHAR* Cue = bLeadIn ? TEXT("GET READY: LEFT HAND") :
                           bRecovery ? TEXT("RELAX BOTH TO RECENTER") : WindRouteTraining::SegmentNames[Stage];
        const float S = FMath::Min(Canvas->ClipX/1280.f, Canvas->ClipY/720.f);
        const float W = Canvas->ClipX, H = Canvas->ClipY;
        const float Left = W*.5f - 168*S, Top = H*.072f;
        auto* PC = GetOwningPlayerController();
        for (float D = FMath::Max(0.f, FMath::FloorToFloat(Start/5.f)*5.f); D < FMath::Min(Start + 75.f, P->GetRouteLength()); D += 5.f)
        {
            const int32 Section = D < WindRouteTraining::LeadIn ? 1 : WindRouteTraining::SegmentAt(D);
            for (const float Side : {-1.f, 1.f})
            {
                const float Offset = Side * WindRouteTraining::HalfWidth * 100.f;
                const FVector Down(0,0,-280);
                FVector2D A, B;
                if (PC->ProjectWorldLocationToScreen(P->RoutePoint(D) + P->RouteRight(D)*Offset + Down, A) &&
                    PC->ProjectWorldLocationToScreen(P->RoutePoint(D+3.f) + P->RouteRight(D+3.f)*Offset + Down, B))
                    DrawLine(A.X, A.Y, B.X, B.Y, TrainingColor(Section), 2.f*S);
            }
        }
        DrawRoundedRect(*Canvas, Left, Top, 336*S, 64*S, 10*S, FLinearColor(.014f,.032f,.050f,.88f));
        const TCHAR* Pause = P->bResumeRequested ? TEXT("RELAX BOTH TO RESUME") :
                             P->Emg->HasFreshSignal() ? TEXT("R TO RESUME") : TEXT("SIGNAL PAUSED");
        DrawText(P->bPausedForSignal ? Pause : Cue, TrainingColor(Stage), Left+15*S, Top+8*S, Font, 1.f*S, false);
        const float Error = FMath::Abs(P->GetRouteOffsetMeters());
        FString Detail = Error <= WindRouteTraining::HalfWidth ? TEXT("HOLD INSIDE THE GUIDE") :
                            P->GetRouteOffsetMeters() > 0.f ? TEXT("RETURN LEFT TO THE GUIDE") : TEXT("RETURN RIGHT TO THE GUIDE");
        if (P->bPausedForSignal) Detail = TEXT("TRAINING TIMER PAUSED");
        else if (bLeadIn) Detail = TEXT("FOLLOW THE FIRST RING");
        else if (bRecovery)
        {
            const TCHAR* Status = P->bTrainingRecoveryActive ? TEXT("RECENTERING") : TEXT("RELEASE BOTH SIDES");
            Detail = Stage == 1 ? FString::Printf(TEXT("%s  |  RIGHT IN %.1fs"), Status, SecondsLeft) :
                                 FString::Printf(TEXT("%s  |  FINISH IN %.1fs"), Status, SecondsLeft);
        }
        DrawText(Detail, White, Left+15*S, Top+39*S, Font, .72f*S, false);
    }
    if (P->GateFeedbackTime>0 && !P->bPausedForSignal)
    {
        const float X=Canvas->ClipX*.43f, Y=Canvas->ClipY*.25f;
        DrawText(FString::Printf(TEXT("RING +1    x%d"),P->ConsecutiveGates),Accent,X,Y,Font,1.0f,false);
    }
    if (P->WindZoneFeedbackTime>0 && !P->bPausedForSignal)
        DrawText(TEXT("WIND CURRENT  + SPEED"),Accent,Canvas->ClipX*.40f,Canvas->ClipY*.31f,Font,1.0f,false);
    const int32 Remaining=FMath::CeilToInt(FMath::Max(0.f, P->GetRouteLength()-P->DistanceMeters)/FMath::Max(1.f,P->FlightSpeed));
    // Draw only calibrated, fresh values. Break history on source changes or
    // signal loss so an old trace cannot be mistaken for a live reading.
    const bool bLive=E->HasFreshSignal();
    const double Now=FPlatformTime::Seconds();
    if (!bLive || E->bSimulated!=bPreviousSimulated || !bPreviousLive) {
        LeftHistory.Reset(); RightHistory.Reset(); LastHistoryTime=0.0;
        if(!bLive) { DisplayLeft=0.f; DisplayRight=0.f; }
    }
    bPreviousLive=bLive; bPreviousSimulated=E->bSimulated;
    const float Dt=GetWorld()?FMath::Min(GetWorld()->GetDeltaSeconds(),.1f):.016f;
    const float Left=bLive?FMath::Clamp(E->LeftLevel,0.f,100.f):0.f;
    const float Right=bLive?FMath::Clamp(E->RightLevel,0.f,100.f):0.f;
    DisplayLeft=FMath::FInterpTo(DisplayLeft,Left,Dt,10.f);
    DisplayRight=FMath::FInterpTo(DisplayRight,Right,Dt,10.f);
    if(bLive && (LastHistoryTime==0.0 || Now-LastHistoryTime>=.067)) {
        LeftHistory.Add(DisplayLeft); RightHistory.Add(DisplayRight);
        constexpr int32 MaxHistory=60;
        if(LeftHistory.Num()>MaxHistory) { LeftHistory.RemoveAt(0,LeftHistory.Num()-MaxHistory,EAllowShrinking::No); RightHistory.RemoveAt(0,RightHistory.Num()-MaxHistory,EAllowShrinking::No); }
        LastHistoryTime=Now;
    }
    if (!P->bShowDetails)
    {
        const float Scale = FMath::Min(Canvas->ClipX / 1280.f, Canvas->ClipY / 720.f);
        const FLinearColor Cyan(.12f,.91f,.91f), Gold(1.f,.69f,.24f), Dim(.59f,.68f,.73f);
        const FLinearColor Rule(.32f,.39f,.44f,.65f), Grid(.14f,.19f,.23f,.55f);
        constexpr float Width = 360.f, Height = 151.f;
        const auto X = [Scale](float Value) { return (16.f + Value) * Scale; };
        const auto Y = [Scale](float Value) { return (16.f + Value) * Scale; };
        const auto Rounded = [&](float L, float T, float W, float H, float Radius, FLinearColor Color)
        {
            DrawRoundedRect(*Canvas, X(L), Y(T), W * Scale, H * Scale, Radius * Scale, Color);
        };
        const auto Text = [&](const FString& Label, float L, float T, float Size, FLinearColor Color)
        {
            DrawText(Label, Color, X(L), Y(T), Font, Size * Scale, false);
        };
        const auto Line = [&](float L, float T, float R, float B, FLinearColor Color, float Weight = 1.f)
        {
            FCanvasLineItem Item(FVector2D(X(L), Y(T)), FVector2D(X(R), Y(B)));
            Item.SetColor(Color);
            Item.BlendMode = SE_BLEND_Translucent;
            Item.LineThickness = Weight * Scale;
            Canvas->DrawItem(Item);
        };
        Rounded(-2, 3, Width + 4, Height + 3, 12, FLinearColor(0.f,0.f,0.f,.16f));
        Rounded(0, 0, Width, Height, 11, FLinearColor(.43f,.54f,.61f,.42f));
        Rounded(1, 1, Width - 2, Height - 2, 10, FLinearColor(.012f,.021f,.034f,.88f));

        const TCHAR* Signal = E->bSourceChangePending ? TEXT("CONNECTING") :
            bLive ? (E->bSimulated ? TEXT("SIMULATOR") : TEXT("EMG LIVE")) :
            !E->bConnected ? TEXT("SERVICE OFFLINE") :
            !E->HasRecentSamples() ? TEXT("SIGNAL LOST") : TEXT("CALIBRATE");
        const FLinearColor StatusColor = bLive && !E->bSimulated ? FLinearColor(.24f,1.f,.59f) : Gold;
        Rounded(13, 13, 8, 8, 4, StatusColor);
        Text(Signal, 28, 9, .75f, White);
        Line(150, 9, 150, 25, Rule);
        Line(266, 9, 266, 25, Rule);
        const auto Icon = [&](float CX, float CY, int32 Sides)
        {
            for (int32 I = 0; I < Sides; ++I)
            {
                const float A = (2.f * I / Sides - .5f) * UE_PI;
                const float B = (2.f * (I + 1) / Sides - .5f) * UE_PI;
                Line(CX + 5 * FMath::Cos(A), CY + 5 * FMath::Sin(A),
                     CX + 5 * FMath::Cos(B), CY + 5 * FMath::Sin(B), Dim);
            }
        };
        Icon(166, 17, 6);
        Text(FString::Printf(TEXT("RINGS %d / %d"), P->GatesPassed, P->GetGateCount()), 178, 9, .73f, White);
        Icon(283, 17, 14);
        Line(283, 14, 283, 17, Dim);
        Line(283, 17, 286, 18, Dim);
        Text(FString::Printf(TEXT("%02d:%02d"), Remaining / 60, Remaining % 60), 295, 9, .73f, White);
        Line(12, 33, Width - 12, 33, Rule);

        const auto Row = [&](float Top, const TCHAR* Label, const TCHAR* Channel, FLinearColor Color,
                             float Level, const TArray<float>& History)
        {
            Text(Label, 14, Top + 7, .81f, Color);
            Text(Channel, 64, Top + 9, .64f, Dim);
            constexpr float GraphLeft = 101.f, GraphWidth = 151.f, GraphHeight = 28.f;
            const float Bottom = Top + 31.f;
            for (int32 I = 0; I <= 8; ++I)
            {
                const float GridX = GraphLeft + GraphWidth * I / 8.f;
                Line(GridX, Bottom - GraphHeight, GridX, Bottom, Grid);
            }
            Line(GraphLeft, Bottom, GraphLeft + GraphWidth, Bottom, Grid);
            Line(GraphLeft, Bottom - GraphHeight / 2, GraphLeft + GraphWidth, Bottom - GraphHeight / 2, Grid);
            const FLinearColor Glow(Color.R, Color.G, Color.B, .19f);
            for (int32 I = 1; I < History.Num(); ++I)
            {
                const float A = GraphLeft + GraphWidth * (1.f - (History.Num() - I) / 59.f);
                const float B = A + GraphWidth / 59.f;
                const float U = Bottom - GraphHeight * History[I - 1] / 100.f;
                const float V = Bottom - GraphHeight * History[I] / 100.f;
                Line(A, U, B, V, Glow, 4.f);
                Line(A, U, B, V, Color, 1.35f);
            }
            Rounded(267, Top + 12, 78, 11, 5.5f, Rule);
            Rounded(268, Top + 13, 76, 9, 4.5f, FLinearColor(.055f,.078f,.095f));
            if (bLive) Rounded(268, Top + 13, 76 * Level / 100.f, 9, 4.5f, Color);
            else Text(TEXT("--"), 299, Top + 7, .65f, Dim);
        };
        Row(38, TEXT("LEFT"), TEXT("CH2"), Cyan, DisplayLeft, LeftHistory);
        Row(77, TEXT("RIGHT"), TEXT("CH1"), Gold, DisplayRight, RightHistory);
        Line(12, 75, Width - 12, 75, Grid);
        Line(12, 115, Width - 12, 115, Rule);

        const TCHAR* Direction = P->bResumeRequested ? TEXT("RELAX BOTH HANDS") :
            P->bPausedForSignal ? (P->bUsingEmg && !bLive ? TEXT("FLIGHT PAUSED") : TEXT("R TO START")) :
            P->Steering < -.03f ? TEXT("STEER LEFT") : P->Steering > .03f ? TEXT("STEER RIGHT") : TEXT("NEUTRAL");
        float TextWidth = 0.f, TextHeight = 0.f;
        GetTextSize(Direction, TextWidth, TextHeight, Font, .81f);
        Text(Direction, (Width - TextWidth) * .5f, 123, .81f, White);
        Text(TEXT("H  DETAILS"), 14, 126, .61f, Dim);
        Text(P->bLowPower ? TEXT("LOW POWER") : P->bUsingEmg ? TEXT("EMG MODE") : TEXT("KEYBOARD"),
             280, 126, .61f, P->bLowPower ? Gold : Dim);
        return;
    }
    DrawRect(FLinearColor(.015f,.035f,.065f,.88f),12,12,650,320);
    DrawText(TEXT("WIND ROUTE - EMG PROTOTYPE"),White,25,22,Font,.9f,false);
    DrawText(FString::Printf(TEXT("ETA %02d:%02d   Rings %d/%d   Guide %.0f%%  %s %.1f m/s"),Remaining/60,Remaining%60,P->GatesPassed,P->GetGateCount(),P->GuideRatio*100.f,TEXT("FREE STEERING / AUTO HEIGHT"),P->FlightSpeed),White,25,50,Font,.7f,false);
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
