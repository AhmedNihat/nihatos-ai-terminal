#!/usr/bin/env bash
set -e

REPO_URL="https://github.com/AhmedNihat/nihatos-ai-terminal.git"
INSTALL_DIR="$HOME/.local/share/nihatos-terminal"
CONFIG_DIR="$HOME/.config/nihatos-terminal"
BIN_DIR="$HOME/.local/bin"

echo "◈ Installing Nihat.O.S AI-Native Linux Terminal..."

# 1. Detect distro & install system prerequisites
if command -v apt &>/dev/null; then
    echo "▸ Detected Debian/Ubuntu (apt). Installing prerequisites..."
    sudo apt update
    sudo apt install -y git python3 python3-venv python3-pip libxcb-cursor0 libegl1 libgl1 libxkbcommon-x11-0
elif command -v dnf &>/dev/null; then
    echo "▸ Detected Fedora/RHEL (dnf). Installing prerequisites..."
    sudo dnf install -y git python3 python3-pip qt6-qtbase-gui xcb-util-cursor
elif command -v pacman &>/dev/null; then
    echo "▸ Detected Arch Linux (pacman). Installing prerequisites..."
    sudo pacman -S --needed --noconfirm git python python-pip qt6-base xcb-util-cursor
elif command -v zypper &>/dev/null; then
    echo "▸ Detected openSUSE (zypper). Installing prerequisites..."
    sudo zypper install -y git python3 python3-pip libqt6-qtbase xcb-util-cursor0
elif command -v apk &>/dev/null; then
    echo "▸ Detected Alpine Linux (apk). Installing prerequisites..."
    sudo apk add git python3 py3-pip qt6-qtbase-x11 xcb-util-cursor
else
    echo "⚠ Unknown package manager. Ensure git, python3, venv, and Qt6 libraries are installed."
fi

# 2. Clone or update repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "▸ Updating existing installation..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    echo "▸ Cloning repository into $INSTALL_DIR..."
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# 3. Create isolated virtual environment & install Python packages
echo "▸ Setting up Python virtual environment (.venv)..."
cd "$INSTALL_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
chmod +x "$INSTALL_DIR/run-gui.sh"

# 4. Interactive Personalization (Custom OS Name & Optional AI Keys)
mkdir -p "$CONFIG_DIR"
CUSTOM_NAME="Nihat.O.S"

if [ -t 0 ] || [ -e /dev/tty ]; then
    echo ""
    echo "◈ Personalize Your Terminal:"
    read -r -p "  ▸ Enter your custom OS name (Press Enter for 'Nihat.O.S', e.g. Saad.O.S): " INPUT_NAME </dev/tty
    if [ -n "$INPUT_NAME" ]; then
        CUSTOM_NAME="$INPUT_NAME"
    fi

    python3 - "$CONFIG_DIR/config.json" "$CUSTOM_NAME" <<'PY'
import json, sys
from pathlib import Path
p, name = Path(sys.argv[1]), sys.argv[2]
data = {}
if p.is_file():
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        data = {}
data["os_name"] = name
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
    echo "    ✓ OS identity set to: $CUSTOM_NAME"

    echo ""
    echo "◈ Optional AI API Key Setup (Press Enter to skip — or run 'ai setup' inside the app later):"
    read -r -s -p "  ▸ Groq API Key (recommended, free at console.groq.com): " GROQ_KEY </dev/tty
    echo ""
    if [ -n "$GROQ_KEY" ]; then
        printf "%s\n" "$GROQ_KEY" > "$CONFIG_DIR/groq_key"
        chmod 600 "$CONFIG_DIR/groq_key"
        echo "    ✓ Groq key saved securely."
    fi

    read -r -s -p "  ▸ Google Gemini API Key (optional, aistudio.google.com): " GEMINI_KEY </dev/tty
    echo ""
    if [ -n "$GEMINI_KEY" ]; then
        printf "%s\n" "$GEMINI_KEY" > "$CONFIG_DIR/gemini_key"
        chmod 600 "$CONFIG_DIR/gemini_key"
        echo "    ✓ Gemini key saved securely."
    fi
fi

# 5. Create global 'nihatos' CLI wrapper (with built-in update & uninstall)
mkdir -p "$BIN_DIR"
cat <<'CLI' > "$BIN_DIR/nihatos"
#!/usr/bin/env bash
set -e
INSTALL_DIR="$HOME/.local/share/nihatos-terminal"

case "${1:-}" in
    update)
        echo "◈ Updating Nihat.O.S..."
        git -C "$INSTALL_DIR" pull --ff-only
        "$INSTALL_DIR/.venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"
        echo "✅ Updated successfully!"
        ;;
    uninstall)
        echo "◈ Removing Nihat.O.S..."
        rm -rf "$INSTALL_DIR"
        rm -f "$HOME/.local/bin/nihatos"
        rm -f "$HOME/.local/share/applications/nihatos-terminal.desktop"
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        echo "✅ Uninstalled. (Your config & keys in ~/.config/nihatos-terminal/ were kept safe.)"
        ;;
    *)
        exec "$INSTALL_DIR/run-gui.sh" "$@"
        ;;
esac
CLI
chmod +x "$BIN_DIR/nihatos"

# 6. Add to Linux App Menu (.desktop)
mkdir -p "$HOME/.local/share/applications"
cat <<DESKTOP > "$HOME/.local/share/applications/nihatos-terminal.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=$CUSTOM_NAME
GenericName=AI Native Terminal
Comment=AI-Native Linux Terminal System
Exec=$INSTALL_DIR/run-gui.sh
Path=$HOME
Icon=utilities-terminal
Terminal=false
Categories=System;TerminalEmulator;Utility;
Keywords=terminal;shell;ai;nihatos;ultron;jarvis;
StartupNotify=true
StartupWMClass=nihatos-terminal
DESKTOP
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "✅ $CUSTOM_NAME installed successfully!"
echo "  ▸ Launch:    nihatos  (or open '$CUSTOM_NAME' from your App Menu)"
echo "  ▸ Update:    nihatos update"
echo "  ▸ Uninstall: nihatos uninstall"
echo "  ▸ AI Setup:  type 'ai setup' or 'setname <Name>' anytime inside the terminal"

if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo ""
    echo "ℹ Tip: Add ~/.local/bin to your PATH to run 'nihatos' from anywhere:"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
fi
