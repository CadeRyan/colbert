#!/usr/bin/env python3
"""Download Homebrew's Apple Silicon build ("bottle") of a formula and check its checksum.

    python3 tools/fetch-arm64-bottle.py gmp gmp.tar.gz

CI builds both Mac engines on an Intel Mac (GitHub's Apple Silicon machines are often
unavailable), so the Apple Silicon engine needs Apple Silicon builds of GMP and libomp to
link against. Homebrew itself only fetches builds for the machine it runs on; its public
catalogue lists them all. Picks the build for the oldest macOS available, the closest to the
engine's own minimum (macOS 12).
"""
import hashlib
import json
import sys
import urllib.request

ORDER = ["monterey", "ventura", "sonoma", "sequoia", "tahoe", "golden_gate"]   # oldest first


def main(name: str, out: str):
    info = json.load(urllib.request.urlopen("https://formulae.brew.sh/api/formula/%s.json" % name, timeout=60))
    files = info["bottle"]["stable"]["files"]
    tags = ["arm64_" + o for o in ORDER if "arm64_" + o in files]
    if not tags:
        sys.exit("Homebrew has no Apple Silicon macOS build of %s (has: %s)" % (name, ", ".join(sorted(files))))
    tag = tags[0]
    # GitHub's container registry, which hosts the bottles, takes this anonymous token
    req = urllib.request.Request(files[tag]["url"], headers={"Authorization": "Bearer QQ=="})
    data = urllib.request.urlopen(req, timeout=300).read()
    if hashlib.sha256(data).hexdigest() != files[tag]["sha256"]:
        sys.exit("checksum mismatch for %s (%s)" % (name, tag))
    with open(out, "wb") as f:
        f.write(data)
    print("%s %s for %s: %d KB, checksum ok" % (name, info["versions"]["stable"], tag, len(data) // 1024))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
