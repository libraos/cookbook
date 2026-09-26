# Get started

Run a LibraOS kernel on your laptop and build on it, one small example at a
time.

| Example | What it shows |
|---|---|
| [`01-first-agent/`](01-first-agent/) | Create an agent and talk to it: a token, one `POST /v1/agents`, one chat call. Bash (`first-agent.sh`) or TypeScript (`first-agent.ts`). |
| [`02-sign-in-with-libraos/`](02-sign-in-with-libraos/) | A browser app that signs a person in with LibraOS (OIDC + PKCE, written by hand) and shows who they are. |
| [`../apps/personal-assistant/`](../apps/personal-assistant/) | Everything together: a signed-in user chats with an app's agent that knows their documents and remembers them. |

## Prerequisites

- Docker with Compose v2.
- Node.js 20 or newer (for the TypeScript examples).
- A model. Either an OpenAI-compatible endpoint and key, or
  [Ollama](https://ollama.com) on this machine.

## Start the kernel

```bash
cd get-started
cp .env.example .env
```

Edit `.env`:

- `LIBRA_OS_JWT_SECRET`: any long random string (`openssl rand -hex 32`).
- `LIBRA_OS_ADMIN_PASSWORD`: the first admin account's password.
- The secret after `LIBRA_OS_SERVICE_CLIENTS=quickstart:admin=`: the examples
  swap it for an admin token.
- Pick one model block. For Ollama, `ollama pull qwen3:8b` first.
- `PA_DEMO_PASSWORD` if you'll run the personal assistant.

```bash
docker compose up -d
curl http://localhost:8900/health
docker compose logs -f libraos     # watch it boot
```

The kernel listens on <http://localhost:8900>. Then run the examples above,
each from its own folder.

The compose file runs kernel **v0.1.21** (`ghcr.io/libraos/libraos:v0.1.21`).
Set `LIBRAOS_VERSION` to run another; the personal assistant needs v0.1.21 or
newer. `curl http://localhost:8900/api/version` shows the one running.

What the compose file turns on besides the kernel and Postgres (each line is
commented in `docker-compose.yml`):

- `LIBRA_OS_OBSERVATIONAL_MEMORY=1`: per-user memory for the personal assistant.
- `LIBRA_OS_SUPERNOVA_ENABLED=true`: parse and index uploaded documents.
- A read-only mount of `apps/personal-assistant/libraos-app` into the kernel's
  apps folder, and a volume for uploaded documents.

## Troubleshooting

**The kernel exits at start with `memlock: RLIMIT_MEMLOCK soft cap is 65536
bytes…`.** The kernel refuses Docker's default 64 KiB memlock cap. The compose
file sets `ulimits: memlock: -1`; keep it if you copy the service elsewhere
(`docker run --ulimit memlock=-1`, or `LimitMEMLOCK=infinity` under systemd).

**Sign-in redirects to the wrong host, or tokens are rejected as the wrong
issuer.** `LIBRA_OS_PUBLIC_URL` must be the URL a *browser* uses to reach the
kernel, e.g. `http://localhost:8900`. The kernel stamps it into every token as
`iss` and uses it to build links such as user invitations. If you change
`LIBRAOS_PORT`, change this too.

**Chats hang, or the log says `model preflight: … FAILED`.** The kernel uses
three model tiers: `OPENAI_MODEL` answers, `LIBRA_OS_BRAIN_MODEL` plans and
routes, and `LIBRA_OS_SKILL_MODEL` runs tools. Point all three at a model your
endpoint actually serves. `.env.example` sets all three from `MODEL`. Check
what's served with `curl $OPENAI_API_BASE/models`.

**Ollama works on the host but the kernel can't reach it.** Inside the
container, `localhost` is the container itself, so `.env.example` uses
`http://host.docker.internal:11434/v1`. By default Ollama listens on 127.0.0.1
only, which the container can't reach. Start it listening on all interfaces:
`OLLAMA_HOST=0.0.0.0 ollama serve` (or set `OLLAMA_HOST` in its service
config).

**`redirect_uri_mismatch` when signing in.** The app's URL must match the
client registered in `LIBRA_OS_OIDC_CLIENTS` exactly: `localhost` is not
`127.0.0.1`, and the port and path count. Restart the kernel after editing it
(`docker compose up -d --force-recreate libraos`).

**A feature seems to do nothing.** The boot log lists every optional feature
and the variable that turns it on:
`docker compose logs libraos | grep -E "capability|feature status"`.
