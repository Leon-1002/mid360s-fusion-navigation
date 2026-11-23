#include "stm32f10x.h"
#include "rmc.h"

/* Bench-only synthetic epoch: 2026-11-23 00:00:00 UTC. NOT real UTC/GNSS. */
#define BENCH_EPOCH 1795392000u
#define TICKS_PER_SECOND 10000u
volatile uint32_t pps_count = 0;
volatile uint32_t rmc_sent_count = 0;
volatile uint32_t firmware_fault = 0;
volatile uint32_t hse_ready = 0;
/* Host writes only camera_request via SWD; no MCU reset needed to start batch. */
volatile uint32_t camera_request = 0;
volatile uint32_t camera_state = 0; /* 0 idle, 1 armed, 2 running, 3 complete */
volatile uint32_t camera_pulses = 0;
volatile uint32_t camera_epoch = 0;
const uint32_t joint_firmware_version = 0x4A533031u;

static void stop_camera(void)
{
    GPIO_InitTypeDef gpio;
    TIM_SelectSlaveMode(TIM2, 0);
    TIM_Cmd(TIM2, DISABLE);
    TIM_ITConfig(TIM2, TIM_IT_Update | TIM_IT_Trigger, DISABLE);
    GPIO_ResetBits(GPIOA, GPIO_Pin_1);
    GPIO_StructInit(&gpio);
    gpio.GPIO_Pin = GPIO_Pin_1;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    GPIO_Init(GPIOA, &gpio);
}

void TIM2_IRQHandler(void)
{
    if (TIM_GetITStatus(TIM2, TIM_IT_Trigger) != RESET) {
        TIM_ClearITPendingBit(TIM2, TIM_IT_Trigger);
        if (camera_state == 1u) {
            camera_epoch = BENCH_EPOCH + pps_count - 1u;
            camera_state = 2u;
        }
    }
    if (TIM_GetITStatus(TIM2, TIM_IT_Update) != RESET) {
        TIM_ClearITPendingBit(TIM2, TIM_IT_Update);
        if (camera_state == 2u && ++camera_pulses >= 300u) {
            stop_camera(); /* Falling edge of the 300th pulse. */
            camera_state = 3u;
        }
    }
}

static void arm_camera(uint32_t timer_clock)
{
    GPIO_InitTypeDef gpio;
    TIM_TimeBaseInitTypeDef timer;
    TIM_OCInitTypeDef output;
    NVIC_InitTypeDef irq;
    TIM_DeInit(TIM2);
    TIM_TimeBaseStructInit(&timer);
    timer.TIM_Prescaler = (uint16_t)(timer_clock / TICKS_PER_SECOND - 1u);
    timer.TIM_Period = 1999; /* 5 Hz on the same APB1 clock as TIM3. */
    TIM_TimeBaseInit(TIM2, &timer);
    TIM_OCStructInit(&output);
    output.TIM_OCMode = TIM_OCMode_PWM2;
    output.TIM_OutputState = TIM_OutputState_Enable;
    output.TIM_OCPolarity = TIM_OCPolarity_High;
    output.TIM_Pulse = 1900; /* Rise at PPS + 190 ms, high for 10 ms. */
    TIM_OC2Init(TIM2, &output);
    TIM_OC2PreloadConfig(TIM2, TIM_OCPreload_Enable);
    TIM_ARRPreloadConfig(TIM2, ENABLE);
    TIM_GenerateEvent(TIM2, TIM_EventSource_Update);
    TIM_ClearITPendingBit(TIM2, TIM_IT_Update | TIM_IT_Trigger);
    NVIC_ClearPendingIRQ(TIM2_IRQn);
    irq.NVIC_IRQChannel = TIM2_IRQn;
    irq.NVIC_IRQChannelPreemptionPriority = 1;
    irq.NVIC_IRQChannelSubPriority = 0;
    irq.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&irq);
    GPIO_StructInit(&gpio);
    gpio.GPIO_Pin = GPIO_Pin_1;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    GPIO_Init(GPIOA, &gpio);
    camera_pulses = 0;
    camera_epoch = 0;
    camera_state = 1;
    TIM_ITConfig(TIM2, TIM_IT_Update | TIM_IT_Trigger, ENABLE);
    /* RM0008 TIM2 ITR2 = TIM3 TRGO. Hardware starts TIM2 on next PPS rise.
       Subsequent trigger edges do not reset an already running counter. */
    TIM_SelectInputTrigger(TIM2, TIM_TS_ITR2);
    TIM_SelectSlaveMode(TIM2, TIM_SlaveMode_Trigger);
}

void TIM3_IRQHandler(void)
{
    if (TIM_GetITStatus(TIM3, TIM_IT_CC2) != RESET) {
        TIM_ClearITPendingBit(TIM3, TIM_IT_CC2);
        ++pps_count; /* CC2 is the hardware rising edge in PWM2 mode. */
        if (pps_count & 1u) GPIO_ResetBits(GPIOC, GPIO_Pin_13);
        else GPIO_SetBits(GPIOC, GPIO_Pin_13);
    }
}

static void send_text(const char *text)
{
    while (*text) {
        while (USART_GetFlagStatus(USART1, USART_FLAG_TXE) == RESET) { __NOP(); }
        USART_SendData(USART1, (uint8_t)*text++);
    }
    while (USART_GetFlagStatus(USART1, USART_FLAG_TC) == RESET) { __NOP(); }
}

