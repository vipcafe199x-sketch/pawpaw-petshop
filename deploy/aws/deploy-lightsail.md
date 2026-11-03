# Deploy PawPaw to AWS Lightsail

This package is prepared for a **single-instance pilot**, not high availability. No AWS credentials were available while building it, so follow these steps in your account.

## 1. Create the instance

1. AWS Console → Lightsail → Create instance → Linux/Unix Ubuntu 24.04, region nearest your customers (Singapore or Mumbai are reasonable starting points).
2. Choose the current Linux bundle around 2 GB RAM. AWS currently lists a $12/month bundle with 2 GB RAM, 2 vCPUs, 60 GB SSD and 3 TB transfer; re-check region pricing before creating it.
3. Attach a static IP. In Networking, allow TCP 80 and 443 from the internet and SSH (22) only from your own IP.
4. If you have a domain, point its A record to the static IP. Domain registration/transfer fees may not be covered by AWS credits.

## 2. Install Docker and upload the project

SSH into the instance, then install Docker Engine and the Compose plugin using the official Docker instructions for Ubuntu. Transfer and extract `pawpaw-petshop-aws.zip` into `/opt/pawpaw` using SCP or the Lightsail browser SSH upload flow.

## 3. Configure secrets and domain

```bash
cd /opt/pawpaw
cp .env.example .env
```

Edit `.env` on the VM. Set:

- `APP_ENV=production`
- `APP_SECRET` to a cryptographically random value of at least 40 characters
- `ADMIN_EMAIL` to your administrator email
- `ADMIN_PASSWORD` to a unique password of at least 14 characters
- `PUBLIC_BASE_URL=https://your-domain`
- `CADDY_SITE=your-domain`
- `DATABASE_PATH=/app/data/pawpaw.sqlite3`

Keep `.env` private; never upload it to a public repository or include it in a shared source archive.

## 4. Start and verify

```bash
chmod +x deploy/aws/deploy-lightsail.sh deploy/aws/backup-db.sh
./deploy/aws/deploy-lightsail.sh
docker compose logs --tail=100 app caddy
```

Open `https://your-domain`, then check `https://your-domain/api/health` and `https://your-domain/admin`. Caddy obtains and renews TLS certificates when the domain resolves to the VM and ports 80/443 are reachable. If testing without a domain, set `CADDY_SITE=:80` and `PUBLIC_BASE_URL=http://<static-ip>`; do not use that HTTP-only configuration for real customer accounts.

## 5. Billing guardrails

Check the AWS Billing → Credits page for the exact remaining balance, eligible products and expiration. Set the account/project spend limit and 50/75/90% alerts where available. AWS credits apply only to eligible charges and may expire; usage over the credit balance or ineligible charges can bill the payment method. The basic VM estimate excludes optional snapshots, domain registration, taxes and transfer overages.

The seed admin login uses the values from `.env`. The local development demo password is not suitable for AWS; replace it before first production start. Create an encrypted off-instance backup regularly with `./deploy/aws/backup-db.sh`, and rehearse restoring it.

For real payments, online provider integration, signed webhooks, refunds, email/SMS and shipping carrier calls, configure provider accounts and credentials first. The MVP currently accepts COD only.
