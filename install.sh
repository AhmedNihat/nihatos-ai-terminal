#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Nihat.O.S Universal Installer & Uninstaller
# ==============================================================================

readonly APP_NAME="nihatos"
readonly REPO_URL="https://github.com/AhmedNihat/nihatos-ai-terminal.git"
readonly INSTALL_DIR="${HOME}/.local/share/nihatos-app"
readonly CONFIG_DIR="${HOME}/.config/nihatos-terminal"
readonly BIN_DIR="${HOME}/.local/bin"
readonly BIN_PATH="${BIN_DIR}/${APP_NAME}"
readonly DESKTOP_FILE="${HOME}/.local/share/applications/nihatos-terminal.desktop"
readonly DESKTOP_SHORTCUT="${HOME}/Desktop/nihatos-terminal.desktop"

log_info()  { printf "\033[1;36m[INFO]\033[0m %s\n" "$1"; }
log_ok()    { printf "\033[1;32m[OK]\033[0m %s\n" "$1"; }
log_warn()  { printf "\033[1;33m[WARN]\033[0m %s\n" "$1"; }
log_error() { printf "\033[1;31m[ERROR]\033[0m %s\n" "$1" >&2; }

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

clear_api_keys() {
    if [[ ! -d "${CONFIG_DIR}" ]]; then
        log_info "No config directory found at ${CONFIG_DIR}."
        return 0
    fi

    local removed=0
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
    log_info "Starting Nihat.O.S uninstallation..."

    safe_remove_dir "${INSTALL_DIR}"

    for f in "${BIN_PATH}" "${DESKTOP_FILE}" "${DESKTOP_SHORTCUT}" \
             "${HOME}/.local/share/applications/nihatos.desktop" \
             "${HOME}/Desktop/nihatos.desktop"; do
        if [[ -f "${f}" ]]; then
            rm -f "${f}"
            log_ok "Removed: ${f}"
        fi
    done

    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "${HOME}/.local/share/applications" || true

    if [[ -d "${CONFIG_DIR}" ]]; then
        printf "\033[1;33m[PROMPT]\033[0m Also delete saved API keys & config (%s)? [y/N]: " "${CONFIG_DIR}"
        read -r answer </dev/tty || answer="n"
        if [[ "${answer}" =~ ^[Yy]$ ]]; then
            safe_remove_dir "${CONFIG_DIR}"
        else
            log_info "Kept config & API keys at ${CONFIG_DIR}."
        fi
    fi

    log_ok "Nihat.O.S has been completely uninstalled."
    exit 0
}

install_app() {
    detect_system
    log_info "Checking prerequisites..."
    for cmd in git python3; do
        if ! command -v "${cmd}" >/dev/null 2>&1; then
            log_error "Required command '${cmd}' is not installed."
            exit 1
        fi
    done

    mkdir -p "${HOME}/.local/share" "${HOME}/.local/share/applications" "${BIN_DIR}" "${CONFIG_DIR}"

    # Remove legacy desktop files if present
    rm -f "${HOME}/.local/share/applications/nihatos.desktop" "${HOME}/Desktop/nihatos.desktop"

    # Strict directory check: Update if valid git repo, else clean clone
    if [[ -d "${INSTALL_DIR}" ]]; then
        if [[ -d "${INSTALL_DIR}/.git" ]]; then
            log_info "Existing Nihat.O.S installation detected. Updating..."
            git -C "${INSTALL_DIR}" pull --ff-only
        else
            log_warn "${INSTALL_DIR} is not a valid git repo. Rebuilding cleanly..."
            safe_remove_dir "${INSTALL_DIR}"
            git clone "${REPO_URL}" "${INSTALL_DIR}"
        fi
    else
        log_info "Cloning Nihat.O.S into ${INSTALL_DIR}..."
        git clone "${REPO_URL}" "${INSTALL_DIR}"
    fi

    # Setup isolated Python virtual environment
    log_info "Setting up Python virtual environment..."
    if [[ ! -d "${INSTALL_DIR}/.venv" ]]; then
        python3 -m venv "${INSTALL_DIR}/.venv"
    fi

    "${INSTALL_DIR}/.venv/bin/pip" install --upgrade pip >/dev/null
    if [[ -f "${INSTALL_DIR}/requirements.txt" ]]; then
        "${INSTALL_DIR}/.venv/bin/pip" install -r "${INSTALL_DIR}/requirements.txt"
    fi

    # Create CLI wrapper launcher (points to gui.py)
    cat <<WRAPPER > "${BIN_PATH}"
#!/usr/bin/env bash
set -euo pipefail

case "\${1:-}" in
    uninstall)
        exec "${INSTALL_DIR}/install.sh" --uninstall
        ;;
    key-clear)
        exec "${INSTALL_DIR}/install.sh" --clear-keys
        ;;
    update)
        exec "${INSTALL_DIR}/install.sh"
        ;;
    *)
        cd "${INSTALL_DIR}"
        exec "${INSTALL_DIR}/.venv/bin/python" "${INSTALL_DIR}/gui.py" "\$@"
        ;;
esac
WRAPPER
    chmod +x "${BIN_PATH}"

    # Pick custom icon from assets/ if available, else default terminal icon
    local app_icon="utilities-terminal"
    for candidate in "${INSTALL_DIR}/assets/icon.png" "${INSTALL_DIR}/assets/logo.png" "${INSTALL_DIR}/assets/nihatos.png"; do
        if [[ -f "${candidate}" ]]; then
            app_icon="${candidate}"
            break
        fi
    done

    # Create App Menu & Desktop shortcut (matches gui.py setDesktopFileName)
    cat <<DESKTOP > "${DESKTOP_FILE}"
[Desktop Entry]
Version=1.0
Type=Application
Name=Nihat.O.S Terminal
Comment=AI-Native Linux Terminal
Exec=${BIN_PATH}
Icon=${app_icon}
Terminal=false
Categories=System;TerminalEmulator;Development;
StartupNotify=true
DESKTOP
    chmod +x "${DESKTOP_FILE}"

    if [[ -d "${HOME}/Desktop" ]]; then
        cp "${DESKTOP_FILE}" "${DESKTOP_SHORTCUT}"
        chmod +x "${DESKTOP_SHORTCUT}"
    fi
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "${HOME}/.local/share/applications" || true

    # Verify PATH
    if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
        log_warn "${BIN_DIR} is not in your PATH. Run:"
        echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
    fi

    log_ok "Nihat.O.S installed successfully!"
    echo "  Run app       : nihatos"
    echo "  Update app    : nihatos update"
    echo "  Clear API keys: nihatos key-clear"
    echo "  Uninstall app : nihatos uninstall"
}

case "${1:-}" in
    --uninstall|uninstall)
        uninstall_app
        ;;
    --clear-keys|key-clear)
        clear_api_keys
        ;;
    *)
        install_app
        ;;
esac
