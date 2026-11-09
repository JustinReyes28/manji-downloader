#!/usr/bin/env bash
# Build the Linux binary + platform package, publish both to the local registry,
# then install and run the documented npm entry points exactly as an end user would.
set -euo pipefail

REGISTRY="${REGISTRY:-http://registry:4873}"
PX_WORK="${PX_WORK:-/src}"
VERSION="$(node -p "require('${PX_WORK}/package.json').version")"

case "$(uname -m)" in
  x86_64) ARCH=x64 ;;
  aarch64 | arm64) ARCH=arm64 ;;
  *)
    echo "unsupported container architecture: $(uname -m)" >&2
    exit 1
    ;;
esac
PLATFORM="linux-${ARCH}"

echo "== waiting for registry at ${REGISTRY} =="
i=0
until node -e "fetch('${REGISTRY}/-/ping').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "registry did not become ready" >&2
    exit 1
  fi
  sleep 1
done

echo
echo "== building ${VERSION} standalone binary =="
cd "${PX_WORK}"
uv run pyinstaller manji.spec --distpath "${PX_WORK}/dist" \
  --workpath "${PX_WORK}/build/pyinstaller" --noconfirm >/tmp/pyinstaller.log 2>&1
cat /tmp/pyinstaller.log | tail -3
"${PX_WORK}/dist/manji" version

echo
echo "== generating npm platform package (${PLATFORM}) =="
uv run python scripts/build_platform_package.py \
  --platform "${PLATFORM}" \
  --binary "${PX_WORK}/dist/manji" \
  --output /tmp/npm-platform
ls -l "/tmp/npm-platform/${PLATFORM}"

echo
echo "== packing tarballs =="
mkdir -p /tmp/pkgs
npm pack --pack-destination /tmp/pkgs >/dev/null
(cd "/tmp/npm-platform/${PLATFORM}" && npm pack --pack-destination /tmp/pkgs >/dev/null)
ls -l /tmp/pkgs

echo
echo "== publishing to ${REGISTRY} =="
# npm refuses to publish with no credentials at all, so create a throwaway
# account through Verdaccio's adduser endpoint and use the returned token.
TOKEN="$(node -e '
  const registry = process.argv[1];
  const body = JSON.stringify({ name: "smoke", password: "smoke-pass", email: "smoke@example.test" });
  fetch(`${registry}/-/user/org.couchdb.user:smoke`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body,
  })
    .then((r) => (r.ok ? r.json() : r.text().then((t) => Promise.reject(new Error(`${r.status} ${t}`)))))
    .then((data) => {
      if (!data.token) throw new Error("no token in response");
      process.stdout.write(data.token);
    })
    .catch((error) => {
      console.error(error.message);
      process.exit(1);
    });
' "${REGISTRY}")"
echo "token acquired (${#TOKEN} chars)"
npm config set "//$(echo "$REGISTRY" | cut -d/ -f3)/:_authToken" "${TOKEN}"

npm publish "/tmp/pkgs/manji-downloader-${PLATFORM}-${VERSION}.tgz" \
  --registry "${REGISTRY}" --access public
npm publish "/tmp/pkgs/manji-downloader-${VERSION}.tgz" \
  --registry "${REGISTRY}" --access public
npm view manji-downloader version --registry "${REGISTRY}"

echo
echo "== simulating a clean user machine =="
mkdir -p /home/tester && cd /home/tester
npm config set registry "${REGISTRY}"
npm config set update-notifier false
export npm_config_registry="${REGISTRY}"

echo
echo "--- npx manji-downloader --help ---"
npx --yes "manji-downloader@${VERSION}" --help < /dev/null
echo
echo "--- npx manji-downloader version ---"
npx --yes "manji-downloader@${VERSION}" version < /dev/null
echo
echo "--- npx manji-downloader adapters list ---"
npx --yes "manji-downloader@${VERSION}" adapters list < /dev/null

echo
echo "--- npm install -g manji-downloader ---"
npm install -g "manji-downloader@${VERSION}"
which manji
manji version
echo
echo "--- manji --help (global install) ---"
manji --help < /dev/null
echo
echo "--- manji adapters list (global install) ---"
manji adapters list < /dev/null

echo
echo "== installed npm tree =="
npm ls -g --depth=0

echo
echo "ALL NPM SMOKE CHECKS PASSED"
