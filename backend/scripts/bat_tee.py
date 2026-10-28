"""
bat_tee.py - Chay demo_launcher.py, hien thi output realtime va ghi file log dong thoi.
Su dung: python bat_tee.py <log_file> <action_name> <launcher_arg1> [arg2 ...]
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    if len(sys.argv) < 4:
        print("Usage: bat_tee.py <log_file> <action> <launcher_args...>")
        return 1

    log_file = Path(sys.argv[1])
    action   = sys.argv[2]
    launcher_args = sys.argv[3:]  # e.g. ["start"] or ["migrate", "--confirm", "scopus_ictu_app"]

    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Tim python va launcher tu vi tri script nay
    script_dir = Path(__file__).parent
    launcher   = script_dir / "demo_launcher.py"
    python_exe = sys.executable

    def tee(line: str) -> None:
        print(line, flush=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    tee(f"[{ts()}] HANH VI: {action}")

    cmd = [python_exe, str(launcher)] + launcher_args
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    for line in proc.stdout:
        tee(line.rstrip("\n"))

    proc.wait()
    rc = proc.returncode
    status = "THANH CONG" if rc == 0 else f"THAT BAI (ma thoat {rc})"
    tee(f"[{ts()}] KET QUA {action}: {status}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
