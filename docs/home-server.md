# The apps on a Raspberry Pi

Built on 17 September 2026. This was a plan; it is now a record of what was done, with the
bits that are still outstanding at the end.

## What it replaced

Both apps ran as launchd agents on the laptop, published to the tailnet with
`tailscale serve`. They were up only while the laptop was awake and logged in, and only
tailnet devices could reach them, so a guest would have had to install Tailscale and be
invited before they could look at a recipe.

## What runs now

```
phone/laptop/guest on the house wifi
        │  https://recipes.julianjelfs.co.uk
        │  (public DNS answers with a private address: 192.168.68.69)
        ▼
Raspberry Pi 4 2GB, "pi", on wifi
  Caddy :443 ── Let's Encrypt certificate, DNS-01 through Cloudflare
    └── recipes.julianjelfs.co.uk → 127.0.0.1:8010  (uvicorn, systemd)
  Tailscale ── pi.tail50bfbf.ts.net:8445, for away from the house
```

Public DNS holding a private address is normal and safe: anyone outside the house resolves
the name to 192.168.68.69 and gets nowhere. The cost is that the name itself is public.

**The names are not under a `.home` label.** The plan put everything under
`*.home.julianjelfs.co.uk` behind one wildcard certificate. Naming the hosts explicitly is
shorter to type on a phone, and the Pi then holds certificates for exactly those names
rather than for anything on the domain. Adding an app later costs a DNS record and three
lines of Caddyfile.

## How it was built

**The Pi.** Raspberry Pi OS Lite 64-bit (Debian 13, trixie), written with Raspberry Pi
Imager, with hostname, wifi, locale and an SSH public key set in Imager's options before
writing. The preloaded card that came with the board held the desktop image and would have
needed a monitor and a micro-HDMI cable for its first-boot wizard.

`uv` from Astral's installer. No Node: the frontend is built on the laptop and copied
across, which is what keeps a 2GB board comfortable and sidesteps arm64 builds of `sharp`.

A user created by Imager gets password-required sudo, unlike the old `pi` user. Passwordless
sudo was granted deliberately in `/etc/sudoers.d/`, which is what makes `recipes rebuild`
work without a prompt.

**The service.** `deploy/recipes.service`, binding loopback only. `ExecStart` points
straight at the venv's uvicorn rather than going through `uv run`, because uv re-resolves
the environment on every start: that alone was 13 seconds of a Pi 4's startup, and 7.3
seconds without it. Logging goes to the journal, since an SD card has a finite number of
writes and a second log file to rotate earns nothing.

**Caddy.** Debian's `caddy` package cannot load plugins, so the official apt repo, then
`caddy add-package github.com/caddy-dns/cloudflare`. The certificate comes over DNS-01
because nothing here is reachable from the internet and the usual HTTP challenge needs a
public address on port 80. Validation took 11 seconds. Caddy renews every 60 days on its
own. The token lives in `/etc/caddy/cloudflare.env`, root-only, scoped to Zone → DNS →
Edit on this one zone.

**DNS.** `julianjelfs.co.uk` moved from Route 53 to Cloudflare. The zone had no DNSSEC, no
MX and no TXT records, so the move was safe; the only live records were an apex and `www`
pointing at an old S3 site, which were deleted. Records must be **DNS only**, not proxied:
a proxied record cannot point at a private address.

**Backups.** `deploy/backup.sh` nightly at 03:30 via a systemd timer, keeping 14. It uses
SQLite's online backup API rather than `cp`, so it snapshots consistently while uvicorn
keeps serving, then reads the result back and checks both its integrity and that it holds
any recipes at all. An empty or corrupt backup fails the run instead of quietly rotating
fourteen good copies out of existence. `deploy/pull-backups.sh` copies them to the laptop
daily, keeping 30, deliberately without `rsync --delete`.

## Things worth knowing next time

**A migration that drops a table cascades to its children, and `PRAGMA foreign_keys` is a
no-op inside a transaction.** `db.migrate` sets it outside the transaction and runs
`foreign_key_check` afterwards. Invariant 23 pins it. This was found before it ate anything.

**Cloudflare's negative cache is 1800 seconds.** Deleting the old records, switching
nameservers and only then adding the new ones left a window where resolvers cached
"doesn't exist" for the new names. It looks exactly like DNS rebinding protection and is
not. Add the records before switching the nameservers.

**The Pi is not what makes an import slow.** Fetch is network-bound and identical to the
laptop; extract is 0.41s against 0.06s, on the largest page in the library. The rest is the
Haiku call, which takes the same time from anywhere.

## Outstanding

- **Triad Trainer still runs on the laptop.** The DNS record `triads.julianjelfs.co.uk`
  exists and points at the Pi, and the Caddyfile has its block ready and commented out.
- **Confirm the house name resolves on the wifi.** At the time of writing the Deco and
  Virgin's resolver were still inside the 1800s negative cache. If the name stays dead once
  that has passed, Virgin's resolver is stripping private answers: point the Deco's upstream
  DNS at 1.1.1.1, or run AdGuard Home on the Pi and hand it out as the network's DNS.
- **Install the PWA on phones from the house address**, not the tailnet one. A PWA is
  installed per origin.
- **A USB SSD, £25-30**, if the SD card ever proves the weak point. Both Pi 4 and 5 boot
  from USB. Backups make a card failure an hour's annoyance rather than a loss.
- **Delete the Route 53 hosted zone** once Cloudflare has been answering for a while, to
  stop the charge.
- **The Anthropic key sits on a machine everyone on the wifi can reach**, and the import
  button spends money. Among people you know that's fine. If it ever matters: a guest wifi
  network that can't see the Pi, or a spending cap on the key.
