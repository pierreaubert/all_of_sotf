# Windows QEMU Worker Setup

1. Install QEMU and create a Windows 11 VM:
   ```bash
   qemu-img create -f qcow2 /var/lib/qemu/windows11.qcow2 128G
   ```
2. Install Windows, enable OpenSSH server, and install the Rust toolchain plus `cargo`.
3. From inside the VM, install the Buildbot worker in a Python venv:
   ```powershell
   pip install buildbot-worker==4.1.0
   buildbot-worker create-worker C:\buildbot-worker <HOST_IP> windows-qemu windows-password
   buildbot-worker start C:\buildbot-worker
   ```
4. Replace `<HOST_IP>` with the host IP reachable from the VM (`host.docker.internal` does not apply here; use the VM gateway or a static host-only IP).
5. Ensure the VM mounts or can clone `/Volumes/home_ext1/src_pierre/all_of_sotf` (e.g., via SMB or by cloning the repos over SSH).
6. The repository must be available inside the VM at the same absolute path `/Volumes/home_ext1/src_pierre/all_of_sotf`, because the Windows builders use that path as `workdir`. If that path is not possible in your VM, edit `master.cfg` to set the correct `workdir` for the Windows builders.
