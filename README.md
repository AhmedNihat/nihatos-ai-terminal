<div align="center">

# NIHAT.O.S — AI-Native Linux Terminal

**A modern, privacy-first Linux terminal emulator with a persistent Bash PTY, live system telemetry, smart AI command fixing, built-in file preview, and dual personas.**

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

## Demo

<div align="center">

[![Watch Nihat.O.S Demo on YouTube](https://img.youtube.com/vi/f-jkptbtydw/maxresdefault.jpg)](https://www.youtube.com/watch?v=f-jkptbtydw)

*Click the preview above to watch the full demo on YouTube.*

</div>

---

## Screenshots

| Nihat.O.S Mode | U.L.T.R.O.N Mode |
| :---: | :---: |
| ![Nihat.O.S Mode](assets/nihatos-ss.png) | ![U.L.T.R.O.N Mode](assets/ultron-ss.png) |

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

---

## Security & Privacy by Design

Running AI inside a system terminal demands strict guardrails. **Nihat.O.S** is built so you stay in full control of your machine and data at all times:

- **Zero Auto-Execution (Human-in-the-Loop)**  
  Nihat.O.S never executes an AI-generated command automatically. Every suggestion from `ai do` or `ai fix` is displayed clearly and requires explicit manual `y` / `n` confirmation before touching your shell.
- **Pre-Execution Bash Syntax Guard**  
  Commands are validated before being sent to the live PTY, catching unclosed quotes, trailing backslashes, or broken blocks early so malformed input never hangs or misfires in your session.
- **Masked `sudo` Password Handling**  
  Password prompts are masked directly in the input bar and are never echoed to the terminal buffer, saved to shell history, or sent to any AI provider.
- **Strict Local Storage for Keys & History**  
  API keys (`groq_key`, `gemini_key`, `openrouter_key`), user settings (`config.json`), and command history (`~/.nihatos_history`) stay strictly on your local machine inside `~/.config/nihatos-terminal/` with owner-only permissions (`chmod 600`)—completely outside the repository.
- **Read-Only Diagnostics & No Background Tracking**  
  Hardware telemetry probes are strictly read-only. Nihat.O.S has no analytics, no cloud account requirement, and no background data collection—external API calls only happen when you explicitly invoke an `ai` command.
- **100% Open Source & Auditable (GPLv3)**  
  No closed-source binaries or hidden wrappers. You can inspect every line of Python code before running it.

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

- **Smart Input Recommendations & Live Autocomplete**  
  A real-time dropdown suggestion popup appears as you type, recommending built-in commands, `$PATH` executables, local files/directories, and saved waypoints. Navigate with `Up`/`Down`, press `Tab` or `Enter` (or click) to complete, and press `Esc` to dismiss.
- **Interactive History Search (`Ctrl+R`)**  
  Search through your persistent command history live inside the suggestion popup without leaving the input bar.
- **Universal Pre-Execution Bash Syntax Guard**  
  Automatically validates commands before sending them to the live PTY. Unclosed quotes, trailing `\` continuations, incomplete heredocs, or broken blocks are caught instantly with a `[Syntax Error]` prompt instead of hanging the shell—ready to repair in one step with `ai fix`.
- **Persistent Bash PTY Engine**  
  Runs a true interactive Bash PTY session with OSC marker parsing, live working-directory tracking, active Git branch (`[⎇ main]`) and Python virtualenv (`(venv)`) badges, and masked `sudo` password entry.
- **Auto-Expanding Multi-Line Code Input**  
  Paste multi-line shell loops, Python heredocs, or Docker commands directly into the input bar. Press `Shift+Enter` for newlines and `Enter` to execute, with a top-aligned prompt that stays steady while editing multi-line blocks.
- **Built-in File, Image & Directory Previewer**  
  Run `preview <path>`, `view <path>`, or `less <file>` to inspect files inside Nihat.O.S without spawning external windows:
  - **Code & Text:** Line-number gutter, live search (`Ctrl+F` or `/`), word-wrap toggle, one-click Copy All, and 2 MB large-file truncation guard.
  - **Binary Files:** Automatic hex + ASCII dump instead of garbled output.
  - **Images & Directories:** Native image viewer (`.png`, `.jpg`, `.webp`, `.svg`, `.gif`) and clean directory listings.
  - **Quick Close:** Press `q` or `Esc` to close. Piped commands (`cat file | less`) continue running natively in Bash.
- **Directory Waypoints, Ports & Hardware Powertools**  
  Bookmark frequent directories (`go <mark>` or one-click sidebar Waypoints), inspect open network ports, monitor serial/USB ports, and view live CPU, RAM, temperature, fan RPM, and battery telemetry in a pauseable HUD bar with real-time USB hotplug alerts.
- **Multi-Tab Workspace & Desktop Integration**  
  Movable, isolated multi-tab terminal sessions (`Ctrl+T` / `Ctrl+W`) with animated HUD indicators and proper Wayland/X11 taskbar icon grouping (`setDesktopFileName` + `StartupWMClass`).

---

## Quick Commands & Shortcuts

| Command / Shortcut | Action |
| :--- | :--- |
| `Tab` / `Up` / `Down` | Trigger and navigate live command, path, and waypoint recommendations |
| `Ctrl + R` | Open live interactive command history search |
| `ai <question>` | Ask the AI copilot (auto-injects live hardware/OS telemetry when relevant) |
| `ai do <task>` | Generate one safe, distro-specific Bash command from plain English |
| `ai fix` | Diagnose the last failed command or syntax error and propose a fix |
| `y` / `n` *(after AI suggestion)* | Run or cancel the pending AI-generated command |
| `mode nihatos` / `mode ultron` | Switch between Nihat.O.S and U.L.T.R.O.N modes |
| `Ctrl + M` | Toggle persona and theme |
| `Ctrl + T` / `Ctrl + W` | Open a new terminal tab / close the current tab |
| `Ctrl + L` / `Ctrl + K` | Clear terminal output / focus the command input bar |
| `go <mark>` | Jump directly to a bookmarked waypoint directory |
| `preview <path>` / `view <path>` / `less <file>` | Open built-in code, text, hex, image, or directory previewer |
| `tui <cmd>` | Launch an interactive TUI app in your external terminal |
| `sys` | Display quick system scan (kernel, uptime, memory) |
| `save [filename]` | Export current terminal output to a file (default: `nihatos-log.txt`) |
| `copy [N \| all]` | Copy last `N` lines (default `25`) or full output to clipboard |
| `Shift + Enter` | Insert a newline in the multi-line command input |
| `Ctrl + F` or `/` *(in Preview)* | Search inside an opened file |
| `help` | List all built-in commands and shortcuts |

---

## Installation & Setup (Step-by-Step)

Nihat.O.S runs inside an isolated Python virtual environment (`.venv`) so it **never pollutes or breaks your system Python**. Follow these steps on any Linux PC or laptop:

### Step 1: Check Python & Install System Prerequisites

First, verify that you have **Python 3.10 or newer**:
```bash
python3 --version
```

Next, install `git`, `python3-venv`, `pip`, and the required Qt6 display libraries for your Linux distribution:

- **Debian / Ubuntu / Linux Mint / Pop!_OS / Kali:**
  ```bash
  sudo apt update
  sudo apt install -y git python3 python3-venv python3-pip libxcb-cursor0 libegl1 libgl1 libxkbcommon-x11-0
  ```
- **Fedora / RHEL / Nobara / AlmaLinux:**
  ```bash
  sudo dnf install -y git python3 python3-pip qt6-qtbase-gui xcb-util-cursor
  ```
- **Arch Linux / Manjaro / EndeavourOS / CachyOS:**
  ```bash
  sudo pacman -S --needed git python python-pip qt6-base xcb-util-cursor
  ```
- **openSUSE (Tumbleweed / Leap):**
  ```bash
  sudo zypper install -y git python3 python3-pip libqt6-qtbase xcb-util-cursor0
  ```

---

### Step 2: Clone the Repository & Enter the Project Folder

> **Important:** Make sure to run `cd nihatos-ai-terminal` before running any setup or launch commands.

```bash
git clone [https://github.com/AhmedNihat/nihatos-ai-terminal.git](https://github.com/AhmedNihat/nihatos-ai-terminal.git)
cd nihatos-ai-terminal
```

---

### Step 3: Create Virtual Environment & Install Python Packages (`PyQt6` & Dependencies)

#### Option A: Automated Setup (Recommended)
This script automatically creates `.venv` and installs all required Python packages (`PyQt6`, `psutil`, `requests`, etc.) from `requirements.txt`:

```bash
chmod +x scripts/setup_venv.sh run-gui.sh
./scripts/setup_venv.sh
```

#### Option B: Manual Setup (Using `venv` & `pip`)
If you prefer to create the virtual environment and install packages manually:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

*(Optional verification — confirm `PyQt6` is installed inside `.venv`:)*
```bash
.venv/bin/python -c "import PyQt6; print('PyQt6 OK')"
```

---

### Step 4: Launch Nihat.O.S

Always launch using `./run-gui.sh` (or `.venv/bin/python gui.py`) so it uses the `.venv` environment instead of system Python:

```bash
./run-gui.sh
```

*(Alternative direct launch command:)*
```bash
.venv/bin/python gui.py
```

---

### Step 5: Get & Configure a Free AI API Key

Nihat.O.S supports **three free-tier AI providers with automatic fallback** in this priority order: **Groq -> Google Gemini -> OpenRouter**. You only need **one** key to start (adding more enables automatic failover).

#### A. Get a Free API Key
- **Groq (Recommended — fastest):** Go to [console.groq.com/keys](https://console.groq.com/keys), sign in, click **Create API Key**, and copy the key (`gsk_...`).
- **Google Gemini:** Go to [aistudio.google.com/apikey](https://aistudio.google.com/apikey), sign in with Google, click **Create API key**, and copy the key (`AIza...`).
- **OpenRouter (Free models fallback):** Go to [openrouter.ai/keys](https://openrouter.ai/keys), sign in, click **Create Key**, and copy the key (`sk-or-...`).

#### B. Save Key in `~/.config/nihatos-terminal/`
All keys and user settings (`config.json`) stay privately inside `~/.config/nihatos-terminal/`, completely outside the repository:

```bash
mkdir -p ~/.config/nihatos-terminal

# Primary: Groq (recommended)
echo "YOUR_GROQ_API_KEY" > ~/.config/nihatos-terminal/groq_key
chmod 600 ~/.config/nihatos-terminal/groq_key

# Optional fallback: Google Gemini
echo "YOUR_GEMINI_API_KEY" > ~/.config/nihatos-terminal/gemini_key
chmod 600 ~/.config/nihatos-terminal/gemini_key

# Optional fallback: OpenRouter
echo "YOUR_OPENROUTER_API_KEY" > ~/.config/nihatos-terminal/openrouter_key
chmod 600 ~/.config/nihatos-terminal/openrouter_key
```

---

## Troubleshooting (Common Installation Issues)

### 1. `ModuleNotFoundError: No module named 'PyQt6'`
This happens if you ran `python3 gui.py` directly outside `.venv`, or if `.venv` was created before `python3-venv` was installed.

**Fix:** Rebuild `.venv` inside the project folder and launch with `.venv`:
```bash
cd ~/nihatos-ai-terminal
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install PyQt6
.venv/bin/python gui.py
```

**Debian / Ubuntu Fallback (if `pip install PyQt6` fails on your system):**
Install Debian's native `python3-pyqt6` package and let `.venv` inherit it:
```bash
sudo apt install -y python3-pyqt6
cd ~/nihatos-ai-terminal
rm -rf .venv
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
./run-gui.sh
```

### 2. `error: externally-managed-environment` (PEP 668 on Debian 12+ / Ubuntu 24.04+)
Modern Debian/Ubuntu blocks global `pip install`. Always use `.venv/bin/pip install ...` (never plain `pip install ...`) as shown in Step 3.

### 3. `qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`
Your system is missing Qt6 XCB display libraries. Run the prerequisite command for your distro from **Step 1** (especially `libxcb-cursor0` on Debian/Ubuntu or `xcb-util-cursor` on Fedora/Arch).

### 4. `chmod: cannot access 'scripts/setup_venv.sh': No such file or directory`
You are still in your home directory (`~`). Enter the cloned folder first:
```bash
cd ~/nihatos-ai-terminal
```

---

## Add to Linux App Menu & Desktop (KDE / GNOME / XFCE)

Run this from inside the `nihatos-ai-terminal` folder to add **Nihat.O.S** to your application launcher:

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
