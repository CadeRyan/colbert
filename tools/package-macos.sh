#!/usr/bin/env bash
# The Mac download: a disk image holding Colbert.app, a link to Applications to drag it onto,
# and a short note on opening an app that isn't signed by Apple.
#
#   tools/package-macos.sh dist/Colbert.app Colbert-macOS.dmg
set -euo pipefail
APP=$1
OUT=$2
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
cat > "$STAGE/How to open Colbert.txt" <<'EOF'
1. Drag Colbert onto Applications.
2. Open Colbert from your Applications folder. It opens in your web browser.

The first time, macOS may say it can't check Colbert for malicious software, because
Colbert isn't signed with a paid Apple developer certificate. To open it anyway:

   System Settings -> Privacy & Security -> scroll down -> "Open Anyway" next to Colbert,
   then confirm with your password or Touch ID.

You only need to do this once. The source code is public:
https://github.com/CadeRyan/colbert
EOF

rm -f "$OUT"
for attempt in 1 2 3; do              # hdiutil occasionally reports "Resource busy" on CI
  hdiutil create -volname Colbert -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "$OUT" && exit 0
  sleep 5
done
exit 1
