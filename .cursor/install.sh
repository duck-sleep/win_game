#!/usr/bin/env bash
# Idempotent bootstrap for the SNM970 / win_game Cloud Agent environment.
# Self-contained: installs the JDK 17 / Android SDK / audio toolchain the
# repository needs on top of the default base image, then prepares the
# repository-specific Python + Gradle state. Safe to run repeatedly.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$REPO_ROOT/.cursor/env.sh"

# ---------------------------------------------------------------------------
# 1. System packages (JDK 17 for Android, tkinter for the GUI prototype,
#    PulseAudio so `soundcard` can be imported headless).
# ---------------------------------------------------------------------------
NEED_PKGS=()
[ -d /usr/lib/jvm/java-17-openjdk-amd64 ] || NEED_PKGS+=(openjdk-17-jdk-headless)
command -v pulseaudio >/dev/null 2>&1 || NEED_PKGS+=(pulseaudio pulseaudio-utils)
command -v unzip >/dev/null 2>&1 || NEED_PKGS+=(unzip)
command -v wget  >/dev/null 2>&1 || NEED_PKGS+=(wget)
command -v curl  >/dev/null 2>&1 || NEED_PKGS+=(curl)
python3 -c 'import ensurepip' >/dev/null 2>&1 || NEED_PKGS+=(python3-venv)
python3 -c 'import tkinter' >/dev/null 2>&1 || NEED_PKGS+=(python3-tk)
if [ "${#NEED_PKGS[@]}" -gt 0 ]; then
  echo "==> Installing system packages: ${NEED_PKGS[*]}"
  sudo apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${NEED_PKGS[@]}"
fi

# ---------------------------------------------------------------------------
# 2. Android SDK (cmdline-tools + platform 34 + build-tools 34.0.0).
#    Gradle itself is provided by the committed wrapper (./gradlew).
# ---------------------------------------------------------------------------
if [ ! -d "$ANDROID_HOME/platform-tools" ]; then
  echo "==> Installing Android SDK into $ANDROID_HOME"
  SDK_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
  mkdir -p "$ANDROID_HOME/cmdline-tools"
  tmpzip="$(mktemp --suffix=.zip)"
  wget -q "$SDK_TOOLS_URL" -O "$tmpzip"
  unzip -q -o "$tmpzip" -d "$ANDROID_HOME/cmdline-tools"
  rm -f "$tmpzip"
  if [ -d "$ANDROID_HOME/cmdline-tools/cmdline-tools" ]; then
    rm -rf "$ANDROID_HOME/cmdline-tools/latest"
    mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
  fi
  yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$ANDROID_HOME" --licenses >/dev/null 2>&1 || true
  "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --sdk_root="$ANDROID_HOME" \
    "platform-tools" "platforms;android-34" "build-tools;34.0.0"
fi

# ---------------------------------------------------------------------------
# 3. Python virtualenv + HapticX dependencies.
# ---------------------------------------------------------------------------
echo "==> Python virtualenv + HapticX deps"
if [ ! -x "$HAPTICX_VENV/bin/python" ]; then
  python3 -m venv "$HAPTICX_VENV"
fi
"$HAPTICX_VENV/bin/pip" install --upgrade pip -q
"$HAPTICX_VENV/bin/pip" install -q -r "$REPO_ROOT/25_xbox_control/hapticx/requirements.txt"

# ---------------------------------------------------------------------------
# 4. PulseAudio autospawn: the HapticX DSP code imports `soundcard`, which
#    connects to a PulseAudio server at import time. Enabling autospawn makes
#    any client start a headless server on demand, so the audio path works even
#    if the per-boot `start` phase has not run yet.
# ---------------------------------------------------------------------------
echo "==> Configure PulseAudio autospawn"
mkdir -p "$HOME/.config/pulse"
cat > "$HOME/.config/pulse/client.conf" <<EOF
autospawn = yes
daemon-binary = /usr/bin/pulseaudio
EOF
cat > "$HOME/.config/pulse/daemon.conf" <<EOF
exit-idle-time = -1
.include /etc/pulse/daemon.conf
EOF

# ---------------------------------------------------------------------------
# 5. Gradle configuration: point at the SDK and force JDK 17.
# ---------------------------------------------------------------------------
ANDROID_PROJECT="$REPO_ROOT/25_xbox_control/hapticx-android"
if [ -d "$ANDROID_PROJECT" ]; then
  printf 'sdk.dir=%s\n' "$ANDROID_HOME" > "$ANDROID_PROJECT/local.properties"
fi
mkdir -p "$HOME/.gradle"
if ! grep -q '^org.gradle.java.home=' "$HOME/.gradle/gradle.properties" 2>/dev/null; then
  echo "org.gradle.java.home=$JAVA_HOME" >> "$HOME/.gradle/gradle.properties"
fi

# ---------------------------------------------------------------------------
# 6. Make the shared environment available to interactive shells.
# ---------------------------------------------------------------------------
BASHRC="$HOME/.bashrc"
MARKER="# >>> win_game env >>>"
if ! grep -qF "$MARKER" "$BASHRC" 2>/dev/null; then
  {
    echo ""
    echo "$MARKER"
    echo "[ -f \"$REPO_ROOT/.cursor/env.sh\" ] && source \"$REPO_ROOT/.cursor/env.sh\""
    echo "# <<< win_game env <<<"
  } >> "$BASHRC"
fi

echo "==> install.sh complete"
