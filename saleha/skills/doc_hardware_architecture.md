---
id: "doc_hardware_architecture"
title: "Unified Hardware Architecture & Subsystem Specification"
version: "3.0.0"
---

# Unified Hardware Architecture Specification

## 1. System Block Diagram
```text
 ┌──────────────────────────────────────────────────────────────┐
 │                     MAIN SYSTEM BOARD                        │
 │                                                              │
 │   ┌────────────────────────┐      PCIe 3.0 x4    ┌─────────┐ │
 │   │ Primary Application SoC│ ◄─────────────────► │ NVMe SSD│ │
 │   │ (ARM Cortex-A78 Octa)  │                     └─────────┘ │
 │   └───────────┬────────────┘                                 │
 │               │ SPI / DMA @ 50MHz                            │
 │               ▼                                              │
 │   ┌────────────────────────┐      CAN-FD Bus     ┌─────────┐ │
 │   │ Real-time Safety MCU   │ ◄─────────────────► │ Transc. │ │
 │   │ (STM32H7 Dual Cortex-M)│                     └────┬────┘ │
 │   └───────────┬────────────┘                          │      │
 └───────────────┼───────────────────────────────────────┼──────┘
                 ▼                                       ▼
        [Power Management]                      [External CAN-FD Net]
```

