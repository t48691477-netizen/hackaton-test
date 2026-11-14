# TOiR API deployment

This stack runs the FastAPI TOiR API (`app.main`) behind Caddy. It supplies HTTPS termination and deployment isolation; application access control, request limits, and upload validation remain application responsibilities and must be configured and tested as described below. The React client contract and Android mock service are separate APIs; this stack does not adapt either one.

## Prerequisites

- A Linux host with Docker Engine and Compose v2; use a recent Compose release for GPU device reservations.
- A DNS name such as `api.example.com` whose A/AAAA records point directly to this host. Remove an AAAA record if IPv6 is not routed to the host.
- Inbound TCP 80 and 443 open in the host firewall and cloud firewall/security group. No other inbound port is needed. Keep outbound internet access for image builds, first-time model downloads from Hugging Face, and optional Gemini requests.
- For CUDA, an NVIDIA GPU, supported host driver, and NVIDIA Container Toolkit. The CPU profile is the default and needs no GPU.

## Configure and start

From the repository root:

```sh
cp .env.production.example .env
```

Edit `.env`; set `DOMAIN` to the DNS name, keep `COMPOSE_PROFILES=cpu`, generate an Argon2id hash for a real 10-character access key, and set `TOIR_ACCESS_KEY_HASH`, `TOIR_ACCOUNT_ID`, `TOIR_FULL_NAME`, `TOIR_EMAIL`, and `TOIR_ROLE`. Keep `TOIR_DISABLE_DOCS=true` for production. Leave `TOIR_CORS_ORIGINS` empty for same-origin browser use and native Android; if a separate browser console is approved, set it to exact HTTPS origins separated by commas. Tune the detect concurrency/rate-limit variables only after load testing. Add `GEMINI_API_KEY` only if the Gemini integration is intended. Restrict `.env` to the deployment operator. Never put secrets in the image, build arguments, source control, or Android app. An empty Gemini key selects the rule-based fallback; it does not disable the API.

Generate the access-key hash before starting the stack:

```sh
python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash('REPLACE_WITH_A_10_CHARACTER_KEY'))"
```

The plaintext key is entered only into the Android login form or another trusted client; store only the generated hash in `.env`.

Start and inspect:

```sh
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs -f caddy api
```

Caddy obtains and renews a public certificate using ACME. The persistent `caddy_data` volume holds certificates and private key material; back it up as a secret. Caddy redirects HTTP to HTTPS, terminates public TLS, sets HSTS on HTTPS responses, and returns 404 for `/docs`, `/redoc`, and `/openapi.json` (including subpaths). The API container has no published host port; only Caddy publishes TCP 80/443.

For CUDA instead, set `COMPOSE_PROFILES=cuda` and `API_UPSTREAM=api-cuda:8000` in `.env`, then run `docker compose up --build -d`. Do not enable both profiles: both services share the persistent volumes and are not intended to run concurrently. This builds PyTorch from the CUDA 12.8 wheel index; the host's NVIDIA driver/toolkit must support it. Switch back by setting `COMPOSE_PROFILES=cpu` and `API_UPSTREAM=api:8000`.

Check HTTPS readiness with `curl -fsS https://api.example.com/health`. The Compose health check calls the existing `/health` route from inside the API container. That route proves HTTP/process reachability only: it can return healthy while either model is not loaded. Models are loaded lazily on the first inspection, weights may be downloaded then, and health is not a model-readiness or inference check. First requests can be slow or fail if the host cannot reach Hugging Face.

## Persistent data and operations

Named volumes persist SQLite data (`api_data` at `/app/data`), uploaded and annotated images (`uploaded_images` at `/app/static/uploads`), and model files (`model_weights` at `/app/weights`) across container replacement. The image copies only backend code and `static/index.html`; local weights, runtime data, and secrets are excluded from the build context. The API runs as UID 10001 with a read-only root filesystem and writable data volumes. Back up the SQLite database consistently while the API is stopped, and back up uploads/weights according to retention needs. Test restores; Docker volumes are not a backup policy.

