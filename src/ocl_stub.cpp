#include "engine.h"
std::unique_ptr<Engine> makeOclEngine(const Layout&, int, int, bool) { throw std::runtime_error("built without OpenCL"); }
std::string listOclDevices() { return "built without OpenCL\n"; }
std::vector<OclDeviceInfo> oclDeviceInfo() { throw std::runtime_error("built without OpenCL"); }
bool g_oclProfile = false;
std::string oclProfileReport() { return ""; }
