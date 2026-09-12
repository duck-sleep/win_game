#!/usr/bin/env bash
# Idempotent repository bootstrap for the SNM970 / win_game Cloud Agent environment.
# System toolchains (JDK 17, Android SDK, Gradle, PulseAudio) come from the base
# snapshot; this script prepares the repository-dependent state on top of it.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$REPO_ROOT/.cursor/env.sh"

echo "==> Python virtualenv + HapticX deps"
if [ ! -x "$HAPTICX_VENV/bin/python" ]; then
  python3 -m venv "$HAPTICX_VENV"
fi
"$HAPTICX_VENV/bin/pip" install --upgrade pip -q
"$HAPTICX_VENV/bin/pip" install -q -r "$REPO_ROOT/25_xbox_control/hapticx/requirements.txt"

echo "==> Android SDK location (local.properties)"
ANDROID_PROJECT="$REPO_ROOT/25_xbox_control/hapticx-android"
if [ -d "$ANDROID_PROJECT" ]; then
  printf 'sdk.dir=%s\n' "$ANDROID_HOME" > "$ANDROID_PROJECT/local.properties"
fi

echo "==> Force Gradle to build with JDK 17"
mkdir -p "$HOME/.gradle"
if ! grep -q '^org.gradle.java.home=' "$HOME/.gradle/gradle.properties" 2>/dev/null; then
  echo "org.gradle.java.home=$JAVA_HOME" >> "$HOME/.gradle/gradle.properties"
fi

echo "==> Make the shared environment available to interactive shells"
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