Useful commands:

```sh
docker compose logs -f api
docker compose exec api python -c "from urllib.request import urlopen; print(urlopen('http://127.0.0.1:8000/health').read().decode())"
docker compose down
```

`docker compose down` preserves named volumes. Do not use `docker compose down -v` unless intentionally deleting the database, uploads, models, and Caddy certificates. Do not publish or bind-mount port 8000 to the host. Restrict Docker socket and host access to trusted operators.

## Required production controls

- **Access control:** the FastAPI routes require a bearer session issued by `/api/auth/login`. The configured account receives permissions from `TOIR_ROLE`: `engineer` may scan and create reports, `dispatcher` may also read/update the report queue, and `admin`/`director` may manage equipment. `/health`, the UI, and static files remain public for readiness and same-origin delivery; `/static/uploads/` is public by design in this prototype, so do not put confidential images there without adding authenticated media delivery.
- **Rate limiting:** `/api/auth/login` allows five credential checks, then applies a per-client lockout after the fifth failure. The FastAPI app applies a configurable in-process ingress limit (`TOIR_INGRESS_RATE_LIMIT`, `TOIR_INGRESS_RATE_WINDOW_SECONDS`) and a separate per-client/per-account `/api/detect` sliding-window limit (`TOIR_DETECT_RATE_LIMIT`, `TOIR_DETECT_RATE_WINDOW_SECONDS`), with non-waiting inference concurrency (`TOIR_DETECT_CONCURRENCY`). Current defaults (120 ingress requests and 30 detect requests per minute) can throttle a fast live stream; measure the target server and tune both limits to the needed frame cadence before deployment. The Android client can submit up to about 22 frames per second when responses are fast, but that is a client-side ceiling, not a measured server rate. Caddy overwrites `X-Real-IP` from its connection peer before forwarding; do not put another proxy in front without restricting origin access and configuring a trusted client-IP chain. Limits are local to one API worker; keep one worker or add a shared gateway/store before scaling horizontally. Caddy also caps request bodies at 20 MiB and should be paired with gateway connection/time limits, especially for `/api/inspect`.
- **Uploads:** `/api/detect` validates `image/jpeg`, caps the body at 5 MiB, and caps dimensions at 4096 pixels. `/api/inspect` still checks the filename extension and writes the upload to disk; it needs an edge request-body cap, upstream timeout/concurrency limits, and a future byte/signature/dimension validator before broad public exposure.
- **CORS:** the application allows no cross-origin requests unless `TOIR_CORS_ORIGINS` is set to an exact comma-separated origin list. Same-origin use of the API and static panel on `https://api.example.com` needs no browser CORS allowance. Native Android traffic is not governed by browser CORS. Never use wildcard origins for a credentialed production API.
- **TLS trust boundary:** this stack assumes Caddy receives public HTTP/HTTPS directly and is the trusted TLS terminator. Do not expose the API container or trust client-supplied forwarding headers. If placing a load balancer/CDN in front, restrict its origin access, configure its TLS and forwarded-header trust explicitly, and test redirects/client IP handling; do not assume the app currently has trusted-proxy configuration.
- Keep DNS and the firewall aligned with the certificate hostname, use a real public hostname (not an IP), protect Caddy's certificate volume, and monitor certificate/renewal and disk capacity. HSTS is set for one year without `includeSubDomains` or preload; only enable broader HSTS after every affected hostname is HTTPS-ready.

The API has no configured migration or model pre-download/readiness command. Allow first-start/first-inference time, verify both models and a representative inspection manually, and monitor disk use. `/health` reports model booleans but does not gate health on them. The LLM and model behavior, upload validation, static-media access policy, and trusted-proxy configuration remain application/deployment concerns. Certificate pinning is intentionally not enabled; decide it separately after establishing certificate rotation and recovery procedures.
