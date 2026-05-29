#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${BALATRO_GYM_LIVE_VENV_DIR:-${REPO_ROOT}/.venv_live_smoke}"

select_python() {
  if [[ -n "${BALATRO_GYM_PYTHON_BIN:-}" ]]; then
    echo "${BALATRO_GYM_PYTHON_BIN}"
    return
  fi

  if command -v python3.12 >/dev/null 2>&1; then
    echo "python3.12"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    local version
    version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [[ "${version}" == "3.12" ]]; then
      echo "python3"
      return
    fi
  fi

  echo "Python 3.12 is required. Install python3.12 or set BALATRO_GYM_PYTHON_BIN." >&2
  exit 1
}

PYTHON_BIN="$(select_python)"

if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

export PIP_DISABLE_PIP_VERSION_CHECK=1

if ! "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

required_modules = ["gymnasium", "numpy", "httpx", "typer"]
missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
sys.exit(0 if not missing else 1)
PY
then
  "${VENV_DIR}/bin/python" -m pip install \
    "gymnasium==0.29.1" \
    "numpy==1.26.4" \
    "httpx==0.28.1" \
    "typer==0.15.4"
fi

cd "${REPO_ROOT}"
"${VENV_DIR}/bin/python" tests/live_smoke_test.py
