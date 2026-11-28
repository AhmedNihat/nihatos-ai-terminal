#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# N1BroX Universal Installer & Uninstaller
# ==============================================================================

readonly APP_NAME="n1brox"
readonly REPO_URL="https://github.com/AhmedNihat/linux-ai-terminal-n1brox.git"
readonly INSTALL_DIR="${HOME}/.local/share/n1brox-app"
readonly CONFIG_DIR="${HOME}/.config/n1brox-terminal"
readonly HISTORY_FILE="${HOME}/.n1brox_history"
readonly BIN_DIR="${HOME}/.local/bin"
readonly BIN_PATH="${BIN_DIR}/${APP_NAME}"
readonly DESKTOP_FILE="${HOME}/.local/share/applications/n1brox-terminal.desktop"
readonly DESKTOP_SHORTCUT="${HOME}/Desktop/n1brox-terminal.desktop"

log_info()  { printf "\033[1;36m[INFO]\033[0m %s\n" "$1"; }
log_ok()    { printf "\033[1;32m[OK]\033[0m %s\n" "$1"; }
log_warn()  { printf "\033[1;33m[WARN]\033[0m %s\n" "$1"; }
log_error() { printf "\033[1;31m[ERROR]\033[0m %s\n" "$1" >&2; }

read_tty() {
    local reply=""
    printf "%s" "$1" >/dev/tty
    IFS= read -r reply </dev/tty || reply=""
    printf "%s" "${reply}"
}

detect_system() {
    local os_name="Unknown Linux"
    local arch
    arch="$(uname -m)"
    if [[ -r /etc/os-release ]]; then
        # shellcheck disable=SC1091
        source /etc/os-release
        os_name="${PRETTY_NAME:-${NAME:-Unknown Linux}}"
    fi
    log_info "Detected OS   : ${os_name} (${arch})"
    log_info "Desktop Env   : ${XDG_CURRENT_DESKTOP:-Unknown}"
}

safe_remove_dir() {
    local target="$1"
    if [[ -z "${target}" || "${target}" == "/" || "${target}" == "${HOME}" ]]; then
        log_error "Refusing to remove unsafe path: '${target}'"
        exit 1
    fi
    if [[ -d "${target}" ]]; then
        rm -rf "${target}"
        log_ok "Removed directory: ${target}"
    else
        log_info "Directory not found (skipping): ${target}"
    fi
}

confirm_delete() {
    local target="$1" label="$2"
    [[ -e "${target}" ]] || return 0
    if [[ -r /dev/tty ]]; then
        local ans
        ans="$(read_tty $'\033[1;33m[PROMPT]\033[0m Also delete '"${label} (${target})? [y/N]: ")"
        if [[ "${ans}" =~ ^[Yy]$ ]]; then
            [[ -d "${target}" ]] && safe_remove_dir "${target}" || { rm -f "${target}"; log_ok "Removed: ${target}"; }
            return 0
        fi
    fi
    log_info "Kept ${label} at ${target}."
}

save_key_file() {
    local provider="$1" clean_val
    clean_val="$(printf "%s" "$2" | sed -e 's/^[[:space:]<>'\''"]*//' -e 's/[[:space:]<>'\''"]*$//')"
    [[ -n "${clean_val}" ]] || return 1
    printf "%s\n" "${clean_val}" > "${CONFIG_DIR}/${provider}_key"
    chmod 600 "${CONFIG_DIR}/${provider}_key"
}

INSTALL_USER_NAME=""

save_config_fields() {
    local user_val="$1" os_val="$2"
    [[ -n "${user_val}${os_val}" ]] || return 1
    N1_CFG="${CONFIG_DIR}/config.json" N1_USER="${user_val}" N1_OS="${os_val}" python3 - << 'PYCFG'
import json, os
from pathlib import Path

p = Path(os.environ["N1_CFG"])
try:
    data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    if not isinstance(data, dict):
        data = {}
except Exception:
    data = {}

if os.environ["N1_USER"]:
    data["user_name"] = os.environ["N1_USER"]
if os.environ["N1_OS"]:
    data["os_name"] = os.environ["N1_OS"]

p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
os.chmod(p, 0o600)
PYCFG
}

