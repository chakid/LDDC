#!/usr/bin/env python3
"""Build a dependency-bundled LDDC package on the native target platform.

Windows produces a single ``dist/LDDC-windows-<arch>.exe`` plus a portable zip and macOS produces
``dist/LDDC-macos-arm64.dmg`` (or a zip when ``hdiutil`` is unavailable).
Cross-compiling a Qt application is deliberately rejected.

Install build dependencies with ``python -m pip install -r requirements-build.txt``
before running this script.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
DIST = ROOT / "dist"
sys.path.insert(0, str(ROOT))

from LDDC.common.version import __version__, parse_version


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    try:
        subprocess.run(args, cwd=ROOT, check=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"Package build failed with exit code {error.returncode}.") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="remove previous build and dist directories")
    parser.add_argument("--jobs", type=int, default=2, help="maximum parallel compiler jobs")
    args = parser.parse_args()

    system = platform.system()
    machine = platform.machine().lower()
    if system not in {"Windows", "Darwin"}:
        raise SystemExit("Only native Windows and macOS builds are supported.")
    if system == "Darwin" and machine not in {"arm64", "aarch64"}:
        raise SystemExit("The macOS package must be built on an Apple Silicon (arm64) runner.")

    if args.clean:
        shutil.rmtree(BUILD, ignore_errors=True)
        shutil.rmtree(DIST, ignore_errors=True)
    BUILD.mkdir(exist_ok=True)
    DIST.mkdir(exist_ok=True)

    try:
        import PySide6  # noqa: F401
    except ImportError as error:
        raise SystemExit("Install runtime dependencies first: python -m pip install -r requirements.txt") from error

    nuitka = [sys.executable, "-m", "nuitka"]
    common = [
        "--assume-yes-for-downloads",
        f"--jobs={args.jobs}",
        "--report=build/nuitka-report.xml",
        "--enable-plugin=pyside6",
        "--output-dir=build",
        "--product-name=LDDC",
        "--file-version=" + ".".join(str(part) for part in parse_version(__version__)[:3]),
        "--include-data-dir=LDDC/gui/components/assets=LDDC/gui/components/assets",
        "--include-data-dir=LDDC/res/img/icon=LDDC/res/img/icon",
    ]
    from PySide6.QtCore import QLibraryInfo

    translation_path = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    for locale in ("en", "zh_CN", "zh_TW", "ja"):
        translation = translation_path / f"qtbase_{locale}.qm"
        if translation.is_file():
            target = "PySide6/translations" if system == "Windows" else "PySide6/Qt/translations"
            common.append(f"--include-data-files={translation}={target}/{translation.name}")
    if system == "Windows":
        arch = "arm64" if "arm" in machine or "aarch" in machine else "x64"
        run(*(nuitka + common + [
            "--mode=onefile",
            "--windows-icon-from-ico=LDDC/res/img/icon/logo.ico",
            "--windows-console-mode=disable",
            "LDDC",
        ]))
        output = DIST / f"LDDC-windows-{arch}"
        run(str(BUILD / "LDDC.dist" / "LDDC.exe"), "--help")
        shutil.copy2(ROOT / "LICENSE", BUILD / "LDDC.dist" / "LICENSE.txt")
        shutil.copy2(BUILD / "LDDC.exe", output.with_suffix(".exe"))
        shutil.make_archive(str(output), "zip", BUILD / "LDDC.dist")
        print(f"Created {output}.zip")
        return 0

    run(*(nuitka + common + [
        "--mode=app",
        "--output-filename=LDDC.bin",
        "--macos-app-name=LDDC",
        "--macos-app-icon=LDDC/res/img/icon/logo.icns",
        "--macos-target-arch=arm64",
        "--macos-app-version=" + ".".join(str(part) for part in parse_version(__version__)[:3]),
        "LDDC",
    ]))
    app = BUILD / "LDDC.app"
    if not app.exists():
        raise SystemExit(f"Nuitka did not create the expected app bundle: {app}")
    run(str(app / "Contents" / "MacOS" / "LDDC.bin"), "--help")
    run("file", str(app / "Contents" / "MacOS" / "LDDC.bin"))
    dmg = DIST / "LDDC-macos-arm64.dmg"
    if shutil.which("hdiutil"):
        staging = BUILD / "dmg-staging"
        staging.mkdir(exist_ok=True)
        run("ditto", str(app), str(staging / app.name))
        shutil.copy2(ROOT / "LICENSE", staging / "LICENSE.txt")
        applications = staging / "Applications"
        if not applications.is_symlink():
            applications.symlink_to("/Applications", target_is_directory=True)
        run("hdiutil", "create", "-volname", "LDDC", "-srcfolder", str(staging), "-ov", "-format", "UDZO", str(dmg))
        run("hdiutil", "verify", str(dmg))
        print(f"Created {dmg}")
    else:
        archive = DIST / "LDDC-macos-arm64"
        shutil.make_archive(str(archive), "zip", app.parent, app.name)
        print(f"Created {archive}.zip (install create-dmg/hdiutil for a DMG)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
