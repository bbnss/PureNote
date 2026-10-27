"""Check the actual Android artifact before publishing it in CI."""

import argparse
import re
import subprocess
from pathlib import Path

from verify_signing import fingerprint


def find_signer(sdk: Path) -> Path:
    candidates = list((sdk / "build-tools").glob("*/apksigner"))
    if not candidates:
        raise FileNotFoundError(f"Android build tools not found in {sdk}")
    return max(candidates, key=lambda path: tuple(map(int, re.findall(r"\d+", path.parent.name))))


def verify_apk(
    apk: Path, sdk: Path, expected_sha256: str | None = None, release: bool = False
) -> None:
    if release and expected_sha256 is None:
        raise ValueError("Release verification requires the confirmed Play app certificate")
    signer = find_signer(sdk)
    subprocess.run([str(signer), "verify", "--verbose", str(apk)], check=True)
    if expected_sha256 is not None:
        expected = fingerprint(expected_sha256)
        details = subprocess.check_output(
            [str(signer), "verify", "--print-certs", str(apk)], text=True
        )
        actual = re.findall(
            r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-f]+)$",
            details,
            re.MULTILINE,
        )
        if actual != [expected]:
            raise ValueError("APK certificate does not match the confirmed Play app certificate")
    manifest = subprocess.check_output(
        [str(signer.parent / "aapt"), "dump", "badging", str(apk)], text=True
    )
    permissions = [line for line in manifest.splitlines() if line.startswith("uses-permission")]
    if permissions:
        raise ValueError(
            "PureNote should not request Android permissions:\n" + "\n".join(permissions)
        )
    if release and "application-debuggable" in manifest.splitlines():
        raise ValueError("The official release APK must not be debuggable")
    for line in manifest.splitlines():
        if line.startswith(("package:", "minSdkVersion:", "targetSdkVersion:", "native-code:")):
            print(line)
    print("APK signature and permission checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apks", nargs="+", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--release", action="store_true")
    parser.add_argument(
        "--sdk",
        type=Path,
        default=Path.home() / ".buildozer/android/platform/android-sdk",
    )
    args = parser.parse_args()
    for apk in args.apks:
        verify_apk(apk, args.sdk, args.expected_sha256, args.release)
