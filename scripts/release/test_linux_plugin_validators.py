import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATE = ROOT / "scripts/release/validate_linux_plugins.sh"
FETCH = ROOT / "scripts/release/fetch_linux_plugin_validators.sh"


class LinuxPluginValidatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def executable(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/usr/bin/env bash\n" + body)
        path.chmod(0o755)
        return path

    def test_vst3_validates_native_arm_bundle_layout(self):
        (self.root / "dist/vst3-linux").mkdir(parents=True)
        staged = self.root / "evidence/artifacts/sotf-daw/dist/vst3-linux"
        staged.mkdir(parents=True)
        for index in range(43):
            name = f"Plugin{index:02}.vst3"
            (self.root / "dist/vst3-linux" / name).touch()
            binary = staged / name / "Contents/aarch64-linux" / f"Plugin{index:02}.so"
            binary.parent.mkdir(parents=True)
            binary.touch()
        calls = self.root / "calls"
        self.executable(self.bin / "uname", "if [[ $1 == -m ]]; then echo aarch64; else echo Linux; fi\n")
        self.executable(self.bin / "pluginval", f"echo \"$*\" >> '{calls}'\n")
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}"}
        result = subprocess.run(
            ["bash", str(VALIDATE), "vst3", str(self.root / "evidence"), "aarch64"],
            cwd=self.root, env=env, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(len(calls.read_text().splitlines()), 43)

    def test_foreign_target_is_rejected_before_plugin_validation(self):
        self.executable(self.bin / "uname", "if [[ $1 == -m ]]; then echo aarch64; else echo Linux; fi\n")
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}"}
        result = subprocess.run(
            ["bash", str(VALIDATE), "vst3", str(self.root / "evidence"), "x86_64"],
            cwd=self.root, env=env, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("use a native runner", result.stderr)

    def fetch_env(self, evidence):
        uname = self.executable(self.bin / "uname", "if [[ $1 == -m ]]; then echo aarch64; else echo Linux; fi\n")
        return {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "SOTF_PLUGIN_VALIDATOR_EVIDENCE_DIR": str(evidence),
        }

    def test_arm_missing_validators_is_actionable_and_does_not_download(self):
        evidence = self.root / "evidence"
        env = self.fetch_env(evidence)
        curl_calls = self.root / "curl-called"
        self.executable(self.bin / "curl", f"touch '{curl_calls}'\nexit 99\n")
        result = subprocess.run(["bash", str(FETCH)], cwd=self.root, env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ARM64 pluginval is unavailable", result.stderr)
        self.assertIn("no x86_64 fallback or download", result.stderr)
        self.assertFalse(curl_calls.exists())
        self.assertFalse((evidence / "downloads/pluginval.zip").exists())

    def test_arm_local_validators_are_architecture_checked_and_staged(self):
        evidence = self.root / "evidence"
        env = self.fetch_env(evidence)
        pluginval = self.executable(self.root / "local/pluginval", "exit 0\n")
        clap = self.executable(self.root / "local/clap-validator", "exit 0\n")
        env["SOTF_PLUGINVAL_PATH"] = str(pluginval)
        env["SOTF_CLAP_VALIDATOR_PATH"] = str(clap)
        self.executable(self.bin / "file", "echo 'ELF 64-bit LSB pie executable, ARM aarch64'\n")
        self.executable(self.bin / "ldd", "echo 'statically linked'\n")
        result = subprocess.run(["bash", str(FETCH)], cwd=self.root, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue((evidence / "bin/pluginval").is_file())
        self.assertTrue((evidence / "bin/clap-validator").is_file())
        self.assertIn("local", (evidence / "provenance.tsv").read_text())

        env["SOTF_PLUGINVAL_PATH"] = str(self.executable(self.root / "local/wrong-pluginval", "exit 0\n"))
        self.executable(self.bin / "file", "echo 'ELF 64-bit LSB pie executable, x86-64'\n")
        rejected = subprocess.run(["bash", str(FETCH)], cwd=self.root, env=env, text=True, capture_output=True)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("not an ARM64 ELF binary", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
