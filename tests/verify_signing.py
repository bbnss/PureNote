"""Require an independently confirmed certificate before signing a release."""

import argparse
import base64
import hashlib
import os
import re
import subprocess
from pathlib import Path


def fingerprint(value: str) -> str:
    value = value.strip().replace(":", "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a confirmed SHA-256 certificate fingerprint")
    return value


def verify_signing(expected: str, artifact: Path | None = None) -> None:
    expected = fingerprint(expected)
    if artifact is None:
        command = [
            "keytool", "-exportcert",
            "-keystore", os.environ["P4A_RELEASE_KEYSTORE"],
            "-alias", os.environ["P4A_RELEASE_KEYALIAS"],
            "-storepass:env", "P4A_RELEASE_KEYSTORE_PASSWD",
        ]
        certificate = subprocess.check_output(command)
    else:
        if artifact.suffix != ".aab":
            raise ValueError("Only AAB certificate verification is supported here")
        subprocess.run(["jarsigner", "-verify", str(artifact)], check=True)
        details = subprocess.check_output(
            ["keytool", "-printcert", "-rfc", "-jarfile", str(artifact)], text=True
        )
        certificates = re.findall(
            r"-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----",
            details,
            re.DOTALL,
        )
        if not certificates:
            raise ValueError("The AAB has no signing certificate")
        certificate = base64.b64decode(certificates[0])
    actual = hashlib.sha256(certificate).hexdigest()
    if actual != expected:
        raise ValueError("Signing certificate does not match the confirmed Play certificate")
    print(f"Confirmed signing certificate SHA-256: {actual}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("artifact", nargs="?", type=Path)
    args = parser.parse_args()
    verify_signing(args.expected_sha256, args.artifact)
