# SPI & UART Tool

A macOS GUI tool for working with SPI flash chips and UART devices.

Replaces manual flashrom and screen commands with a native graphical interface.

## Features

### SPI flash programmer

- Auto-detect chip (with name and size)
- Read dump to file (with real-time progress)
- Write dump from file
- Verify chip against file
- Erase chip
- SHA256 hash for dumps
- Auto-verify after read / write (optional)
- Support for 705+ chips (via libflashrom)

### UART terminal

- Auto-detect available serial ports
- Connect at any baud rate
- Full terminal emulation (with scrollback history)
- Send / receive data
- Copy / paste support
- Save terminal log to file
- Open in external Terminal.app (via screen)

### General

- USB hotplug detection (SPI / UART mode, no restart needed)
- Programmer mode indicator in toolbar
- Settings persistence (JSON config)
- System log with rotation
- Dark log theme (like a terminal)

## Requirements

- macOS 10.13 or later
- CH340 driver (only for UART mode) — download from wch.cn
- CH341A programmer (or compatible CH341-family device)
- SPI flash chip (for SPI operations)

## Installation

### For users

Download the latest .zip from the Releases section.

1. Unpack SPI_UART_Tool.app and SPI-UART-Tool-Launcher.app to the same folder
2. Install CH340 driver (only for UART)
3. Right-click on SPI-UART-Tool-Launcher.app, choose Open, then Open again (first time only)
4. Enter your admin password

### For developers

Build from source:

Step 1. Install dependencies via Homebrew:

    brew install python@3.14 flashrom tcl-tk

Step 2. Clone repository:

    git clone https://github.com/SYAO/spi-uart-tool.git
    cd spi-uart-tool

Step 3. Create virtual environment:

    python3 -m venv venv
    source venv/bin/activate

Step 4. Install Python dependencies:

    pip3 install pyserial pyte usb-plug-notification-darwin py2app

Step 5. Run from source:

    sudo venv/bin/python main.py

Step 6. Build .app:

    rm -rf build dist
    python3 setup.py py2app

## Usage

### SPI

1. Insert SPI flash chip into CH341A socket (make sure 3.3V, not 5V!)
2. Set jumper to SPI mode
3. Connect CH341A to Mac
4. Open SPI tab, press Detect, chip name appears
5. Press Read to read chip into memory
6. Press Save to save dump to file
7. Press Write to write file to chip (with confirmation)
8. Press Verify to verify chip against file
9. Press Erase to erase chip (with confirmation)

### UART

1. Set jumper to UART mode
2. Connect CH341A to Mac
3. Open UART tab, select port, press Connect
4. Type commands in the terminal
5. Press Save log to save terminal output
6. Press Open in external terminal to use screen in Terminal.app

## Safety notes

- CH341A must be set to 3.3V, NOT 5V. 5V can damage SPI chips.
- Disconnect the target device from power before reading or writing SPI.
- Write and Erase operations are destructive. Make sure you have a backup.
- Verify after write is enabled by default. Keep it on to ensure data integrity.

## License

This project is licensed under the GNU General Public License v3.0 (GPLv3).

It uses libflashrom (GPLv2), which is compatible with GPLv3.

See LICENSE file for details.

## Author

Sushkov Yan (SYAO)

## Acknowledgments

- flashrom — for the excellent SPI programming library
- pyte — for terminal emulation
- pyserial — for serial port communication