setup_initial_config() {
    [[ -r /dev/tty ]] || return 0
    echo ""
    echo "================================================================"
    echo "  N1BroX Quick Setup (Press Enter to skip any step)"
    echo "================================================================"
    echo "Skip now? You can configure everything anytime inside n1brox:"
    echo "  Your Name : setuser <YourName>"
    echo "  OS Name   : setname <CustomName>"
    echo "  API Keys  : ai key <groq|gemini|openrouter> <YOUR_API_KEY>"
    echo "  API Guide : ai key setup"
    echo ""

    local saved=() raw_user raw_os clean_user clean_os spec provider label val

    # 1. User's display name (used in "Hello Boss, <Name>!")
    raw_user="$(read_tty "1) Your Name (Enter to skip): ")"
    clean_user="$(printf "%s" "${raw_user}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

    # 2. Custom N1BroX OS name
    raw_os="$(read_tty "2) Custom N1BroX Name [N1BroX] (Enter to skip): ")"
    clean_os="$(printf "%s" "${raw_os}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

    if save_config_fields "${clean_user}" "${clean_os}"; then
        if [[ -n "${clean_user}" ]]; then
            INSTALL_USER_NAME="${clean_user}"
            saved+=("user=${clean_user}")
        fi
        [[ -n "${clean_os}" ]] && saved+=("os=${clean_os}")
    fi

    # 3. AI API Keys (optional)
    echo ""
    echo "3) AI API Keys (optional — any 1 key enables AI):"
    for spec in         "gemini|   Google (Gemini) API Key"         "groq|   Groq API Key"         "openrouter|   OpenRouter API Key"; do
        provider="${spec%%|*}"
        label="${spec#*|}"
        val="$(read_tty "${label} (Enter to skip): ")"
        if save_key_file "${provider}" "${val}"; then
            saved+=("${provider}_key")
        fi
    done

    echo ""
    if (( ${#saved[@]} > 0 )); then
        log_ok "Saved (${saved[*]}) securely in ${CONFIG_DIR}."
    else
        log_info "Skipped setup. Run 'setuser <Name>', 'setname <OS>', or 'ai key setup' inside n1brox."
    fi
}
clear_api_keys() {
    [[ -d "${CONFIG_DIR}" ]] || { log_info "No config directory found at ${CONFIG_DIR}."; return 0; }
    local removed=0 key_file
    for key_file in groq_key gemini_key openrouter_key; do
        if [[ -f "${CONFIG_DIR}/${key_file}" ]]; then
            rm -f "${CONFIG_DIR}/${key_file}"
            log_ok "Deleted saved key: ${key_file}"
            removed=1
        fi
    done
    if [[ "${removed}" -eq 0 ]]; then
        log_info "No saved API keys found in ${CONFIG_DIR}."
    fi
}

uninstall_app() {
    detect_system
    log_info "Starting N1BroX uninstallation..."
    safe_remove_dir "${INSTALL_DIR}"

    for f in "${BIN_PATH}" "${DESKTOP_FILE}" "${DESKTOP_SHORTCUT}" \
             "${HOME}/.local/share/applications/n1brox.desktop" "${HOME}/Desktop/n1brox.desktop" \
             "${HOME}/.local/share/applications/nihatos-terminal.desktop" "${HOME}/Desktop/nihatos-terminal.desktop" \
             "${HOME}/.local/share/applications/nihatos.desktop" "${HOME}/Desktop/nihatos.desktop"; do
        if [[ -f "${f}" ]]; then
            rm -f "${f}"
            log_ok "Removed: ${f}"
        fi
    done

    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "${HOME}/.local/share/applications" || true
    confirm_delete "${CONFIG_DIR}" "saved API keys & config"
    confirm_delete "${HISTORY_FILE}" "command history"
    log_ok "N1BroX has been completely uninstalled."
    exit 0
}

install_app() {
    local is_update="${1:-0}"
    detect_system
    log_info "Checking prerequisites..."
    for cmd in git python3; do
        command -v "${cmd}" >/dev/null 2>&1 || { log_error "Required command '${cmd}' is not installed."; exit 1; }
    done
    python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" || {
        log_error "Python 3.10+ is required (found: $(python3 --version 2>&1))."; exit 1;
    }
    python3 -c "import venv, ensurepip" >/dev/null 2>&1 || {
        log_error "Python venv/ensurepip modules are missing."
        log_info "On Debian/Ubuntu, install them with: apt install python3-venv"
        exit 1
    }

    mkdir -p "${HOME}/.local/share" "${HOME}/.local/share/applications" "${BIN_DIR}" "${CONFIG_DIR}"
    rm -f "${HOME}/.local/share/applications/n1brox.desktop" "${HOME}/Desktop/n1brox.desktop" \
          "${HOME}/.local/share/applications/nihatos.desktop" "${HOME}/Desktop/nihatos.desktop" \
          "${HOME}/.local/share/applications/nihatos-terminal.desktop" "${HOME}/Desktop/nihatos-terminal.desktop"

    if [[ -d "${INSTALL_DIR}" ]]; then
        if [[ -d "${INSTALL_DIR}/.git" ]]; then
            log_info "Existing N1BroX installation detected. Updating..."
            git -C "${INSTALL_DIR}" pull --ff-only
        else
            log_warn "${INSTALL_DIR} is not a valid git repo. Rebuilding cleanly..."
            safe_remove_dir "${INSTALL_DIR}"
            git clone "${REPO_URL}" "${INSTALL_DIR}"
        fi
    else
        log_info "Cloning N1BroX into ${INSTALL_DIR}..."
        git clone "${REPO_URL}" "${INSTALL_DIR}"
    fi
    chmod +x "${INSTALL_DIR}/install.sh" "${INSTALL_DIR}/run-gui.sh"

    log_info "Setting up Python virtual environment..."
    [[ -d "${INSTALL_DIR}/.venv" ]] || python3 -m venv "${INSTALL_DIR}/.venv"
    "${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip >/dev/null
    [[ -f "${INSTALL_DIR}/requirements.txt" ]] && "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"

    cat <<WRAPPER > "${BIN_PATH}"
#!/usr/bin/env bash
set -euo pipefail
case "\${1:-}" in
    uninstall) exec bash "${INSTALL_DIR}/install.sh" --uninstall ;;
    key-clear) exec bash "${INSTALL_DIR}/install.sh" --clear-keys ;;
    update)    exec bash "${INSTALL_DIR}/install.sh" --update ;;
    *)         cd "${HOME}"; exec "${INSTALL_DIR}/.venv/bin/python" "${INSTALL_DIR}/gui.py" "\$@" ;;
