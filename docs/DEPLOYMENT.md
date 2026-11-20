# Deploying HousingSearch

| | Render (free) | Oracle Cloud Always Free | Hugging Face Spaces |
|---|---|---|---|
| Cost | Free plan | Free (card for verification) | Docker Spaces need **PRO** (~$9/month) |
| Best for | A shareable public demo | Real data you import and keep, scheduled imports, custom domain | If you already pay for PRO |
| Effort | ~5 minutes, one click | 1–2 hours | ~5 minutes, one command |
| Data | Resets on restart (demo data reloads automatically) | Kept on disk | Resets unless you add paid storage |
| Always on | Sleeps after 15 min idle, ~1 min to wake | Yes | Yes (PRO) |

---

## Render (recommended for a free demo)

The repo contains `render.yaml`, a Render *Blueprint* that builds the `Dockerfile` on the free plan in the Singapore region.

1. Open **https://render.com/deploy?repo=https://github.com/bhagathchan1/HousingSearch** (or click the *Deploy to Render* button in the README).
2. Sign in to Render (easiest: *Sign in with GitHub*).
3. Press **Deploy Blueprint**. The first build takes about 3–5 minutes; follow it under the service's **Logs**.
4. Your app is at the URL shown on the service page, e.g. `https://housingsearch-xxxx.onrender.com`.

After that, every push to `main` on GitHub redeploys automatically.

**Good to know**
* Free web services sleep after 15 minutes without traffic; the first request afterwards takes about a minute while it wakes.
* The disk is temporary, so data imported through the admin API disappears on redeploy or restart. The demo dataset reloads automatically. To keep real data, commit it to the repo (for example replace `data/seed/demo_properties.json`), or use a VM.
* `HS_ADMIN_TOKEN` is generated for you; find it under the service's **Environment** tab to use `POST /api/admin/import`.
* The app listens on the `PORT` Render provides; locally it still defaults to 8000.

---

## Hugging Face Spaces (requires PRO)

> Hugging Face now only runs Docker (and Gradio) Spaces on its free CPU hardware for **PRO** subscribers. Without PRO the deploy script stops with HTTP 402 and nothing is created.

The repo is ready for a **Docker Space**: the settings block at the top of `README.md` tells Spaces to build the `Dockerfile` and serve port 8000.

### 1. One-time setup
1. Create a free account at <https://huggingface.co/join>.
2. Create a token with **Write** access at <https://huggingface.co/settings/tokens>.

### 2. Deploy from your computer
```bash
HF_TOKEN=hf_your_token scripts/deploy_hf.sh <your-hf-username>
```
This creates the Space `<your-hf-username>/HousingSearch` if needed, uploads the last **committed** version of the code, and Hugging Face builds it (2–4 minutes; watch the **Logs** tab on the Space page). Your app will be at:

* Space page: `https://huggingface.co/spaces/<your-hf-username>/HousingSearch`
* Direct link (full screen, best for sharing): `https://<your-hf-username>-housingsearch.hf.space`

Use a different name with a second argument: `scripts/deploy_hf.sh <user> MyPropertySearch`.
Re-run the same command after every commit to redeploy.
`DRY_RUN=1 scripts/deploy_hf.sh <user>` builds the upload without sending anything.

> **Why a script instead of `git push` to the Space?** Hugging Face rejects binary files (the PNG screenshots in `docs/`) unless they are stored with Xet/LFS. The script uploads a copy without them and points the README images at GitHub.

### 3. Or deploy automatically from GitHub
`.github/workflows/deploy-hf.yml` redeploys after every push to `main` (it runs the tests first). In your GitHub repo → **Settings → Secrets and variables → Actions**:

* **Secret** `HF_TOKEN` — the write token
* **Variable** `HF_USERNAME` — your Hugging Face username
* **Variable** `HF_SPACE` — optional, defaults to `HousingSearch`

### Optional Space settings
In the Space → **Settings → Variables and secrets**:

| Name | Type | Effect |
|---|---|---|
| `HS_ADMIN_TOKEN` | Secret | Enables `POST /api/admin/import` so you can push data over HTTP |
| `HS_DB_PATH` = `/data/housingsearch.db` | Variable | Use together with paid **Persistent storage** (Settings → Persistent storage) so imported data survives restarts |

### Things to know
* The basic CPU hardware (2 vCPU, 16 GB RAM) is plenty for this app.
* On the Space page the app runs inside an iframe; some browsers block storage there, so the shortlist and notes may not be saved. Share the **direct `.hf.space` link** instead.
* Anything you import into a free Space disappears when it restarts or rebuilds. For data you want to keep, add your import files to the repo (e.g. replace `data/seed/demo_properties.json`) or move to a VM.

---

## Oracle Cloud Always Free (when you have real data)

1. Sign up at <https://www.oracle.com/cloud/free/> (needs a card for verification; Always Free resources aren't charged).
2. **Create a VM**: Compute → Instances → Create. Image *Ubuntu 22.04*, shape *VM.Standard.A1.Flex* (Ampere, Always Free; 1 OCPU / 6 GB is plenty). If you get "out of capacity", try another availability domain or later.
3. **Open the ports**: in the VCN's Security List add ingress rules for TCP 80 and 443 from `0.0.0.0/0`. On the VM itself:
   ```bash
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```
4. **Install Docker and run the app**:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
   git clone https://github.com/bhagathchan1/HousingSearch.git && cd HousingSearch
   sudo docker compose up -d --build        # data kept in the housingsearch-data volume
   ```
5. **HTTPS with your domain** (point an A record at the VM's public IP first):
   ```bash
   sudo apt install -y caddy
   echo 'yourdomain.com { reverse_proxy localhost:8000 }' | sudo tee /etc/caddy/Caddyfile
   sudo systemctl restart caddy
   ```
6. **Weekly price imports** (example cron, `crontab -e`):
   ```
   0 6 * * 1 cd ~/HousingSearch && sudo docker compose exec -T housingsearch python -m housingsearch import-quotes examples/sample_quotes.csv
   ```
7. **Update**: `git pull && sudo docker compose up -d --build`.
