# Moving the apps to a Raspberry Pi

A plan, not instructions to run yet. It covers Recipe for Disaster and Triad Trainer together,
because they'll share the machine, the certificates and the deployment pattern.

## What's wrong with today

Both apps run as launchd agents on the laptop and are published to the tailnet with
`tailscale serve`. That means:

- They're only up while the laptop is awake and logged in.
- Only devices on the tailnet can reach them, so guests would have to install Tailscale and be
  invited before they could look at a recipe.

## What we want instead

- Always on, independent of any laptop.
- Anyone on the house wifi can open them, with nothing to install.
- Still reachable from outside the house, at least for me.
- Nothing exposed to the public internet.

## The constraint that shapes everything: HTTPS

Browsers reserve several features for "secure contexts", meaning HTTPS or localhost. Over plain
`http://` on the LAN we would lose:

| Feature | Used by | Without HTTPS |
| --- | --- | --- |
| Installing as an app (manifest, share target) | Recipes | No home screen app, no sharing a recipe link to it |
| Screen Wake Lock | Recipes, cooking mode | The phone dims while you cook |
| Microphone | Triad Trainer | Voice stepping doesn't work |

So this isn't "nginx versus Tailscale". It's how to get a certificate every device already trusts,
on a network with no public address. Three ways:

1. **A real certificate for a domain we own, issued by DNS.** Let's Encrypt proves we control
   `julianjelfs.co.uk` through Route 53, never over the internet, so the Pi needs no public
   address and no open ports. Every device trusts it with zero setup. **This is the plan.**
2. **Our own certificate authority (mkcert).** No domain needed, but every device, guests
   included, has to install our CA certificate first. That's the faff we're trying to avoid.
3. **Plain HTTP.** Simplest, and gives up the table above.

`julianjelfs.co.uk` is delegated to Route 53 (`ns-1417.awsdns-49.org` and friends), and
`home`, `recipes`, `triads` and `pi` are all unused, so option 1 is open to us.

## Shape

```
phone/laptop/guest on the house wifi
        │  https://recipes.home.julianjelfs.co.uk
        │  (public DNS answers with a private address: 192.168.1.20)
        ▼
Raspberry Pi
  Caddy :443 ── wildcard certificate for *.home.julianjelfs.co.uk
    ├── recipes.home… → 127.0.0.1:8010   (uvicorn, systemd)
    └── triads.home…  → 127.0.0.1:8000   (uvicorn, systemd)
  Tailscale (for me, when away from the house)
```

Public DNS holding a private address is normal and safe: anyone outside the house resolves the
name to 192.168.1.20 and gets nowhere. The cost is that the names themselves are public, so
anyone curious can learn that `recipes.home.julianjelfs.co.uk` exists. That's an acceptable trade
for certificates that every device accepts silently.

## Pieces

**Hardware.** Raspberry Pi OS 64-bit, headless, SSH keys only. The machine barely has to do
anything: two Python web apps serving a handful of people, and Caddy in front.

**The frontend gets built on the laptop, not the Pi.** Vite and sharp are the only hungry part of
this, and they don't need to run there. `recipes rebuild` builds on the Mac and copies the result
across, which means the Pi only ever runs Python and Caddy. That decision is what makes a small,
cheap board fine, and it removes any worry about ARM builds of `sharp`.

Prices from The Pi Hut, September 2026, including VAT:

| Route | Cost |
| --- | --- |
| **Pi 4 2GB, self-assembled: board £52.80, supply £7.70, Flirc case £15.40, own microSD ~£7** | **~£83** |
| Pi 4 2GB, same but official case £4.80 with its case fan £4.80 | ~£77 |
| Pi 5 2GB, self-assembled: board £62.40, 27W supply ~£12, case with fan £9.60, own microSD | ~£91 |
| Pi 4 starter kit, 2GB (no cooling included) | £100.70 |
| Pi 5 starter kit, 2GB | £118.90 |
| Pi 5 starter kit, 4GB | £162.10 |
| Refurbished mini PC (ThinkCentre M720q, i5, 8GB, 256GB SSD) | ~£158 |

The kits cost what they do mostly because of the official 64GB card and an HDMI cable that a
headless server never uses.

**The Pi 4 takes a USB-C supply** (Raspberry Pi 15W, £7.70). The 12.5W micro-USB one is for the
Pi 3 and Zero and won't power a Pi 4 at all.

**What was ordered** (£106.50, all from The Pi Hut): Pi 4 Model B 2GB £52.80, Flirc case £15.40,
15W USB-C supply £7.70, official 64GB microSD with the OS preloaded £30.60. The card is dearer
than one from a normal retailer, but not by enough to justify a second order.

