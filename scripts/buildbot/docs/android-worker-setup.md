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
3. Install a pinned `just` binary on the worker machine; the `gpui-toolkit-android-check` builder uses `just showcase-android-check`:
   Download the `just` 1.40.0 release asset matching the worker host architecture from
   <https://github.com/casey/just/releases/tag/1.40.0>, extract the `just` binary to a
   directory on `PATH`, and make it executable. For an x86_64 Linux worker the steps are:
   ```bash
   JUST_VERSION=1.40.0
   curl -fsSL -o /tmp/just.tar.gz \
       "https://github.com/casey/just/releases/download/${JUST_VERSION}/just-${JUST_VERSION}-x86_64-unknown-linux-musl.tar.gz"
   sudo tar -xzf /tmp/just.tar.gz -C /usr/local/bin just
   rm /tmp/just.tar.gz
   chmod +x /usr/local/bin/just
   ```
   If the worker is not x86_64 Linux, substitute the appropriate release asset for its architecture.
4. Mount or clone the aggregate repository at `/workspace`. Android builders
   expect `/workspace/gpui-toolkit`, `/workspace/sotf`, and
   `/workspace/scripts/buildbot/version_snapshot.py`.
5. On the same machine, install a Buildbot worker in a venv and connect it as `android-qemu`:
   ```bash
   python3 -m venv ~/bb-android
   ~/bb-android/bin/pip install buildbot-worker==4.1.0
   ~/bb-android/bin/buildbot-worker create-worker ~/bb-android/worker <HOST> android-qemu android-password
   ~/bb-android/bin/buildbot-worker start ~/bb-android/worker
   ```
5. The `gpui-toolkit-android-check` builder runs `just showcase-android-check`; ensure `ANDROID_HOME` points to the SDK in the worker environment.
6. The repository must be available inside the Android emulator/VM at the same absolute path `/Volumes/home_ext1/src_pierre/all_of_sotf`, because the Android builder uses that path as `workdir`. If that path is not possible in your environment, edit `scripts/buildbot/master.cfg` to set the correct `workdir` for the Android builder.
