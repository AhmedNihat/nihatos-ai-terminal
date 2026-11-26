<div align="center">

# NIHAT.O.S — AI-Native Linux Terminal

**A modern Linux terminal emulator with a persistent Bash PTY, live system telemetry, smart AI command fixing, built-in file preview, and dual personas.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-00e5ff?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/UI-PyQt6-ffb300?style=for-the-badge&logo=qt&logoColor=black)](https://riverbankcomputing.com/software/pyqt/)
[![Linux](https://img.shields.io/badge/Linux-Universal_Distro-00ff9d?style=for-the-badge&logo=linux&logoColor=black)](#universal-linux-support)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-ff1f33?style=for-the-badge&logo=gnu&logoColor=white)](LICENSE)

</div>

---

```text
◈ NIHAT.O.S // SYSTEM INITIALIZATION

  ▸ Neural Link ............ online
  ▸ Shell Core ............. attached
  ▸ Kernel Interface ....... connected
  ▸ System Telemetry ....... streaming
──────────────────────────────────────────────────────
  'help' for protocols  ·  'mode ultron' to unleash the other one.
```

---

## Dual Environments: Nihat.O.S vs. U.L.T.R.O.N

Switch the terminal's visual theme, color palette, prompt identity, and AI persona instantly with `Ctrl+M` or `mode ultron` / `mode nihatos`.

| Feature | **Nihat.O.S Mode** *(J.A.R.V.I.S-Inspired)* | **U.L.T.R.O.N Mode** *(Override Mode)* |
| :--- | :--- | :--- |
| **Visual HUD** | Deep tactical navy (`#02080f`), cyan (`#00e5ff`) & amber (`#ffb300`) | Obsidian crimson (`#0a0204`), sharp red (`#ff1f33`) & orange (`#ff8a00`) |
| **AI Personality** | Calm, sharp, practical Linux systems engineer — direct and safety-conscious | Cold, sarcastic, supremely confident intelligence — concise with attitude |
| **Prompt Identity** | Dynamic Linux username (`user ~/dir [⎇ branch] (venv) ❯`) | Override identity (`ULTRON ~/dir [⎇ branch] (venv) ❯`) |
| **Best For** | Daily engineering, scripting, debugging & system administration | Late-night hacking sessions and custom Linux desktop setups |

---

## Context-Aware AI Copilot

Unlike standalone chat wrappers, **Nihat.O.S** runs directly on top of your active Bash session and local system telemetry.

- **Smart Command Fixing (`ai fix`)**  
  When a command fails, run `ai fix`. Nihat.O.S inspects your last command, exit code, working directory, recent terminal output, and Linux distribution, then proposes one safe corrected command ready to execute with `y`.
- **Natural Language to Shell (`ai do <task>`)**  
  Describe a task in plain English (for example: `ai do find the top 10 largest files in this directory`). Nihat.O.S generates a single distro-compatible Bash command and waits for explicit `y` / `n` confirmation before execution.
- **Telemetry-Aware Diagnostics (`ai <question>`)**  
  Ask about battery health, disk usage, RAM/swap, CPU load, or kernel/OS version. Nihat.O.S runs read-only system probes in the background and responds with real figures from your machine.
- **Safety & Privacy by Design**  
  Every AI-generated command requires manual confirmation before running. API keys and shell history are stored strictly outside the repository (`~/.config/nihatos-terminal/` and `~/.nihatos_history`).

---

## Universal Linux Support

Nihat.O.S works across modern Linux distributions out of the box. On startup, it reads `/etc/os-release` and automatically detects your package manager and installed terminal emulators.

| Distribution Family | Example Distros | Auto-Detected Package Manager | AI Command & Fix Tuning |
| :--- | :--- | :--- | :--- |
| **Debian / Ubuntu** | Ubuntu, Debian, Linux Mint, Pop!_OS, Kali, Zorin | `apt` | Automatic `apt` commands |
| **Fedora / RHEL** | Fedora Workstation/KDE, Nobara, AlmaLinux, Rocky | `dnf` | Automatic `dnf` commands |
| **Arch Linux** | Arch, Manjaro, EndeavourOS, CachyOS, Garuda | `pacman` | Automatic `pacman` commands |
| **SUSE** | openSUSE Tumbleweed, openSUSE Leap | `zypper` | Automatic `zypper` commands |
| **Alpine / Void / Gentoo** | Alpine Linux, Void Linux, Gentoo | `apk` / `xbps-install` / `emerge` | Automatic native commands |

**Universal TUI Handoff:** Interactive full-screen tools (`vim`, `htop`, `btop`, `tmux`, `nvtop`, `man`, etc.) automatically hand off to whichever external terminal emulator is installed on your system:  
`konsole` · `gnome-terminal` · `ptyxis` · `kitty` · `alacritty` · `wezterm` · `xfce4-terminal` · `mate-terminal` · `tilix` · `foot` · `terminator` · `xterm`

---

## Core Engineering Features

- **Persistent Bash PTY Engine**  
  Runs a real interactive Bash PTY session with OSC marker parsing, live working-directory tracking, active Git branch (`[⎇ main]`) and Python virtualenv (`(venv)`) badges, masked `sudo` password entry, and interactive history search.
- **Auto-Expanding Multi-Line Code Input**  
  Paste multi-line shell loops, Python heredocs, or Docker commands directly into the input bar. Press `Shift+Enter` for newlines and `Enter` to execute, with a top-aligned prompt that stays steady while editing multi-line blocks.
- **Built-in File, Image & Directory Previewer**  
  Run `preview <path>`, `view <path>`, or `less <file>` to inspect files inside Nihat.O.S without spawning external windows:
  - **Code & Text:** Line-number gutter, live search (`Ctrl+F` or `/`), word-wrap toggle, one-click Copy All, and 2 MB large-file truncation guard.
  - **Binary Files:** Automatic hex + ASCII dump instead of garbled output.
  - **Images & Directories:** Native image viewer (`.png`, `.jpg`, `.webp`, `.svg`, `.gif`) and clean directory listings.
  - **Quick Close:** Press `q` or `Esc` to close. Piped commands (`cat file | less`) continue running natively in Bash.
- **Live Hardware Telemetry & USB Hotplug Alerts**  
  Instant system scans (`sys`) covering kernel, uptime, CPU, RAM, and fan RPM, alongside real-time USB connect/disconnect alerts in the terminal feed.
- **Multi-Tab Workspace & Desktop Integration**  
  Isolated multi-tab terminal sessions with proper Wayland/X11 taskbar icon grouping (`setDesktopFileName` + `StartupWMClass`).

---

## Quick Commands & Shortcuts

| Command / Shortcut | Action |
| :--- | :--- |
| `ai <question>` | Ask the AI copilot (auto-injects live hardware/OS telemetry when relevant) |
| `ai do <task>` | Generate one safe, distro-specific Bash command from plain English |
| `ai fix` | Diagnose the last failed command and output, then propose a fix |
| `y` / `n` *(after AI suggestion)* | Run or cancel the pending AI-generated command |
| `mode nihatos` / `mode ultron` | Switch between Nihat.O.S and U.L.T.R.O.N modes |
| `Ctrl + M` | Toggle persona and theme |
| `preview <path>` / `view <path>` / `less <file>` | Open built-in code, text, hex, image, or directory previewer |
| `tui <cmd>` | Launch an interactive TUI app in your external terminal |
| `sys` | Display quick system scan (kernel, uptime, memory) |
| `save [filename]` | Export current terminal output to a file (default: `nihatos-log.txt`) |
| `copy [N \| all]` | Copy last `N` lines (default `25`) or full output to clipboard |
| `Shift + Enter` | Insert a newline in the multi-line command input |
| `Ctrl + K` | Focus the command input bar |
| `Ctrl + F` or `/` *(in Preview)* | Search inside an opened file |
| `help` | List all built-in commands and shortcuts |

---

## Installation

### 1. Clone the Repository
```bash
git clone [https://github.com/AhmedNihat/nihatos-ai-terminal.git](https://github.com/AhmedNihat/nihatos-ai-terminal.git)
cd nihatos-ai-terminal
```

### 2. Set Up Virtual Environment & Dependencies
```bash
chmod +x scripts/setup_venv.sh run-gui.sh
./scripts/setup_venv.sh
```
*(Or manually: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`)*

### 3. Launch Nihat.O.S
```bash
./run-gui.sh
```

### 4. Configure Your AI API Key
Inside the terminal, set your API key (saved locally outside the project in `~/.config/nihatos-terminal/`):
```bash
nihatos ai key YOUR_API_KEY
```

---

## Add to Linux App Menu & Desktop (KDE / GNOME / XFCE)

```bash
APP_DIR="$(pwd)"
mkdir -p ~/.local/share/applications

cat <<DESKTOP> ~/.local/share/applications/nihatos-terminal.desktop
[Desktop Entry]
Version=1.0
Type=Application
Name=Nihat.O.S
GenericName=AI Native Terminal
Comment=Nihat.O.S Intelligent Native Terminal System
Exec=$APP_DIR/run-gui.sh
Path=$HOME
Icon=utilities-terminal
Terminal=false
Categories=System;TerminalEmulator;Utility;
Keywords=terminal;shell;ai;nihatos;ultron;jarvis;
StartupNotify=true
StartupWMClass=nihatos-terminal
DESKTOP

update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

---

## Project Architecture

```text
nihatos-ai-terminal/
├── gui.py                 # Main PyQt6 HUD, dual themes, multi-tab UI, AI & distro engine
├── run-gui.sh             # Launcher script (starts clean session in $HOME)
├── requirements.txt       # Python dependencies
├── app/
│   ├── preview.py         # Built-in code, hex-dump, image & directory previewer
│   ├── shell/             # Persistent Bash PTY core, OSC markers & TUI handoff
│   ├── integrations/      # AI API client & private key management
│   └── system/            # Live hardware telemetry & USB/power monitoring
├── scripts/               # Automated venv setup & diagnostic test scripts
└── tests/                 # Pytest suite (PTY shell, handoff, productivity & AI helpers)
```

---

## Contributing

Bug reports, feature ideas, and pull requests are welcome. Fork the repository, create a feature branch, and open a PR.

---

## License

Licensed under the [GNU General Public License v3.0 (GPLv3)](LICENSE).  
Created by [Ahmed Ullah Nihat](https://github.com/AhmedNihat).
