#!/usr/bin/env bash
# Per-boot runtime init: bring up a headless PulseAudio server with a virtual
# sink so the HapticX Python code (which imports `soundcard`) can run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$REPO_ROOT/.cursor/env.sh"

mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR" 2>/dev/null || true

if ! pulseaudio --check 2>/dev/null; then
  echo "==> Starting PulseAudio (headless)"
  pulseaudio --start --exit-idle-time=-1 --log-target=stderr 2>/dev/null || true
  for _ in $(seq 1 20); do
    pulseaudio --check 2>/dev/null && break
    sleep 0.5
  done
fi

if ! pactl list short sinks 2>/dev/null | grep -q hapticx_sink; then
  echo "==> Loading virtual audio sink"
  pactl load-module module-null-sink sink_name=hapticx_sink \
    sink_properties=device.description=HapticX_Virtual >/dev/null 2>&1 || true
  pactl set-default-sink hapticx_sink >/dev/null 2>&1 || true
fi

pactl info >/dev/null 2>&1 && echo "==> PulseAudio ready" || echo "!! PulseAudio not ready"
