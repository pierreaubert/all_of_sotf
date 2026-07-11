# Android QEMU Worker Setup

1. Install the Android SDK, platform-tools, and an emulator image on the host or inside a Linux VM:
   ```bash
   sdkmanager --install "platform-tools" "platforms;android-35" "system-images;android-35;google_apis;arm64-v8a"
   avdmanager create avd -n ci -k "system-images;android-35;google_apis;arm64-v8a" -d pixel_8
   ```
2. Start the emulator with acceleration (HVF on Apple Silicon, KVM on Linux):
   ```bash
   emulator -avd ci -no-window -no-audio -gpu swiftshader_indirect
   ```
3. On the same machine, install a Buildbot worker in a venv and connect it as `android-qemu`:
   ```bash
   python3 -m venv ~/bb-android
   ~/bb-android/bin/pip install buildbot-worker==4.1.0
   ~/bb-android/bin/buildbot-worker create-worker ~/bb-android/worker <HOST> android-qemu android-password
   ~/bb-android/bin/buildbot-worker start ~/bb-android/worker
   ```
4. The `gpui-toolkit-android-check` builder runs `just showcase-android-check`; ensure `ANDROID_HOME` points to the SDK in the worker environment.
