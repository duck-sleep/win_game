#!/usr/bin/env bash
# Shared environment for the SNM970 / win_game repository.
# Sourced by interactive shells (via ~/.bashrc) and by the install/start scripts.

export ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export HAPTICX_VENV="${HAPTICX_VENV:-$HOME/hapticx-venv}"

# PulseAudio needs a runtime dir; soundcard (imported by the HapticX DSP code)
# connects to a PulseAudio server at import time.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

case ":$PATH:" in
  *":$JAVA_HOME/bin:"*) : ;;
  *) export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH" ;;
esac

# Activate the Python virtualenv used by the HapticX prototype/DSP tests.
if [ -f "$HAPTICX_VENV/bin/activate" ]; then
  # shellcheck disable=SC1091
  . "$HAPTICX_VENV/bin/activate"
fi
