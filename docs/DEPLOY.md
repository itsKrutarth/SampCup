# Deploying SampCup

One small AWS Lightsail server runs everything with Docker Compose: Caddy (HTTPS),
the app (API plus website) and Postgres, with a database dump every 6 hours.

## One-time setup (owner)
1. **AWS account:** create it, turn on MFA for the root user, then create an IAM user
   for daily use. Set a billing alarm (for example $25/month).
2. **Lightsail instance:** region `us-east-1`, Ubuntu 24.04 LTS, 2 GB plan (check the current
   price on the Lightsail pricing page). Name it `sampcup`.
3. **Static IP:** create one in Lightsail and attach it to the instance.
4. **Firewall (Lightsail Networking tab):** allow 22 (SSH), 80 (HTTP) and 443 (HTTPS).
5. **DNS at Namecheap** (Domain List → sampcup.com → Advanced DNS):
   - Remove the URL Redirect record.
   - Add an `A` record, host `@`, value = the static IP.
   - Add an `A` record, host `www`, value = the static IP.

## Install on the server
```sh
ssh ubuntu@<static-ip>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit   # log in again so the group applies
git clone https://github.com/itsKrutarth/SampCup.git && cd SampCup/deploy
cp .env.example .env && nano .env        # set POSTGRES_PASSWORD (openssl rand -hex 24)
docker compose up -d --build
docker compose exec app python -m app.cli create-admin <your-username>
```
Caddy fetches the HTTPS certificate on the first visit to https://sampcup.com once DNS
points at the server.

## Updating
```sh
cd ~/SampCup && git pull && cd deploy && docker compose up -d --build
```
Migrations run automatically when the app starts.

## Backups and restore
- Dumps land in `deploy/backups/` every 6 hours; 14 days are kept. Also turn on automatic
  Lightsail snapshots for the instance.
- Restore into an empty database:
  `gunzip -c backups/<file>.sql.gz | docker compose exec -T db psql -U sampcup sampcup`

## Event week
- Move to the 4 GB plan a few days before: snapshot the instance, launch a 4 GB instance
  from the snapshot, move the static IP to it. Move back afterwards.
- Take a manual snapshot the night before and right after the event.