int main(void)
{
    GPIO_InitTypeDef gpio;
    USART_InitTypeDef uart;
    TIM_TimeBaseInitTypeDef timer;
    TIM_OCInitTypeDef output;
    NVIC_InitTypeDef irq;
    RCC_ClocksTypeDef clocks;
    uint32_t timer_clock, sequence;
    char rmc[96];

    RCC_APB2PeriphClockCmd(RCC_APB2Periph_AFIO | RCC_APB2Periph_GPIOA |
                          RCC_APB2Periph_GPIOB | RCC_APB2Periph_GPIOC |
                          RCC_APB2Periph_USART1, ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM3 | RCC_APB1Periph_TIM2, ENABLE);
    NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2);
    GPIO_StructInit(&gpio);
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    gpio.GPIO_Pin = GPIO_Pin_1;
    GPIO_ResetBits(GPIOA, GPIO_Pin_1); /* Remain low until camera acquisition is ready. */
    GPIO_Init(GPIOA, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_13;
    GPIO_SetBits(GPIOC, GPIO_Pin_13);
    GPIO_Init(GPIOC, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_5;
    GPIO_ResetBits(GPIOB, GPIO_Pin_5);
    GPIO_Init(GPIOB, &gpio);
    gpio.GPIO_Pin = GPIO_Pin_9;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(GPIOA, &gpio);
    USART_StructInit(&uart);
    uart.USART_BaudRate = 9600;
    uart.USART_Mode = USART_Mode_Tx;
    USART_Init(USART1, &uart);
    USART_Cmd(USART1, ENABLE);
    hse_ready = RCC_GetFlagStatus(RCC_FLAG_HSERDY) != RESET;
    if (!hse_ready) {
        firmware_fault = 1;
        send_text("!ERROR,HSE_NOT_READY,PPS_DISABLED\r\n");
        for (;;) { __NOP(); }
    }
    RCC_GetClocksFreq(&clocks);
    timer_clock = clocks.PCLK1_Frequency;
    if (clocks.PCLK1_Frequency != clocks.HCLK_Frequency) timer_clock *= 2u;
    TIM_DeInit(TIM3);
    GPIO_PinRemapConfig(GPIO_PartialRemap_TIM3, ENABLE);
    TIM_TimeBaseStructInit(&timer);
    timer.TIM_Prescaler = (uint16_t)(timer_clock / TICKS_PER_SECOND - 1u);
    timer.TIM_Period = TICKS_PER_SECOND - 1u;
    TIM_TimeBaseInit(TIM3, &timer);
    TIM_OCStructInit(&output);
    output.TIM_OCMode = TIM_OCMode_PWM2;
    output.TIM_OutputState = TIM_OutputState_Enable;
    output.TIM_OCPolarity = TIM_OCPolarity_High;
    output.TIM_Pulse = 9000; /* Low 900 ms, then high 100 ms. */
    TIM_OC2Init(TIM3, &output);
    TIM_OC2PreloadConfig(TIM3, TIM_OCPreload_Enable);
    TIM_SelectOutputTrigger(TIM3, TIM_TRGOSource_OC2Ref);
    TIM_ARRPreloadConfig(TIM3, ENABLE);
    TIM_GenerateEvent(TIM3, TIM_EventSource_Update);
    TIM_ClearITPendingBit(TIM3, TIM_IT_Update | TIM_IT_CC2);
    NVIC_ClearPendingIRQ(TIM3_IRQn);
    irq.NVIC_IRQChannel = TIM3_IRQn;
    irq.NVIC_IRQChannelPreemptionPriority = 0;
    irq.NVIC_IRQChannelSubPriority = 0;
    irq.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&irq);
    TIM_ITConfig(TIM3, TIM_IT_CC2, ENABLE);
    gpio.GPIO_Pin = GPIO_Pin_5;
    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(GPIOB, &gpio);
    send_text("!BENCH_ONLY,JOINT_V1,PB5_PPS_1HZ,PA9_TX_9600,PA1_5HZ_ARMED_BY_HOST\r\n");
    TIM_Cmd(TIM3, ENABLE);
    for (;;) {
        sequence = pps_count;
        if (sequence != rmc_sent_count) {
            if (sequence != rmc_sent_count + 1u ||
                make_bench_rmc(BENCH_EPOCH + sequence - 1u, rmc, sizeof(rmc)) < 0) {
                firmware_fault = 2;
                stop_camera();
                TIM_Cmd(TIM3, DISABLE);
                gpio.GPIO_Mode = GPIO_Mode_Out_PP;
                GPIO_ResetBits(GPIOB, GPIO_Pin_5);
                GPIO_Init(GPIOB, &gpio);
                send_text("!ERROR,MISSED_PPS,PPS_DISABLED\r\n");
                for (;;) { __NOP(); }
            }
            send_text(rmc);
            rmc_sent_count = sequence;
        }
        if (camera_request == 0x53544F50u) {
            stop_camera(); camera_state = 0; camera_request = 0;
        }
        if (camera_request == 0x43414D35u && (camera_state == 0 || camera_state == 3) &&
            TIM3->CNT > 1000 && TIM3->CNT < 8000) {
            camera_request = 0;
            arm_camera(timer_clock);
        }
        __NOP(); /* Keep SWD accessible; no WFI. */
    }
}
