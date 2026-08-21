#!/usr/bin/env python3
"""Verify and package an exact, user-acquired V7 checkout for local screening."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / "candidates/v7-portable/source.json"
MEMBERS = {
    "main.py": ("path", "sha256"),
    "THIRD_PARTY_NOTICES.txt": ("notice_path", "notice_sha256"),
    "LICENSE-APACHE-2.0.txt": ("apache_license_path", "apache_license_sha256"),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(source_checkout: Path, output: Path) -> dict[str, object]:
    descriptor = json.loads(DESCRIPTOR.read_text())
    payloads: dict[str, bytes] = {}
    for member, (path_key, hash_key) in MEMBERS.items():
        source = source_checkout / descriptor[path_key]
        data = source.read_bytes()
        actual = sha256_bytes(data)
        if actual != descriptor[hash_key]:
            raise ValueError(f"{source}: SHA-256 {actual} != pinned {descriptor[hash_key]}")
        payloads[member] = data

    output.parent.mkdir(parents=True, exist_ok=True)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for name in sorted(payloads):
            info = tarfile.TarInfo(name)
            info.size = len(payloads[name])
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(payloads[name]))
    with output.open("wb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            compressed.write(raw.getvalue())

    with tarfile.open(output, "r:gz") as archive:
        names = archive.getnames()
        extracted = {name: archive.extractfile(name).read() for name in names}
    expected = sorted(MEMBERS)
    if names != expected or any(extracted[name] != payloads[name] for name in expected):
        raise ValueError("archive contents do not exactly match the pinned source files")
    return {
        "archive": str(output),
        "archive_sha256": sha256_bytes(output.read_bytes()),
        "contents": names,
        "source_sha256": descriptor["sha256"],
        "redistribution": descriptor["redistribution"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source_checkout, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
