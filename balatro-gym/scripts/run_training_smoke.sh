#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${BALATRO_GYM_VENV_DIR:-${REPO_ROOT}/.venv_training_smoke}"

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

export MPLCONFIGDIR="${REPO_ROOT}/.tmp/matplotlib"
mkdir -p "${MPLCONFIGDIR}"
export PIP_DISABLE_PIP_VERSION_CHECK=1

if ! "${VENV_DIR}/bin/python" - <<'PY' >/dev/null 2>&1
import importlib.util
import sys

required_modules = [
    "pytest",
    "gymnasium",
    "numpy",
    "pandas",
    "matplotlib",
    "torch",
    "stable_baselines3",
    "sb3_contrib",
    "tensorboard",
]

missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
sys.exit(0 if not missing else 1)
PY
then
  "${VENV_DIR}/bin/python" -m pip install -r "${REPO_ROOT}/config/requirements.txt" pytest
fi

cd "${REPO_ROOT}"
"${VENV_DIR}/bin/python" -m pytest tests/training_smoke_test.py -q
