#include "stm32f10x.h"
#include "rmc.h"

/* Bench-only synthetic epoch: 2026-11-23 00:00:00 UTC. NOT real UTC/GNSS. */
#define BENCH_EPOCH 1795392000u
#define TICKS_PER_SECOND 10000u
volatile uint32_t pps_count = 0;
volatile uint32_t rmc_sent_count = 0;
volatile uint32_t firmware_fault = 0;
volatile uint32_t hse_ready = 0;

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
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM3, ENABLE);
    GPIO_StructInit(&gpio);
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    gpio.GPIO_Pin = GPIO_Pin_1;
    GPIO_ResetBits(GPIOA, GPIO_Pin_1); /* Camera disabled in this radar-only test. */
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
    send_text("!BENCH_ONLY,SYNTHETIC_TIME,PB5_PPS_1HZ,PA9_TX_9600,PA1_DISABLED\r\n");
    TIM_Cmd(TIM3, ENABLE);
    for (;;) {
        sequence = pps_count;
        if (sequence != rmc_sent_count) {
            if (sequence != rmc_sent_count + 1u ||
                make_bench_rmc(BENCH_EPOCH + sequence - 1u, rmc, sizeof(rmc)) < 0) {
                firmware_fault = 2;
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
        __NOP(); /* Keep SWD accessible; no WFI. */
    }
}
