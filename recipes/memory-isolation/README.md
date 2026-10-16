# Memory — recall and user isolation

**L2, independent branch.** Prerequisite: First Agent, memory enabled and two
normal authenticated users. Tools and Document Q&A are not prerequisites.

The observable result is that **A recalls a unique synthetic preference in a
fresh conversation, while B cannot recall it**. The script sends no old message
history to the recall calls. B also attempts to select A through `X-End-User`;
a normal user's authenticated identity must remain authoritative.

## Run

Use Python 3.12 and [shared setup](../../docs/recipe-setup.md), which explains how
to obtain the admin setup token and two normal-user tokens. Alternatively install
this directory's `requirements.txt` (SDK 2.0.0 and HTTPX).

Required environment:

- `LIBRA_OS_URL`: your disposable Runtime.
- `LIBRA_OS_API_KEY`: setup identity permitted to create/delete a temporary public agent.
- `LIBRA_OS_USER_A_TOKEN` and `LIBRA_OS_USER_B_TOKEN`: different ordinary users in
  the same organization, with permission to chat with that public agent.
- On the **kernel**, `LIBRA_OS_OBSERVATIONAL_MEMORY=1` and its persistence setup.
  The common Compose file already enables memory.

```bash
python recipes/memory-isolation/memory_isolation.py
```

The script validates `/oauth/userinfo` and memory availability, creates an agent
with a unique name, teaches A a random tea label, and prints a JSON evaluation:
`a_recalled`, `b_isolated`, `b_override_isolated`, and the observed responses.
It exits nonzero if any check fails. No specific refusal wording is required.

The temporary agent is deleted in `finally`. This does **not** promise deletion
of its conversation or memory records. Use only the synthetic demo preference
and reset the disposable environment when stored data must be erased.

## What is and is not proven

```bash
# Client protocol tests, no Runtime/model.
python -m pytest tests/test_memory_isolation.py

# Real identity and recall behavior; explicit opt-in.
COOKBOOK_LIVE=1 python -m pytest tests/test_live.py -k memory --junitxml=live-results.xml
```

Offline tests prove separate bearer tokens, fresh conversation IDs, no accidental
history forwarding, identity preflight rejection and correct override-header
serialization. They do **not** prove server isolation.

Live tests combine the real authorization boundary with probabilistic model
recall. They first require successful A recall; an empty/unavailable memory
system must not count as an isolation success. An absent random label in B's
answer is evidence for this scenario, not an exhaustive security proof. Repeat
with different labels/models; report failures separately from protocol CI.

Do not substitute a single admin token with different `end_user` values for
these two normal-user tokens. Trusted service impersonation, canonical user
identity and regular-user permissions have different contracts. The existing
customer-support pattern must be checked for the chosen integration identity.

**Validation status:** SDK 2.0.0 protocol tests pass. Live Runtime/model results
have not been recorded for this new example. See [validation](../../docs/validation.md).
Next: [Personal Assistant](../../apps/personal-assistant/) for a complete signed-in app.
