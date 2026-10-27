"""Give debug APKs a persistent identity, independent of Gradle's default key."""

import argparse
import hashlib
import subprocess
import tempfile
from pathlib import Path

from verify_apk import find_signer


def sign_apk(apk: Path, sdk: Path, keystore: Path) -> None:
    signer = find_signer(sdk)
    certificate = subprocess.check_output(
        [
            "keytool",
            "-exportcert",
            "-keystore",
            str(keystore),
            "-storepass",
            "android",
            "-alias",
            "androiddebugkey",
        ]
    )
    expected = hashlib.sha256(certificate).hexdigest()
    with tempfile.TemporaryDirectory(prefix="purenote-sign-", dir=apk.parent) as directory:
        signed = Path(directory) / apk.name
        subprocess.run(
            [
                str(signer),
                "sign",
                "--ks",
                str(keystore),
                "--ks-key-alias",
                "androiddebugkey",
                "--ks-pass",
                "pass:android",
                "--key-pass",
                "pass:android",
                "--v4-signing-enabled",
                "false",
                "--out",
                str(signed),
                str(apk),
            ],
            check=True,
        )
        details = subprocess.check_output(
            [str(signer), "verify", "--print-certs", str(signed)], text=True
        )
        if f"certificate SHA-256 digest: {expected}" not in details:
            raise ValueError("APK certificate differs from the persistent debug key")
        signed.replace(apk)
    print(f"{apk.name}: persistent debug certificate SHA-256 {expected}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apks", nargs="+", type=Path)
    parser.add_argument("--keystore", required=True, type=Path)
    parser.add_argument(
        "--sdk", type=Path, default=Path.home() / ".buildozer/android/platform/android-sdk"
    )
    args = parser.parse_args()
    for apk in args.apks:
        sign_apk(apk, args.sdk, args.keystore)
