# Legaltech — contract clause extraction

End-to-end worked example: a legal-tech partner ingests an MSA (Master Services Agreement) text, has LibraOS extract clauses by type with risk flags, and lets the agent call back to the partner's clause-precedent database via a Mode B webhook.

## What this demonstrates

- **Structured output (`output_type`)** — the agent's reply is validated against a JSON Schema before it leaves LibraOS, so the partner gets a typed `{clauses: [...]}` object instead of free-text it has to re-parse. The validation (and the `repair` retry) runs on the agent chat endpoint, `POST /agents/v1/<agent>/chat`, which returns the parsed object as `output` — that is the call the script makes.
- **Mode B custom-tool webhook** — when the agent decides it needs to look up precedent for a clause, LibraOS POSTs a signed JSON payload to the partner's webhook (`X-LibraOS-Signature`, with the older `X-Nova-Signature` as fallback). The partner runs the lookup against its own clause DB and returns the result. This is the integration pattern most legal-tech partners use because the precedent corpus is partner IP and never leaves their network.
- **Employee + agent as a bundle** — custom tools live in the agent definition file (`custom_tools:` frontmatter), so the script builds the `contracts-reviewer` employee and its agent as a bundle zip in memory and imports it with `POST /v1/managed/employees/bundle/import`. The employee is where a per-employee `model_config` cascade would go. From kernel v0.3.0 the import loads the agent at once, and `POST /v1/agents` also takes `custom_tools` (see [Tools](../tool-calling/)).

## Files

| File | Role |
|---|---|
| `contract_clause_extraction.py` | Main partner-side script: creates the agent, sends the MSA, prints the structured output |
| `webhook_server.py` | FastAPI server hosting the `lookup_clause_precedent` tool callback (Mode B) |
| `sample_msa.txt` | Synthetic MSA text used as input |

## Run

Tested against kernel v0.3.0 with `libraos-sdk` 2.0.0.

The kernel signs callbacks with a secret it holds itself, named by the tool's `secret_ref`, and only sends them to hosts it is allowed to. On the LibraOS host:

```bash
LIBRA_OS_CALLBACK_SECRET_LEGAL=<webhook secret>             # the secret_ref this recipe uses
LIBRA_OS_CALLBACK_ALLOWED_HOSTS=partner.example             # host(s) of LIBRA_OS_CB_URL (https)
```

In one terminal, start the partner's webhook server with the same secret:

```bash
pip install libraos-sdk fastapi uvicorn
export LIBRA_OS_CB_SECRET=<webhook secret>
uvicorn webhook_server:app --port 8080
```

In another terminal, run the extraction with the matching secret + your LibraOS credentials:

```bash
export LIBRA_OS_URL=https://nova.your-company.example
export LIBRA_OS_API_KEY=msk_live_...
export LIBRA_OS_CB_URL=https://partner.example/nova/cb/   # public URL of the webhook server above
export LIBRA_OS_CB_SECRET=<same value as above>
python contract_clause_extraction.py
```

You'll see the bundle import confirmed, then the agent extract clauses, call back to the precedent-lookup tool one or more times (one `POST /nova/cb/...` line per call in the first terminal — the smoke check that the callback arrived and its signature verified), and finally print a JSON object listing every clause with its type, risk flag, and precedent score.

> **Local testing:** the kernel refuses plain `http://` and loopback callback targets unless the host is listed in `LIBRA_OS_CALLBACK_DEV_HOSTS` (e.g. `localhost:8080`). `LIBRA_OS_CB_SECRET_REF` overrides the `secret_ref` (default `LIBRA_OS_CALLBACK_SECRET_LEGAL`). The API key must be allowed to import employee bundles (an admin token is).

## Adapting to your data

Replace `sample_msa.txt` with your contract corpus. The agent's output schema is declared inline in `contract_clause_extraction.py` — extend it with whatever clause types and risk dimensions your reviewers care about. For partner-side precedent lookup, swap the in-memory dict in `webhook_server.py` for a real query against your clause DB.
