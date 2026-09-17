#!/usr/bin/env bash
# Install (or re-install) the recipe library on the Pi. Run it ON the Pi:
#
#   cd ~/recipe-for-disaster && ./deploy/install-pi.sh
#
# Safe to re-run: it never touches the database and never overwrites the Cloudflare
# token. What it does is put the units, the timer and the Caddyfile back the way this
# repo says they should be, which is what you want after changing any of them.
#
# It does not build the frontend. That happens on the laptop, via `recipes rebuild`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(id -un)"
TOKEN_FILE=/etc/caddy/cloudflare.env

[ "$USER_NAME" = root ] && { echo "run this as your normal user, not root" >&2; exit 1; }

echo "==> backend dependencies"
"$HOME/.local/bin/uv" --version >/dev/null 2>&1 || { echo "uv is not installed: https://astral.sh/uv" >&2; exit 1; }
(cd "$ROOT/backend" && "$HOME/.local/bin/uv" sync -q)

echo "==> systemd units"
sudo cp "$ROOT/deploy/recipes.service" /etc/systemd/system/recipes.service
sudo cp "$ROOT/deploy/recipes-backup.service" /etc/systemd/system/recipes-backup.service
sudo cp "$ROOT/deploy/recipes-backup.timer" /etc/systemd/system/recipes-backup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now recipes.service >/dev/null
sudo systemctl enable --now recipes-backup.timer >/dev/null

echo "==> Caddy"
if ! command -v caddy >/dev/null; then
	echo "   Caddy is not installed. Debian's build cannot load the Cloudflare DNS module," >&2
	echo "   so use the official repo, then: sudo caddy add-package github.com/caddy-dns/cloudflare" >&2
	exit 1
fi
caddy list-modules | grep -q dns.providers.cloudflare || {
	echo "   Caddy has no Cloudflare DNS module: sudo caddy add-package github.com/caddy-dns/cloudflare" >&2
	exit 1
}
sudo cp "$ROOT/deploy/Caddyfile" /etc/caddy/Caddyfile
sudo chown root:root /etc/caddy/Caddyfile

# The token is a credential and is not in this repo. Create an empty file rather than
# failing, so a fresh machine gets this far and tells you what is missing.
if ! sudo test -s "$TOKEN_FILE"; then
	printf '# Cloudflare API token, scoped to Zone -> DNS -> Edit on this zone\nCLOUDFLARE_API_TOKEN=\n' | sudo tee "$TOKEN_FILE" >/dev/null
fi
sudo chmod 600 "$TOKEN_FILE"
sudo chown root:root "$TOKEN_FILE"
sudo mkdir -p /etc/systemd/system/caddy.service.d
printf '[Service]\nEnvironmentFile=%s\n' "$TOKEN_FILE" | sudo tee /etc/systemd/system/caddy.service.d/override.conf >/dev/null
sudo systemctl daemon-reload

if sudo awk -F= '/^CLOUDFLARE_API_TOKEN=/{print $2}' "$TOKEN_FILE" | grep -q .; then
	sudo systemctl restart caddy
else
	# Starting without a token means failing the ACME challenge over and over, which
	# burns Let's Encrypt rate limits for the domain. Stay stopped instead.
	sudo systemctl stop caddy || true
	echo "   no token in $TOKEN_FILE, so Caddy is left stopped. Add it, then: sudo systemctl restart caddy" >&2
fi

echo "==> waiting for the app"
for _ in $(seq 1 40); do
	curl -sf -m 1 http://127.0.0.1:8010/api/health >/dev/null && break
	sleep 0.5
done
curl -sf -m 3 http://127.0.0.1:8010/api/health >/dev/null \
	|| { echo "the app did not come up; see: sudo journalctl -u recipes -n 50" >&2; exit 1; }

echo
echo "installed."
printf "  app        : %s\n" "$(systemctl is-active recipes)"
printf "  caddy      : %s\n" "$(systemctl is-active caddy)"
printf "  next backup: %s\n" "$(systemctl list-timers recipes-backup --no-pager 2>/dev/null | awk 'NR==2 {print $1, $2, $3}')"
