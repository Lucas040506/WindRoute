#pragma once

namespace WindRouteTraining
{
constexpr float Speed = 14.f;
constexpr float TurnRate = 7.5f;
constexpr float LeadIn = 21.f;
constexpr float LeftEnd = LeadIn + Speed * 3.f;
constexpr float RightStart = LeftEnd + Speed * 5.f;
constexpr float RightEnd = RightStart + Speed * 3.f;
constexpr float Length = RightEnd + Speed * 4.f;
constexpr float HalfWidth = 15.f;
constexpr float RingRadiusCm = 950.f;
constexpr float RingGraceMeters = 10.f;
constexpr float NeutralThreshold = .08f;
constexpr float RecoveryTurnRate = 26.f;
constexpr float RecoveryLateralSpeedCm = 650.f;
constexpr float SegmentEnds[] = {LeftEnd, RightStart, RightEnd, Length};
constexpr float GateDistances[] = {LeadIn, LeftEnd, RightStart, RightEnd, Length - RingGraceMeters};
constexpr int SegmentCount = 4;
constexpr int GateCount = 5;
constexpr const TCHAR* SegmentNames[] = {
    TEXT("LEFT HAND"), TEXT("RELAX BOTH"), TEXT("RIGHT HAND"), TEXT("RELAX BOTH")
};

inline int SegmentAt(float Distance)
{
    int Segment = 0;
    while (Segment + 1 < SegmentCount && Distance >= SegmentEnds[Segment]) ++Segment;
    return Segment;
}

inline bool IsRecovery(int Segment)
{
    return Segment == 1 || Segment == 3;
}
}
