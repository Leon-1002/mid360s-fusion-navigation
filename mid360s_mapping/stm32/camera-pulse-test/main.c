#include "stm32f10x.h"

/* PA1 = TIM2_CH2. Each reset starts one batch of ten camera triggers. */
#define TIMER_TICKS_PER_SECOND 10000u
#define PULSE_HIGH_TICKS       100u
#define PULSE_COUNT            10u

volatile uint32_t completed_pulses = 0;
volatile uint32_t test_complete = 0;

static void stop_pulses(void)
{
    GPIO_InitTypeDef gpio;

    /* Take over PA1 at the falling edge and hold it low after the batch. */
    GPIO_ResetBits(GPIOA, GPIO_Pin_1);
    GPIO_StructInit(&gpio);
    gpio.GPIO_Pin = GPIO_Pin_1;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    GPIO_Init(GPIOA, &gpio);
    TIM_ITConfig(TIM2, TIM_IT_Update, DISABLE);
    TIM_Cmd(TIM2, DISABLE);
    test_complete = 1;
}

void TIM2_IRQHandler(void)
{
    if (TIM_GetITStatus(TIM2, TIM_IT_Update) != RESET) {
        TIM_ClearITPendingBit(TIM2, TIM_IT_Update);
        completed_pulses++;
        if (completed_pulses >= PULSE_COUNT) {
            stop_pulses();
        }
    }
}

int main(void)
{
    GPIO_InitTypeDef gpio;
    TIM_TimeBaseInitTypeDef timebase;
    TIM_OCInitTypeDef output;
    NVIC_InitTypeDef interrupt;
    RCC_ClocksTypeDef clocks;
    uint32_t timer_clock;

    RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE);
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM2, ENABLE);

    GPIO_ResetBits(GPIOA, GPIO_Pin_1);
    GPIO_StructInit(&gpio);
    gpio.GPIO_Pin = GPIO_Pin_1;
    gpio.GPIO_Mode = GPIO_Mode_Out_PP;
    gpio.GPIO_Speed = GPIO_Speed_2MHz;
    GPIO_Init(GPIOA, &gpio);

    RCC_GetClocksFreq(&clocks);
    timer_clock = clocks.PCLK1_Frequency;
    if (clocks.PCLK1_Frequency != clocks.HCLK_Frequency) {
        timer_clock *= 2u;
    }

    TIM_DeInit(TIM2);
    TIM_TimeBaseStructInit(&timebase);
    timebase.TIM_Prescaler = (uint16_t)(timer_clock / TIMER_TICKS_PER_SECOND - 1u);
    timebase.TIM_Period = TIMER_TICKS_PER_SECOND - 1u;
    TIM_TimeBaseInit(TIM2, &timebase);

    /* PWM2 starts low. The first rising edge is at 990 ms, falling at 1 s. */
    TIM_OCStructInit(&output);
    output.TIM_OCMode = TIM_OCMode_PWM2;
    output.TIM_OutputState = TIM_OutputState_Enable;
    output.TIM_OCPolarity = TIM_OCPolarity_High;
    output.TIM_Pulse = TIMER_TICKS_PER_SECOND - PULSE_HIGH_TICKS;
    TIM_OC2Init(TIM2, &output);
    TIM_OC2PreloadConfig(TIM2, TIM_OCPreload_Enable);
    TIM_ARRPreloadConfig(TIM2, ENABLE);
    TIM_GenerateEvent(TIM2, TIM_EventSource_Update);
    TIM_ClearITPendingBit(TIM2, TIM_IT_Update);
    NVIC_ClearPendingIRQ(TIM2_IRQn);

    interrupt.NVIC_IRQChannel = TIM2_IRQn;
    interrupt.NVIC_IRQChannelPreemptionPriority = 0;
    interrupt.NVIC_IRQChannelSubPriority = 0;
    interrupt.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&interrupt);
    TIM_ITConfig(TIM2, TIM_IT_Update, ENABLE);

    gpio.GPIO_Mode = GPIO_Mode_AF_PP;
    GPIO_Init(GPIOA, &gpio);
    TIM_Cmd(TIM2, ENABLE);

    for (;;) {
        /* Keep clocks running so SWD remains accessible during this bench test. */
        __NOP();
    }
}
