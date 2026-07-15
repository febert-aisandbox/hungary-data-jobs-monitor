import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "run-daily.sh"
RUNNER_SCRIPT = ROOT / "deploy" / "run.sh"
ENTRYPOINT = ROOT / "deploy" / "container-entrypoint.sh"


class ScheduleTests(unittest.TestCase):
    def test_waits_until_0630_then_stamps_only_after_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            calls = base / "calls"
            runner = base / "runner.sh"
            runner.write_text(f"#!/bin/sh\nprintf run >> {calls}\n")
            runner.chmod(0o755)
            env = {
                **os.environ,
                "BASE": str(base),
                "RUNNER": str(runner),
                "NOW_DATE": "2026-07-15",
                "NOW_HHMM": "0629",
            }
            subprocess.run([str(SCRIPT)], env=env, check=True)
            self.assertFalse(calls.exists())
            env["NOW_HHMM"] = "0630"
            subprocess.run([str(SCRIPT)], env=env, check=True)
            self.assertEqual(calls.read_text(), "run")
            self.assertEqual((base / "data" / "last-success-date").read_text().strip(), "2026-07-15")
            subprocess.run([str(SCRIPT)], env=env, check=True)
            self.assertEqual(calls.read_text(), "run")

    def test_uses_configured_app_directory_for_default_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); app=base/"app"; data=base/"data"; calls=base/"calls"
            (app/"deploy").mkdir(parents=True)
            runner=app/"deploy"/"run.sh"
            runner.write_text(f"#!/bin/sh\nprintf run > {calls}\n")
            runner.chmod(0o755)
            env={**os.environ,"BASE":str(base/"state"),"APP_DIR":str(app),"DATA_DIR":str(data),"NOW_DATE":"2026-07-15","NOW_HHMM":"0730"}
            subprocess.run([str(SCRIPT)],env=env,check=True)
            self.assertEqual(calls.read_text(),"run")

    def test_container_entrypoint_can_execute_one_scheduler_tick(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=Path(tmp)/"calls"
            runner=Path(tmp)/"daily.sh"
            runner.write_text(f"#!/bin/sh\nprintf tick >> {calls}\n")
            runner.chmod(0o755)
            subprocess.run([str(ENTRYPOINT)],env={**os.environ,"DAILY_SCRIPT":str(runner),"SCHEDULER_ONCE":"1"},check=True)
            self.assertEqual(calls.read_text(),"tick")
    def test_runner_writes_artifacts_to_configured_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp); app=base/"app"; bindir=base/"bin"; data=base/"data"; output=data/"docs"; captured=base/"args"
            (app/"config").mkdir(parents=True); (app/"config"/"searches.json").write_text("{}")
            bindir.mkdir(); fake=bindir/"python3"
            fake.write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" > {captured}\n'); fake.chmod(0o755)
            env={**os.environ,"PATH":f"{bindir}:{os.environ['PATH']}","APP_DIR":str(app),"DATA_DIR":str(data),"OUTPUT_DIR":str(output),"ENV_FILE":str(base/"missing")}
            subprocess.run([str(RUNNER_SCRIPT)],env=env,check=True)
            args=captured.read_text().splitlines()
            self.assertEqual(args[args.index("--output")+1],str(output))
            self.assertTrue(output.is_dir())

    def test_container_entrypoint_forwards_term_to_active_tick(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            started=base/"started"
            terminated=base/"terminated"
            runner=base/"daily.sh"
            runner.write_text(f'#!/bin/sh\ntrap "printf term > {terminated}; exit 0" TERM INT\nprintf started > {started}\nwhile :; do sleep 1; done\n')
            runner.chmod(0o755)
            proc=subprocess.Popen([str(ENTRYPOINT)],env={**os.environ,"DAILY_SCRIPT":str(runner),"POLL_SECONDS":"60"},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                for _ in range(50):
                    if started.exists(): break
                    __import__("time").sleep(0.02)
                self.assertTrue(started.exists())
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
                    self.fail("entrypoint did not stop promptly")
                self.assertTrue(terminated.exists())
            finally:
                if proc.poll() is None: proc.kill(); proc.wait()


if __name__ == "__main__":
    unittest.main()