**First boot has to be headless**, because the parts order has no micro-HDMI cable. The card ships
with the desktop OS, no wifi credentials, no hostname, and SSH off by default, so it can't just be
plugged in and reached over the network. Two ways:

- **Rewrite the card with Raspberry Pi Imager** (preferred): Raspberry Pi OS Lite 64-bit, with
  hostname, wifi and an SSH key set in Imager's options before writing. Five minutes, and Lite
  drops a desktop that a 2GB server has no use for.
- **Keep the preloaded image and prepare the boot partition by hand** from the Mac: an empty file
  named `ssh`, plus a `custom.toml` with the user and wifi details. Works, but more to typo.

Wiring the Pi to a spare ethernet port on a Deco unit removes the wifi half of this, but SSH still
has to be enabled one of those two ways.

2GB is plenty for running the apps. 4GB would only matter if the Pi built the frontend, which it
won't. The Pi 5 is the better machine, but nothing here is waiting on the CPU.

**Cooling.** The Pi 5's official case includes a fan and heatsink. The Pi 4's £4.80 case includes
neither, and it's a sealed plastic box. This machine idles almost all the time, so it would
survive bare, but it would sit warm for no reason. Two cheap fixes:

- **Flirc case, £15.40.** An aluminium body that cools the chip through a thermal pad. Silent, no
  moving parts, nothing to fail. **Preferred**, because this thing will live in the house.
- **Official case fan, £4.80**, which includes a heatsink and fits the official case. Cheaper, and
  it's a small fan a few feet from where people sit.

**Storage.** SD cards fail from constant small writes, and the recipe database will be the only
copy of anything that matters. Two honest options:

- **Run from the SD card and take the backups seriously**: nightly dump copied off the Pi, as
  below. A card costs a few pounds to replace, and with backups a failure is an hour's annoyance.
  Fine to start here.
- **Add a USB SSD later, about £25-30.** Both the Pi 4 and Pi 5 boot from USB. Worth doing once
  the thing has proved itself useful.

NVMe via the M.2 HAT+ (£11.50 plus a 2230/2242 drive) or the Raspberry Pi SSD Kit (256GB, £69.20)
is faster than any of this needs, and awkward with the official Pi 5 case: the HAT only fits by
removing the lid and fan insert, and the cover can't go back on.

**DNS host.** Move `julianjelfs.co.uk` to Cloudflare DNS. It's free, where Route 53 charges about
$0.50 a month per zone, and its credential is a single API token scoped to this zone's DNS rather
than an IAM user, a policy and an access key pair. Caddy's Cloudflare module is also the most
travelled path for this exact job.

The switch is safe: DNSSEC is off (no DS records at the registry), and there are no MX or TXT
records, so no email depends on the domain. One thing does: the apex and `www` still answer over
HTTP from an old S3 static site, with no HTTPS. Moving nameservers drops it unless those records
are recreated at Cloudflare. Worth deciding whether that site is wanted before switching.

In Cloudflare, records must be "DNS only", not proxied. A proxied record can't point at a private
address, and proxying would break LAN access.

Staying on Route 53 works too, with `caddy-dns/route53` and an IAM user restricted to the hosted
zone (`route53:ListResourceRecordSets` and `ChangeResourceRecordSets` on the zone, plus
`route53:GetChange`). Everything below is the same either way.

**DNS records.** Two A records, or one wildcard:

```
recipes.home.julianjelfs.co.uk.  A  192.168.1.20
triads.home.julianjelfs.co.uk.   A  192.168.1.20
```

The Pi needs a fixed address, set as a DHCP reservation rather than a static address on the Pi, so
nothing else is ever handed it.

**The network here.** The Virgin Media box is in modem mode, so the Deco mesh is the router and
owns DHCP. Reservations are in the Deco app under More → Advanced. Deco networks usually hand out
`192.168.68.x`, not `192.168.1.x`, so the addresses above are illustrative until the Pi is on the
network.

