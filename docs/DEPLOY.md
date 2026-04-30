# Deploy to Oracle Cloud (Always Free)

Step-by-step for hosting this bot on an Oracle Cloud Always Free ARM Ampere VM. Oracle's free tier gives you up to 4 OCPUs / 24 GB RAM on `VM.Standard.A1.Flex` (ARM) forever — ~10× what this bot needs. For day-to-day operation (env vars, logs, reset, backup) see [USAGE.md](./USAGE.md); this file is just the one-time bring-up.

## 0. Before you start

You'll need:
- A credit/debit card. Oracle requires it for signup; **Always Free resources are not charged** as long as you don't upgrade the account to "Pay As You Go".
- An SSH keypair on your laptop. If you don't have one, run `ssh-keygen -t ed25519` (accept defaults). The public key (`~/.ssh/id_ed25519.pub`) is what you'll paste into Oracle.

This repo is private (`git@github.com:illumeow/cat.h.git`), so the VM will need GitHub access to clone. Easiest path: generate a fresh SSH key **on the VM** later (step 4) and add it as a GitHub deploy key.

## 1. Sign up

1. Go to <https://www.oracle.com/cloud/free/> → **Start for free**.
2. **Pick your home region carefully — it cannot be changed later.** Free ARM capacity is famously tight in popular regions (Ashburn, London, Frankfurt). Less-busy regions (Phoenix, San Jose, Osaka, Mumbai) tend to provision on the first try. Pick one geographically reasonable for you and trust the latency to be fine — Discord's gateway is in Cloudflare's network everywhere.
3. Verify email, enter card details, finish signup. Account provisioning takes 5–15 minutes; you'll get an email when the console is ready.

## 2. Provision the VM

In the Oracle Cloud console:

1. **Compute → Instances → Create instance**.
2. **Image**: click *Change image* → **Canonical Ubuntu** → pick the latest LTS (24.04 at time of writing). Make sure the architecture filter shows **aarch64** options.
3. **Shape**: click *Change shape* → **Ampere → VM.Standard.A1.Flex**. Set **1 OCPU, 6 GB memory**. (Free cap is 4 OCPUs / 24 GB total, but 1/6 is plenty here and leaves room for a second instance if you ever want one.)
4. **Networking**: leave defaults — Oracle creates a VCN with a public subnet, security list permitting inbound SSH (22) and all egress. That's exactly what a gateway-only bot needs.
5. **SSH keys**: select *Paste public keys* and paste the contents of `~/.ssh/id_ed25519.pub` (or upload the file).
6. **Boot volume**: leave default (50 GB). Free cap is 200 GB total.
7. **Create**.

If you get **"Out of host capacity"**: the region's ARM pool is full right now. Wait a few hours and click *Create* again, or pick a quieter region (you'd have to redo signup — only worth it if you keep failing for days).

Once the instance is **Running**, copy the **Public IP** from its details page.

## 3. SSH in

```sh
ssh ubuntu@<public-ip>
```

Default user on Ubuntu Oracle images is `ubuntu`. Accept the host key on first connect.

## 4. Install Docker + clone

```sh
# system update
sudo apt update && sudo apt -y upgrade

# Docker (official one-liner installer)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker   # picks up the new group without re-login

# generate a deploy key for this VM and print the public half
ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
```

Copy the printed public key, then in GitHub: **repo → Settings → Deploy keys → Add deploy key** → paste, leave *Allow write access* off, save.

```sh
git clone git@github.com:illumeow/cat.h.git discord-bot
cd discord-bot
cp .env.example .env
nano .env   # fill in DISCORD_TOKEN, channel IDs, TIME_ZONE, etc.
```

For `.env` content see [USAGE.md §2](./USAGE.md#2-configure).

## 5. Run

```sh
docker compose up -d --build
docker compose logs -f bot
```

First build pulls the Playwright base image (~1 GB) and takes ~5 minutes on the 1-OCPU shape. Subsequent rebuilds are layer-cached and quick. Once the bot logs `Logged in as …`, you're live.

`Ctrl-C` exits the log tail; the containers keep running. Both services have `restart: unless-stopped`, and Docker is enabled at boot by default on Ubuntu, so the bot survives VM reboots automatically — nothing else to configure.

## 6. Day-to-day

```sh
# tail logs
docker compose logs -f bot

# update to latest main
git pull && docker compose up -d --build

# stop / start
docker compose down
docker compose up -d

# back up the database to your laptop
scp ubuntu@<public-ip>:~/discord-bot/data/bot.db ./bot-backup-$(date +%F).db
```

The `./data` bind mount is where all state lives (`bot.db` + downloaded `attachments/`). The container itself is disposable — if anything breaks, `docker compose down && docker compose up -d --build` from the same `data/` directory restores you.

## 7. Gotchas specific to Oracle

- **Idle reclamation.** Oracle may reclaim Always Free compute that sits below 20% CPU / network / memory utilization at the 95th percentile across a 7-day window. A Discord bot's persistent gateway connection should stay above the network threshold, but it's not guaranteed. If you ever get an idle-warning email, the simplest mitigation is a cron job that pegs one core for ~10 minutes daily (`stress-ng --cpu 1 --timeout 600s`). Don't pre-emptively add this; only react if Oracle flags you.
- **Account upgrades.** The console occasionally nags about upgrading to "Pay As You Go". **Don't.** Always Free resources stay free indefinitely on a free account; upgrading flips billing on for everything.
- **Console session timeouts.** Oracle's web console logs you out aggressively. Bookmark the *Instances* page for your compartment to skip the navigation each time.
- **Inbound ports.** If you ever add an inbound HTTP service to the bot (none today), Oracle requires opening it in **two** places: the VCN's security list **and** Ubuntu's host iptables (Oracle pre-installs restrictive rules). Not relevant for the current gateway-only bot.

## 8. Tearing it down

If you ever want to abandon the deployment:

```sh
docker compose down -v
```

Then in the Oracle console: **Instances → ⋮ → Terminate**, check *Permanently delete the attached boot volume*. The VCN can stay (it's free); deleting it requires unwinding subnets / gateways manually.
