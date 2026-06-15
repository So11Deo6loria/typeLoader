# typeLoader

typeLoader is a Ghidra script that can aid in reverse engineering bare metal firmware. It relies on vendor specific types used for the hardware abstraction layer (HAL) and on-chip peripheral register blocks. You identify the micro on the board, load the matching vendor type file, and then cast variables as pointers to the imported peripheral/HAL types. Please reach out to me if you would like to support in any way: So11Deo6loria@proton.me.

## Supported vendor type files

Each vendor has its own `*DataTypes.json` (CMSIS peripheral register blocks in true offset order, plus HAL/driver config and handle structs, and vendor status enums):

| File | Vendor / families |
| --- | --- |
| `stmDataTypes.json` | STMicroelectronics — STM32 HAL |
| `nxpDataTypes.json` | NXP — Kinetis / LPC / i.MX RT (MCUXpresso `fsl_` drivers) |
| `microchipDataTypes.json` | Microchip / Atmel — SAM D/E (ASF/Harmony), some PIC32 |
| `nordicDataTypes.json` | Nordic — nRF52/nRF53 (nrfx) |
| `tiDataTypes.json` | Texas Instruments — TM4C / Tiva C (TivaWare) |
| `espressifDataTypes.json` | Espressif — ESP32 (ESP-IDF `*_dev_t`) |
| `renesasDataTypes.json` | Renesas — RA family (FSP) |

> **Accuracy note:** these vendor files were authored from known CMSIS/SDK definitions and cover the most commonly reverse-engineered peripherals, with reserved-padding fields inserted to keep register offsets correct. They are a strong starting point but are not exhaustive and are not pinned to a specific silicon revision/SDK version. For ground truth on a specific part, generate a file from that part's actual headers with `typeExtractor.py` (see below) and verify offset-sensitive structs against the reference manual.

## Requirements
- **Ghidra 12+** with the **PyGhidra** (CPython 3) scripting provider. `typeLoader.py` is tagged `@runtime PyGhidra` so Ghidra runs it under Python 3 rather than the removed Jython 2.7 interpreter. PyGhidra ships with Ghidra 12; if it is not already enabled, run Ghidra's `support/pyghidra` setup once (or install the `pyghidra` package) so the Python 3 provider is available.
- **Python 3** (3.9+) for the standalone `typeExtractor.py` / `extractors/` HAL parsers.

## Usage
The script can be loaded into Ghidra and invoked at any point during the RE process. When run it shows a drop-down of the vendor type files it finds next to `typeLoader.py` (labelled by vendor, e.g. *"Nordic - nRF52 / nRF53"*) — pick the one that matches the micro you are analyzing, or choose *"Browse for a file..."* to load a JSON from elsewhere. (When running headless with no dialog, it loads a `*DataTypes.json` sitting next to `typeLoader.py`, preferring `stmDataTypes.json` for backwards compatibility.) The types are created under the `/CustomTypes` category; once they are added you can simply cast variables as pointers to the imported peripheral/HAL types. I also plan to explore automatically suggesting types at some point.

`typeLoader.py` maps `uint8_t` / `uint16_t` / `uint32_t` (and arrays/pointers of them) to fixed-width Ghidra types so register-block offsets are preserved, and resolves struct/enum cross-references defined in the same file.

## Extracting types from vendor headers
To build a type file from a specific part's real SDK/CMSIS headers, use the standalone `typeExtractor.py` parser (Python 3):

```
python3 typeExtractor.py --vendor ST --directory /path/to/hal/headers --output stmDataTypes.json
```

This is the ground-truth path for offset-accurate, version-correct structs. The shipped `*DataTypes.json` files are curated starting points for when you don't have the headers handy.
![typeLoaderDemo](https://github.com/So11Deo6loria/typeLoader/assets/14260835/afa93db9-573e-4f7e-901e-ae67312ff5c1)
