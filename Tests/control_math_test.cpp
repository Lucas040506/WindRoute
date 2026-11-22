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
 assert(RouteLengthMeters/FlightSpeedMetersPerSecond==150.f);
 std::cout << "PASS steering and route checks\n";
}
