LidarPpsUart: original-route radar-only bench firmware

PB5 / TIM3_CH2 = 1 Hz PPS, 100 ms high; first rising edge 900 ms after timer start.
PA9 / USART1 TX = 9600 baud, 8N1. Connect to a 3.3 V USB-TTL adapter RXD and GND.
Do NOT connect PA9 to the lidar GPS input for this project route.
PA1 stays low; this firmware does not trigger the camera.
PC13 toggles each PPS if the board's LED is wired to it.

Time starts at the synthetic epoch 2026-11-23 00:00:00 on every boot.
RMC status V and mode N deliberately mark no GNSS position/fix. The companion host
bench tool explicitly accepts this test format and transmits its time via command 0x0202.
This is not a live GNSS/RTK time source and must not run while mapping is active.
Hardware CC2 emits the rising edge; the ISR increments pps_count, main sends that edge's time.
At 9600 baud a short RMC line takes roughly 50 ms. Actual edge/serial latency must be measured.
An HSE failure disables PPS and emits an error. A missed whole PPS disables output.

Open lidar-pps-uart.uvprojx in Keil5 / ARM Compiler5; F7 then Flash -> Download.
Alternatively run build.ps1. build-keil and build contain separate build products.
Never flash the incomplete sibling lidar-sync-test skeleton.

Sources: STM32 SPL/CMSIS copied from the existing camera-pulse-test project,
with original ST copyright notices retained. USART library comes from downloaded LIV_handhold.
New main.c and rmc.c are separate from the previously validated camera pulse firmware.

Complete Chinese user checklist: ../../sync-test/硬件触发测试步骤-20261123.txt
