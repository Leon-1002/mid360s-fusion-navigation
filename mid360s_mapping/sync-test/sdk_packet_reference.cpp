// Golden packet generator uses the existing upstream Livox SDK2 implementation.
#include "comm/sdk_protocol.h"
#include <cstdio>
#include <cstdint>
#include <cstring>
int main() {
    using namespace livox::lidar;
    const uint64_t ns=1795392000ULL*1000000000ULL;
    uint8_t payload[9]={2}; std::memcpy(payload+1,&ns,8);
    CommPacket command{};
    command.protocol=kLidarSdk; command.seq_num=7; command.cmd_id=0x0202;
    command.data=payload; command.data_len=sizeof(payload);
    uint8_t bytes[64]={}; uint32_t length=0;
    SdkProtocol sdk;
    if (sdk.Pack(bytes,sizeof(bytes),&length,command)!=0) return 1;
    if (!sdk.CheckPreamble(bytes,length)) return 2;
    for (uint32_t i=0;i<length;++i) std::printf("%02x",bytes[i]);
    std::puts(""); return 0;
}
