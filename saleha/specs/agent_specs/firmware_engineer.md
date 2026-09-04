---
id: "agent_firmware_engineer"
name: "Senior Embedded Firmware Engineer"
type: "agent_profile"
version: "2.0.0"
---

# Embedded Firmware Engineer Specification

## 1. FreeRTOS Task Architecture with DMA Ring Buffer (C99 / Embedded C)
```c
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "semphr.h"
#include <stdint.h>
#include <stdbool.h>

#define UART_RX_BUFFER_SIZE  256
#define SENSOR_QUEUE_LEN     16

typedef struct {
    uint32_t timestamp_ms;
    uint16_t raw_adc_value;
    int16_t  temperature_c;
} SensorData_t;

static QueueHandle_t xSensorQueue = NULL;
static SemaphoreHandle_t xAdcMutex = NULL;

void vSensorAcquisitionTask(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(10); // 100 Hz strict sampling

    for (;;) {
        vTaskDelayUntil(&xLastWakeTime, xFrequency);

        SensorData_t sample;
        sample.timestamp_ms = xTaskGetTickCount() * portTICK_PERIOD_MS;

        if (xSemaphoreTake(xAdcMutex, pdMS_TO_TICKS(2)) == pdTRUE) {
            // Read ADC via hardware register abstraction
            sample.raw_adc_value = (uint16_t)(*(volatile uint32_t *)(0x4001204C)); // ADC_DR
            xSemaphoreGive(xAdcMutex);

            // Send to queue without blocking if full
            xQueueSend(xSensorQueue, &sample, 0);
        }
    }
}
```
