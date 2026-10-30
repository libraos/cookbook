# Get started

Run a LibraOS kernel on your laptop and build on it, one small example at a
time.

Follow the [learning paths](../docs/learning-paths.md): First Agent → Ticket
Routing → choose Knowledge, Tools or Memory. Sign-in below is an optional
application-development branch. For Python recipes, use the
[shared environment and local token setup](../docs/recipe-setup.md).

| Example | What it shows |
|---|---|
| [`01-first-agent/`](01-first-agent/) | Create an agent and talk to it: a token, one `POST /v1/agents`, one chat call. Python with the SDK (`first-agent.py`), Bash (`first-agent.sh`) or TypeScript (`first-agent.ts`). |
| [`02-sign-in-with-libraos/`](02-sign-in-with-libraos/) | A browser app that signs a person in with LibraOS (OIDC + PKCE, written by hand) and shows who they are. |
| [`../apps/personal-assistant/`](../apps/personal-assistant/) | Everything together: a signed-in user chats with an app's agent that knows their documents and remembers them. |

## Prerequisites

- Docker with Compose v2.
- Python 3.10 or newer (for the Python example: `pip install libraos-sdk`).
- Node.js 20 or newer (for the TypeScript examples).
- A model. Either an OpenAI-compatible endpoint and key, or
  [Ollama](https://ollama.com) on this machine. The personal assistant also
  needs an embedding model from the same kind of endpoint.

## Start the kernel

```bash
cd get-started
cp .env.example .env
```

Edit `.env`:

- `LIBRA_OS_JWT_SECRET`: any long random string (`openssl rand -hex 32`).
- `LIBRA_OS_ADMIN_PASSWORD`: the first admin account's password (12+ characters).
- The secret after `LIBRA_OS_SERVICE_CLIENTS=quickstart:admin=`: the examples
  swap it for an admin token.
- Pick one model block. For Ollama, `ollama pull qwen3:8b` first.
- Pick the matching embedding lines (`LIBRA_OS_EMBEDDING_API_BASE`, without
  `/v1`, and `LIBRA_OS_EMBEDDING_MODEL`) if you'll run the personal assistant.
  For Ollama, `ollama pull qwen3-embedding:8b` first.
- `PA_DEMO_PASSWORD` if you'll run the personal assistant.

```bash
docker compose up -d
curl http://localhost:8900/health
docker compose logs -f libraos     # watch it boot
```

The kernel listens on <http://localhost:8900>. Then run the examples above,
each from its own folder.

The compose file runs kernel **v0.3.0** (`ghcr.io/libraos/libraos:v0.3.0`).
Set `LIBRAOS_VERSION` to run another. The examples here are checked on v0.3.0;
the Tools recipe needs it, and a database migrated by 0.3 should not be run
with 0.2.x again (roll forward, not back). `curl http://localhost:8900/api/version` shows the
one running.

What the compose file turns on besides the kernel and Postgres (each line is
commented in `docker-compose.yml`):

- `LIBRA_OS_OBSERVATIONAL_MEMORY=1`: per-user memory for the personal assistant.
- `LIBRA_OS_SUPERNOVA_ENABLED=true`: parse and index uploaded documents.
- A read-only mount of `apps/personal-assistant/libraos-app` into the kernel's
  apps folder, and a volume for uploaded documents.

Postgres runs `pgvector/pgvector:pg17`: the kernel stores document vectors in
Postgres (pgvector 0.8 or newer) and searches them semantically. No other
vector database is needed.

### Another port

Port 8900 taken? Pick another and keep the kernel's public URL in step:

```bash
LIBRAOS_PORT=8901 docker compose up -d        # or put LIBRAOS_PORT in your shell profile or .env
```

and set `LIBRA_OS_PUBLIC_URL=http://localhost:8901` in `.env`. The example
scripts read `LIBRAOS_PORT` from the environment too, or take
`LIBRA_OS_URL=http://localhost:8901` outright. The browser examples read
`LIBRA_OS_URL` from their own `.env` (see each README).

## Troubleshooting

**The kernel exits at start with `memlock: RLIMIT_MEMLOCK soft cap is 65536
bytes…`.** The kernel refuses Docker's default 64 KiB memlock cap. The compose
file sets `ulimits: memlock: -1`; keep it if you copy the service elsewhere
(`docker run --ulimit memlock=-1`, or `LimitMEMLOCK=infinity` under systemd).

**Postgres won't start after upgrading this compose file** (`database files
are incompatible with server`). The Postgres major version changed (16 to 17).
The volume holds only this kernel's data: `docker compose down -v`, then
`docker compose up -d`.

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

**A model server on this machine works from the host but the kernel can't
reach it.** Inside the container, `localhost` is the container itself, so
`.env.example` uses `http://host.docker.internal:11434/v1` (the compose file
maps that name to the host). A server that listens on `127.0.0.1` only is
still out of reach, though: on macOS and Windows Docker Desktop bridges it,
but on Linux `host.docker.internal` is the host's bridge address, and a
loopback-only server does not answer there. Make the server listen on all
interfaces (`OLLAMA_HOST=0.0.0.0 ollama serve`, or your server's bind
setting). If you can't, run the kernel on the host's network instead with a
local override that you don't commit:

```yaml
# docker-compose.override.yml (Linux only; the kernel is then on port 8900 of
# the host itself, and `ports:` no longer applies)
services:
  libraos:
    network_mode: host
    environment:
      LIBRA_OS_DATABASE_URL: postgresql://libraos:libraos@127.0.0.1:5432/libraos?sslmode=disable
  postgres:
    ports: ["127.0.0.1:5432:5432"]
```

and use `http://127.0.0.1:<port>/v1` as `OPENAI_API_BASE`.

**Uploads never become searchable; the log says `embedding API error 404`.**
`LIBRA_OS_EMBEDDING_API_BASE` ends in `/v1`. The kernel adds `/v1/embeddings`
itself, so give it the server root (`http://host.docker.internal:11434`, not
`…:11434/v1`). If the variable is unset, the kernel uses `OPENAI_API_BASE`,
which does end in `/v1`, and hits the same 404. The boot log's
`feature status` block shows what's active: look for `embedding_path` and
`vector_retrieval`.

**`redirect_uri_mismatch` when signing in.** The app's URL must match the
client registered in `LIBRA_OS_OIDC_CLIENTS` exactly: `localhost` is not
`127.0.0.1`, and the port and path count. Restart the kernel after editing it
(`docker compose up -d --force-recreate libraos`). If an app's port is taken
on your machine, run it with `PORT=<other>` and register that port instead.

**A feature seems to do nothing.** The boot log lists every optional feature
and the variable that turns it on:
`docker compose logs libraos | grep -E "capability|feature status"`.
