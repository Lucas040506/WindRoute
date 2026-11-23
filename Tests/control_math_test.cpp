#include "../Source/WindRoute/ControlMath.h"
#include <cassert>
#include <cmath>
#include <iostream>
int main() {
 using namespace WindRouteControl;
 assert(Steering(0,0)==0 && Steering(60,0)<-.99f && Steering(0,60)>.99f);
 assert(Steering(30,30)==0 && Steering(8,9)==0);
 assert(CrossesGate(69.9f,70.f,70.f) && !CrossesGate(70.f,70.1f,70.f));
 assert(InsideGate3D(0,1300,0,GateHeight(3)));
 const float nominalDuration = RouteLengthMeters / FlightSpeedMetersPerSecond;
 assert(nominalDuration >= 120.f && nominalDuration <= 180.f);
 assert(GateDistance(0) > 0.f && GateDistance(GateCount - 1) < RouteLengthMeters);
 std::cout << "PASS steering and route checks\n";
}