esac
WRAPPER
    chmod +x "${BIN_PATH}"

    local app_icon="utilities-terminal" candidate
    for candidate in "${INSTALL_DIR}/assets/icon.png" "${INSTALL_DIR}/assets/logo.png" "${INSTALL_DIR}/assets/n1brox.png"; do
        [[ -f "${candidate}" ]] && { app_icon="${candidate}"; break; }
    done

    cat <<DESKTOP > "${DESKTOP_FILE}"
[Desktop Entry]
Version=1.0
Type=Application
Name=N1BroX Terminal
Comment=AI-Native Linux Terminal
Exec=${BIN_PATH}
Icon=${app_icon}
Terminal=false
Categories=System;TerminalEmulator;Development;
StartupNotify=true
DESKTOP
    chmod +x "${DESKTOP_FILE}"
    [[ -d "${HOME}/Desktop" ]] && { cp "${DESKTOP_FILE}" "${DESKTOP_SHORTCUT}"; chmod +x "${DESKTOP_SHORTCUT}"; }
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "${HOME}/.local/share/applications" || true

    if [[ "${is_update}" -eq 0 ]]; then
        setup_initial_config
    fi

    if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
        log_warn "${BIN_DIR} is not in your PATH. Run:"
        echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
    fi

    if [[ -n "${INSTALL_USER_NAME:-}" ]]; then
        log_ok "Hello Boss, ${INSTALL_USER_NAME}! N1BroX installed successfully!"
    else
        log_ok "N1BroX installed successfully!"
    fi
    echo "  Run app       : n1brox"
    echo "  Update app    : n1brox update"
    echo "  Clear API keys: n1brox key-clear"
    echo "  Uninstall app : n1brox uninstall"
}

case "${1:-}" in
    --uninstall|uninstall) uninstall_app ;;
    --clear-keys|key-clear) clear_api_keys ;;
    --update|update) install_app 1 ;;
    *) install_app 0 ;;
esac
