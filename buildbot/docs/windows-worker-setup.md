# Windows QEMU Worker Setup

This guide configures a Windows VM (e.g. launched via UTM/QEMU) as the `windows-qemu` Buildbot worker.

## Important: Buildbot does not discover workers

Workers connect **to** the master. The VM must run `buildbot-worker` and reach the master PB port (`9989`).

## 1. Prepare the VM

- Install Windows 11 in UTM/QEMU.
- Enable OpenSSH server or set up another way to access the VM from the host.
- Install the Rust toolchain (`cargo`, `rustc`).
- Make the repository available inside the VM at `C:\workspace`. You can use:
  - UTM shared folders
  - SMB share from the macOS host
  - Clone the repos over SSH into `C:\workspace`

The Windows builders expect each workspace at `C:\workspace\<workspace>` (e.g. `C:\workspace\sotf`). This path is configured in `buildbot/master.cfg`.

## 2. Find the host IP from inside the VM

In UTM's default shared-networking mode, the host is usually the VM's default gateway. From a PowerShell prompt inside the VM:

```powershell
ipconfig /all
```

Look for the **Default Gateway** of the active Ethernet adapter (commonly `192.168.64.1`).

Test connectivity back to the master:

```powershell
Test-NetConnection -ComputerName 192.168.64.1 -Port 9989
```

Replace `192.168.64.1` with the actual gateway. If `TcpTestSucceeded` is `True`, the VM can reach the master.

## 3. Install and start the Buildbot worker

Inside the VM, from an elevated PowerShell prompt:

```powershell
python -m venv C:\buildbot-venv
C:\buildbot-venv\Scripts\pip install buildbot-worker==4.1.0
C:\buildbot-venv\Scripts\buildbot-worker create-worker C:\buildbot-worker <HOST_IP> windows-qemu windows-password
C:\buildbot-venv\Scripts\buildbot-worker start C:\buildbot-worker
```

Replace `<HOST_IP>` with the gateway IP found above.

## 4. Verify on the master

On the macOS host, the worker should appear connected:

```bash
curl -s http://localhost:8010/api/v2/workers | python3 -m json.tool
```

Look for `windows-qemu` with `connected_to` containing `{"masterid": 1}`.

## Troubleshooting

- If the worker cannot connect, check that the master is listening on all interfaces (the default `c['protocols'] = {'pb': {'port': 9989}}` does this).
- macOS Firewall may block inbound connections on port 9989. Allow `python3` / the Buildbot master process in System Settings > Network & Security > Firewall.
- If the build fails with "directory does not exist", confirm the workspace is mounted/cloned at `C:\workspace\<workspace>`.
