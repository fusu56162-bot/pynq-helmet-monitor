"""Offline native ARMv7 build, only inside this candidate folder; no apt/pip/install."""
import hashlib
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
SOURCE_SHA = "5aedf25e22d4a9ab7785d33774affee96b55b546e85318cc351a48a365d15ced"


def main():
    if sys.platform != "linux" or platform.machine() not in ("armv7l", "armv8l") or struct.calcsize("P") != 4:
        raise RuntimeError("Run on the 32-bit ARMv7 board, not Windows/x86/ARM64")
    if "neon" not in Path("/proc/cpuinfo").read_text().lower():
        raise RuntimeError("NEON not reported by /proc/cpuinfo")
    for tool in ("cmake", "g++", "make"):
        if not shutil.which(tool):
            raise RuntimeError("Missing tool: " + tool)
    if shutil.disk_usage(ROOT).free < 1024**3:
        raise RuntimeError("Need at least 1 GiB free in the candidate directory")
    mem = dict((k, int(v.strip().split()[0])) for k, v in
               (line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()))
    if mem.get("MemAvailable", 0) < 150*1024 or mem.get("SwapTotal", 0) < 256*1024:
        raise RuntimeError("Need >=150 MiB available RAM and >=256 MiB existing swap; no automatic expansion")
    archive = ROOT / "vendor/ncnn-20260526-source.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SOURCE_SHA:
        raise RuntimeError("Source archive hash mismatch")
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    source = build / "source"
    source.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            target = (source / info.filename).resolve()
            target.relative_to(source.resolve())
            if ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise RuntimeError("Unexpected source symlink")
        print("Extracting pinned source locally...", flush=True)
        z.extractall(source)
    flags = "-mcpu=cortex-a9 -mfpu=neon -mfloat-abi=hard"
    commands = [
        ["cmake", "-S", str(ROOT / "native"), "-B", str(build),
         "-G", "Unix Makefiles", "-DCMAKE_BUILD_TYPE=Release",
         "-DNCNN_SOURCE_DIR=" + str(source / "ncnn-20260526"),
         "-DCMAKE_C_FLAGS=" + flags, "-DCMAKE_CXX_FLAGS=" + flags],
        ["cmake", "--build", str(build), "--target", "rider_ncnn", "--", "-j1"],
    ]
    with (build / "build.log").open("w", encoding="utf-8") as log:
        for command in commands:
            print("Running:", " ".join(command), flush=True)
            log.write("\nCOMMAND " + repr(command) + "\n")
            log.flush()
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, errors="replace")
            try:
                for line in process.stdout:
                    print(line, end="", flush=True)
                    log.write(line)
                    log.flush()
                if process.wait() != 0:
                    raise RuntimeError("Build failed; preserve build/build.log and send its end")
            except BaseException:
                process.terminate()
                process.wait()
                raise
    if not (build / "librider_ncnn.so").is_file():
        raise RuntimeError("Build completed without the expected library")
    print("BUILD PASS. Native inference is NOT yet verified. Next: board acceptance.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("BUILD FAIL:", str(exc), file=sys.stderr)
        sys.exit(1)
