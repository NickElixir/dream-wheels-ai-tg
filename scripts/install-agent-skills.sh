#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/docs/agent-skills"
TARGET_DIR="${CODEX_HOME:-${HOME}/.codex}/skills"

mkdir -p "${TARGET_DIR}"

for skill_dir in "${SOURCE_DIR}"/*; do
  [ -d "${skill_dir}" ] || continue

  skill_name="$(basename "${skill_dir}")"
  target="${TARGET_DIR}/${skill_name}"

  if [ -L "${target}" ]; then
    rm "${target}"
  elif [ -e "${target}" ]; then
    echo "skip ${skill_name}: ${target} exists and is not a symlink" >&2
    continue
  fi

  ln -s "${skill_dir}" "${target}"
  echo "installed ${skill_name} -> ${target}"
done

echo "done"
