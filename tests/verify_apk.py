"""Check the actual Android artifact before publishing it in CI."""

import argparse
import re
import subprocess
from pathlib import Path


def verify_apk(apk: Path, sdk: Path) -> None:
    candidates = list((sdk / "build-tools").glob("*/apksigner"))
    if not candidates:
        raise FileNotFoundError(f"Android build tools not found in {sdk}")
    signer = max(candidates, key=lambda path: tuple(map(int, re.findall(r"\d+", path.parent.name))))
    subprocess.run([str(signer), "verify", "--verbose", str(apk)], check=True)
    manifest = subprocess.check_output(
        [str(signer.parent / "aapt"), "dump", "badging", str(apk)], text=True
    )
    permissions = [line for line in manifest.splitlines() if line.startswith("uses-permission")]
    if permissions:
        raise ValueError(
            "PureNote should not request Android permissions:\n" + "\n".join(permissions)
        )
    for line in manifest.splitlines():
        if line.startswith(("package:", "minSdkVersion:", "targetSdkVersion:", "native-code:")):
            print(line)
    print("APK signature and permission checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apks", nargs="+", type=Path)
    parser.add_argument(
        "--sdk",
        type=Path,
        default=Path.home() / ".buildozer/android/platform/android-sdk",
    )
    args = parser.parse_args()
    for apk in args.apks:
        verify_apk(apk, args.sdk)
