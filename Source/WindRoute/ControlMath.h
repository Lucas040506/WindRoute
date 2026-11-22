#pragma once
#include <algorithm>
#include <cmath>

// Device levels are percentages of the separately calibrated comfortable level.
namespace WindRouteControl
{
constexpr float RouteLengthMeters = 3273.797f;
constexpr float FlightSpeedMetersPerSecond = 20.f;
constexpr float GuideCycleMeters = 200.f;
constexpr int GateCount = 40;
// Game-tuned kinematic model, in meters and seconds; not a real aerodynamic simulation.
struct GlideState { float height=13.f, verticalSpeed=0.f, speed=8.f; };
inline void StepGlide(GlideState& s, float lift, float dt, float dive=0.f) {
    if (dt<=0.f) return;
    lift=std::clamp(lift,0.f,1.f);
    dive=std::clamp(dive,0.f,1.f);
    const float oldHeight=s.height;
    const float targetVertical=-.35f+3.35f*lift-2.65f*dive;
    s.verticalSpeed+=(targetVertical-s.verticalSpeed)*std::min(1.f,dt*3.f);
    s.height=std::clamp(s.height+s.verticalSpeed*dt,7.5f,19.f);
    const float actualVertical=(s.height-oldHeight)/dt;
    if ((s.height<=7.5f && s.verticalSpeed<0.f) || (s.height>=19.f && s.verticalSpeed>0.f)) s.verticalSpeed=0.f;
    // Ease toward a modest speed change; abrupt drag changes feel like a hitch.
    const float targetSpeed=std::clamp(8.f-actualVertical*.18f,7.45f,8.55f);
    const float blend=1.f-std::exp(-.45f*dt);
    s.speed=std::clamp(s.speed+(targetSpeed-s.speed)*blend,7.45f,8.55f);
}
enum class GesturePhase { Idle, First, Gap, Second, Climb, Dive };
struct GestureState { GesturePhase phase=GesturePhase::Idle; float time=0.f; };
inline void StepGesture(GestureState& state, float left, float right, float dt) {
    if (dt<=0.f) return;
    const bool on=left>=30.f && right>=30.f;
    const bool held=left>=18.f && right>=18.f;
    const bool released=left<18.f && right<18.f;
    state.time+=dt;
    const auto set=[&](GesturePhase phase) { state.phase=phase; state.time=0.f; };
    switch(state.phase) {
        case GesturePhase::Idle: if(on) set(GesturePhase::First); break;
        case GesturePhase::First:
            if(!held) { if(released && state.time>=.10f && state.time<.45f) set(GesturePhase::Gap); else set(GesturePhase::Idle); }
            else if(state.time>=.45f) set(GesturePhase::Climb);
            break;
        case GesturePhase::Gap: if(on) set(GesturePhase::Second); else if(state.time>=.8f) set(GesturePhase::Idle); break;
        case GesturePhase::Second: if(!held) set(GesturePhase::Idle); else if(state.time>=.12f) set(GesturePhase::Dive); break;
        case GesturePhase::Climb: case GesturePhase::Dive: if(!held) set(GesturePhase::Idle); break;
    }
}
inline float GateDistance(int Index) { return 80.f * (std::clamp(Index, 0, GateCount-1) + 1); }
inline bool CrossesGate(float OldDistance, float NewDistance, float Gate) { return OldDistance < Gate && NewDistance >= Gate; }
inline bool InsideGate(float Y, float GateY) { return std::abs(Y-GateY) <= 170.f; }
// Center of the canyon in world centimeters, parameterized by forward distance.
inline float CanyonCenter(float) { return 0.f; }
inline float CanyonSlope(float) { return 0.f; }
inline float GateHeight(int) { return 1300.f; }
inline bool InsideGate3D(float Y,float Z,float GateY,float GateZ) {
    const float dy=(Y-GateY)/170.f, dz=(Z-GateZ)/190.f;
    return dy*dy+dz*dz<=1.f;
}
// Hysteresis avoids rapid toggling at the activation threshold.
inline bool LiftActive(bool Active,float Left,float Right) {
    const float threshold=Active?18.f:30.f;
    return Left>=threshold && Right>=threshold;
}

inline float Steering(float Left, float Right)
{
    const float L=std::clamp((Left-8.f)/52.f,0.f,1.f);
    const float R=std::clamp((Right-8.f)/52.f,0.f,1.f);
    const float D=R-L;
    return std::abs(D)<.08f ? 0.f : std::clamp(D,-1.f,1.f);
}
inline float GuideSegment(float D)
{
    constexpr float Pi=3.14159265358979323846f;
    if (D<18) return 0;
    if (D<24) return 3.8f*std::sin((D-18)/6*Pi/2);
    if (D<85) return 3.8f*std::cos((D-24)/61*Pi);
    if (D<95) return -3.8f*std::cos((D-85)/10*Pi/2);
    if (D<110) return 0;
    if (D<120) return -3.8f*std::sin((D-110)/10*Pi/2);
    if (D<185) return -3.8f*std::cos((D-120)/65*Pi);
    if (D<195) return 3.8f*std::cos((D-185)/10*Pi/2);
    return 0;
}
inline float Guide(float D)
{
    if (D < 0.f || D >= RouteLengthMeters) return 0.f;
    const int cycle = static_cast<int>(D / GuideCycleMeters);
    const float segment = D - cycle * GuideCycleMeters;
    return (cycle % 2 ? -1.f : 1.f) * GuideSegment(segment);
}
}
