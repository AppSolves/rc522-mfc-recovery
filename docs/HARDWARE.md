# Hardware setup

## Required parts

- Raspberry Pi 4 or Raspberry Pi 5
- MFRC522 / RC522 13.56 MHz module
- jumper wires
- a MIFARE Classic 1K card you own or are authorized to test
- stable 3.3 V power and adequate Raspberry Pi cooling

## Wiring

| RC522 | Physical pin | BCM | Purpose |
|---|---:|---:|---|
| `3.3V` | 1 | - | Power |
| `GND` | 6 | - | Ground |
| `SDA` / `SS` | 24 | 8 | SPI0 CE0 |
| `SCK` | 23 | 11 | SPI0 clock |
| `MOSI` | 19 | 10 | SPI0 MOSI |
| `MISO` | 21 | 9 | SPI0 MISO |
| `RST` | 18 | 24 | Reset, WiringPi pin 5 |
| `IRQ` | - | - | Not used |

Never power the module from 5 V.

## Enable SPI

```bash
sudo raspi-config nonint do_spi 0
sudo reboot
ls -l /dev/spidev0.0
```

## Reader validation

```bash
rc522-mfc doctor
```

A normal MFRC522 commonly reports VersionReg `0x91` or `0x92`. Stable clone-specific values may also work. `0x00` or `0xFF` usually indicates wiring, power, chip-select, or module problems.

## Coupling

Keep the card flat and motionless over the antenna during acquisition. Long Hardnested runs should use tape or a non-metallic clamp. Do not place metal directly beneath the antenna.
