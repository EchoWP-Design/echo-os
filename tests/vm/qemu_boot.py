#!/usr/bin/env python3
"""Bootet das Echo-OS-Image in QEMU (Raspberry Pi 3B, 64-Bit) und zeichnet den Bildschirm auf.

* Bildschirm: alle 0,5 s ein Screenshot über QMP (screendump) -> Video + Einzelbilder
* Serielle Konsole: Kernel- und systemd-Meldungen -> serial.log
QEMU emuliert die Pi-GPU (VideoCore/KMS) nicht. Für den VM-Test wird deshalb der
Kernel direkt mit Framebuffer gestartet; Plymouth zeichnet dann über den Framebuffer.

Aufruf: qemu_boot.py <image> <ausgabe-ordner> [sekunden]
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time

IMG, OUT = sys.argv[1], sys.argv[2]
SECONDS = int(sys.argv[3]) if len(sys.argv) > 3 else 480
os.makedirs(f"{OUT}/frames", exist_ok=True)
BOOT = f"{OUT}/bootfiles"
os.makedirs(BOOT, exist_ok=True)

# Kernel, Device-Tree und Initramfs aus der Boot-Partition holen (mtools, ohne Mounten)
off = 4 * 1024 * 1024
for name in ("kernel8.img", "initramfs8", "bcm2710-rpi-3-b-plus.dtb", "cmdline.txt"):
    subprocess.run(["mcopy", "-o", "-i", f"{IMG}@@{off}", f"::/{name}", f"{BOOT}/{name}"], check=True)

# Die Mini-UART (serielle Konsole) schaltet auf echter Hardware die Pi-Firmware frei
# (enable_uart). In QEMU fehlt die Firmware, also im Device Tree aktivieren.
subprocess.run(["fdtput", "-t", "s", f"{BOOT}/bcm2710-rpi-3-b-plus.dtb", "/soc/serial@7e215040",
                "status", "okay"], check=False)
cmdline = open(f"{BOOT}/cmdline.txt").read().strip()
# QEMU: Root liegt auf mmcblk0p2; serielle Ausgabe auf der PL011-UART (ttyAMA1); Framebuffer 1280x720
cmdline = cmdline.replace("console=serial0,115200", "console=ttyAMA1,115200")
# QEMUs nachgebildeter Watchdog setzt beim "Entschärfen" zurück – Schritt in QEMU überspringen
# und auch systemds Watchdog-Betrieb ist in der langsamen Emulation zu knapp: Treiber in QEMU abschalten
cmdline += " watchdog_disarm=0 initcall_blacklist=bcm2835_wdt_driver_init"
if os.environ.get("NO_RESIZE"):
    cmdline = cmdline.replace(" resize", "")
DEPTH = os.environ.get("FBDEPTH", "16")
cmdline += f" bcm2708_fb.fbwidth=1280 bcm2708_fb.fbheight=720 bcm2708_fb.fbdepth={DEPTH} systemd.show_status=1"
if os.environ.get("QEMU_DEBUG"):
    # Diagnose: alle Kernel-Meldungen auf die serielle Konsole
    cmdline = cmdline.replace(" quiet", "").replace("loglevel=3", "loglevel=7")
    cmdline = cmdline.replace(" console=tty3", "") + " keep_bootcon panic=0" + os.environ.get("EXTRA_ARGS", "")
open(f"{OUT}/cmdline_qemu.txt", "w").write(cmdline + "\n")

# SD-Karten-Image muss für QEMU eine Zweierpotenz groß sein
sd = f"{OUT}/sd.img"
shutil.copy(IMG, sd)
size = os.path.getsize(sd)
p2 = 1
while p2 < size:
    p2 *= 2
subprocess.run(["qemu-img", "resize", "-f", "raw", sd, str(p2)], check=True, capture_output=True)

qmp_path = f"{OUT}/qmp.sock"
if os.path.exists(qmp_path):
    os.remove(qmp_path)
cmd = ["qemu-system-aarch64", "-M", "raspi3b", "-m", "1G", "-smp", "4",
       "-kernel", f"{BOOT}/kernel8.img", "-dtb", f"{BOOT}/bcm2710-rpi-3-b-plus.dtb",
       "-initrd", f"{BOOT}/initramfs8", "-append", cmdline,
       "-drive", f"file={sd},if=sd,format=raw",
       "-serial", f"file:{OUT}/serial.log", "-serial", f"file:{OUT}/serial_miniuart.log",
       "-display", "none", "-qmp", f"unix:{qmp_path},server,nowait"]
open(f"{OUT}/qemu_command.txt", "w").write(" ".join(cmd) + "\n")
qemu = subprocess.Popen(cmd, stdout=open(f"{OUT}/qemu_stdout.log", "w"), stderr=subprocess.STDOUT)

for _ in range(50):
    if os.path.exists(qmp_path):
        break
    time.sleep(0.2)
q = socket.socket(socket.AF_UNIX)
q.connect(qmp_path)
qf = q.makefile("rw")
qf.readline()


def qmp(cmd, **args):
    qf.write(json.dumps({"execute": cmd, "arguments": args} if args else {"execute": cmd}) + "\n")
    qf.flush()
    while True:
        r = json.loads(qf.readline())
        if "return" in r or "error" in r:
            return r


qmp("qmp_capabilities")
start = time.time()
n = 0
while time.time() - start < SECONDS and qemu.poll() is None:
    path = f"{OUT}/frames/f{n:05d}.ppm"
    qmp("screendump", filename=path)
    n += 1
    time.sleep(0.5)
qemu.terminate()
qemu.wait()
print(f"{n} Bildschirmaufnahmen in {SECONDS} s")

# Video: 0,5 s Echtzeit pro Bild -> doppelte Geschwindigkeit bei 4 fps
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate", "4", "-pattern_type", "glob",
                "-i", f"{OUT}/frames/*.ppm", "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
                "pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "23", f"{OUT}/qemu_boot.mp4"], check=False)
if not os.environ.get("KEEP_SD"):
    os.remove(sd)