One thing to test on day one: some routers refuse to pass on a public DNS answer that points to a
private address, as protection against DNS rebinding. That would break this whole approach. Deco
isn't known for doing it, but it's a five-minute check once the records exist (`dig
recipes.home.julianjelfs.co.uk` from a laptop on the wifi should return the Pi's address). If it
does, AdGuard Home on the Pi, handed out as the network's DNS server, answers for these names
itself and sidesteps the router.

**Certificates.** Caddy with the `caddy-dns/cloudflare` module, which needs a build that includes
it (`xcaddy build --with github.com/caddy-dns/cloudflare`) or the equivalent package. It answers
the DNS-01 challenge by writing a TXT record, then renews on its own every 60 days. One wildcard
certificate for `*.home.julianjelfs.co.uk` covers both apps and any app we add later.

DNS-01 is the only option here. The usual HTTP challenge needs a public address on port 80, and
the Pi will have neither.

It authenticates with a Cloudflare API token limited to Zone → DNS → Edit on this one zone. The
token lives in the Caddy service's environment file, readable only by root, and can do nothing
beyond editing this domain's records.

**Caddyfile.** About as long as this:

```
*.home.julianjelfs.co.uk {
    tls { dns cloudflare }

    @recipes host recipes.home.julianjelfs.co.uk
    handle @recipes { reverse_proxy 127.0.0.1:8010 }

    @triads host triads.home.julianjelfs.co.uk
    handle @triads { reverse_proxy 127.0.0.1:8000 }
}
```

Caddy over nginx because it gets and renews certificates itself. With nginx we'd be wiring up
certbot's Route 53 plugin, a renewal timer and a reload hook by hand, for the same result.

**Services.** One systemd unit per app, replacing the launchd agents: `WorkingDirectory` on the
backend, `ExecStart` running uvicorn through uv on 127.0.0.1, `Restart=always`,
`After=network-online.target`, and an `EnvironmentFile` for the Anthropic key. Both apps keep
listening on loopback only, exactly as now, with Caddy the only thing bound to the network.

**Away from home.** Keep Tailscale on the Pi and keep `tailscale serve` for the recipes app, so it
stays reachable from a supermarket. That gives two addresses for the same app: the house name and
the `ts.net` one. Since a PWA is installed per address, install the house one on phones, and treat
the `ts.net` address as the away-from-home fallback in a browser.

## A public website on the same domain

None of this stops `julianjelfs.co.uk` being a real website. The house apps live under
`*.home.julianjelfs.co.uk`, which resolves to a private address and only works indoors. The apex
and `www` are separate records pointing anywhere public. The two never meet.

Cloudflare Pages is the easy answer once DNS is there: free, HTTPS included, deploys from a Git
repo, and it creates the records itself. GitHub Pages is equivalent. The existing S3 site could
also stay, though S3's website endpoint is HTTP-only, which is why the domain has no HTTPS today;
fixing that means CloudFront in front, which is more work than moving the site.

Worth knowing: a public site makes the domain worth poking at, and `home.julianjelfs.co.uk` easy
to discover. Those names only resolve to a private address, so there's nothing to reach from
outside, but the names themselves are public.

## Backups

Once the Pi is the only copy, `recipes.db` needs real backups:

- A systemd timer running `sqlite3 recipes.db ".backup"` nightly to a dated file.
- Copy those off the Pi, to the laptop or a NAS, since a backup on the same disk is not a backup.
- Keep the last 14, and check a restore works once rather than assuming.

`backend/.env` holds the Anthropic key, and is worth keeping in a password manager as well.

## Worth knowing

The Anthropic API key will sit on a machine that everyone on the wifi can reach, and the import
button spends money. Among people you know that's fine, but "everyone on the wifi" now includes
guests. If that ever matters, the answers are a guest wifi network that can't see the Pi, or a
spending cap on the API key in the Anthropic console.

## Work involved

1. **Pi ready:** OS, SSH keys, DHCP reservation, and uv installed. No Node: the frontend is built
   on the laptop and copied across.
2. **In the repos:** a `deploy/` folder with the systemd units, the Caddyfile and an install script
   for the Pi, alongside the existing macOS ones. Same for Triad Trainer.
3. **`recipes` command:** either run it on the Pi over SSH, or keep it on the laptop as a wrapper
   that SSHes in. `rebuild`, `status` and `logs` all still make sense, with `serve` and `unserve`
   dropping away since Caddy handles that.
4. **DNS:** move the domain to Cloudflare, create the API token, and add the A records.
5. **Move the data:** copy `recipes.db` and `.env` across, and stop the laptop agents.
6. **Backups:** the timer and the off-Pi copy.
7. **Check:** open both apps from a phone with Tailscale turned off, install the recipes app from
   the house address, and confirm the screen stays awake in cooking mode and Triad Trainer gets
   the microphone.

Only the Python side installs on the Pi, and `lxml` and `trafilatura` both publish arm64 wheels, so
`uv sync` should be dull. `sharp` never goes near it: it belongs to the icon script and the
frontend build, which both stay on the laptop.

## Open questions

- Does Triad Trainer move at the same time, or does it stay on the laptop until the recipes app
  has proved the setup?

Settled: the domain moves from Route 53 to Cloudflare; hardware is a Pi 4 2GB in a Flirc case
running from microSD, with a USB SSD as a later upgrade; the Deco mesh is the router, with the
Virgin box in modem mode; the old S3 site at the apex can go.
