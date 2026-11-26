#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

if [ ! -x ".venv/bin/pytest" ]; then
    echo "Virtual environment not found. Run ./scripts/setup_venv.sh first."
    exit 1
fi

REPORT_FILE="test-report.txt"

{
    echo "=== NihatOS Terminal Automated Test Report ==="
    echo "Date: $(date -Is)"
    echo "OS: $(grep PRETTY_NAME /etc/os-release 2>/dev/null || uname -srm)"
    echo "Python: $(.venv/bin/python --version)"
    echo "Bash: $(bash --version | head -1)"
    echo "Konsole: $(konsole --version 2>/dev/null || echo 'N/A')"
    echo "TERM: ${TERM:-unset} | COLORTERM: ${COLORTERM:-unset}"
    echo "Terminal Size (stty): $(stty size 2>/dev/null || echo 'non-tty')"
    echo ""
    echo "=== Installed Venv Packages ==="
    .venv/bin/pip list
    echo ""
    echo "=== Pytest Execution ==="
    .venv/bin/pytest -v
} | tee "${REPORT_FILE}"

echo ""
echo "[NihatOS Terminal] Report saved to ${REPORT_FILE}"