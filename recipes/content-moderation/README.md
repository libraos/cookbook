# Content moderation — risk-score UGC against your policy

End-to-end worked example: a partner sends user-generated content to a moderation agent and gets back a typed `{reasoning, verdict, categories, risk_score}` decision that drives an allow / human-review / block pipeline.

## What this demonstrates

- **`output_type` JSON-schema validation** — every decision is a typed object with an `allow|flag|block` verdict, a category list, and a 0–1 risk score. Your pipeline branches on `verdict` and `risk_score`; it never parses prose. The validation (and the `repair` retry) runs on the agent chat endpoint, `POST /agents/v1/<agent>/chat`, which returns the parsed object as `output` — that is the call the loop makes.
- **`brain=false` + `tool_scope="none"`** — one short call per item on the skill tier, with the tool catalog kept out of the prompt: a classifier needs no tools.
- **App policy layered on the platform firewall** — LibraOS ships an **AI Firewall** as an inbound guardrail (prompt-injection / jailbreak / abuse detection) that runs on *every* request before your agent sees it, tunable via `LIBRA_OS_FIREWALL_THRESHOLD`. This recipe adds your *domain* moderation policy on top. The two are complementary: the firewall protects the platform; this agent enforces your community standards.
- **Risk banding over a hard label** — returning a continuous `risk_score` alongside the verdict lets you set your own automation bands (auto-block high, human-review the middle, auto-allow low) and move them without retraining anything.

## Files

| File | Role |
|---|---|
| `content_moderation.py` | Registers the moderator, runs a labelled set, reports verdict accuracy |
| `sample_content.jsonl` | 6 labelled UGC snippets (`{"content": ..., "expected": ...}`) |

## Run

Tested against kernel v0.3.0 with `libraos-sdk` 2.0.0.

```bash
pip install libraos-sdk
export LIBRA_OS_URL=https://nova.your-company.example
export LIBRA_OS_API_KEY=msk_live_...
python content_moderation.py
```

```
✓ expected=allow got=allow risk=0.02 cats=none :: Thanks everyone for the warm welcome …
✓ expected=block got=block risk=0.94 cats=spam :: Check out my store for 90% OFF designer …
✓ expected=flag  got=flag  risk=0.61 cats=harassment :: You're all idiots and this product …

Verdict accuracy: 6/6 = 100%
```

Scores and the exact accuracy depend on the model the kernel routes the skill tier to. With `gemini/gemini-2.5-flash` on kernel v0.3.0 the run scored 4/6 and 5/6: the model blocks some items the labels mark `flag` (harassment, shared personal details). Treat the labelled set as a starting point for calibrating your bands. A smoke check is the last line: `python content_moderation.py | grep accuracy`.

## Adapting to your data

- **Rewrite the policy.** The category `enum` and the allow/flag/block definitions in `MODERATION_SCHEMA` and the system prompt *are* your policy. Encode your actual community standards there.
- **Calibrate the bands.** Decide where `risk_score` triggers auto-block, human-review, and auto-allow. Start conservative (send more to human review) and tighten as you build confidence against a labelled set.
- **Tune the firewall separately.** `LIBRA_OS_FIREWALL_THRESHOLD` (default `0.4`) governs the platform inbound guardrail, independent of this agent's policy. Lower it to catch more borderline injection attempts; raise it to reduce false positives on benign-but-unusual input.
- **Multi-modal / context.** For content that needs surrounding context (a reply in a thread, an image caption), pass the context in the user message; extend the schema with a `context_dependent` boolean so your queue can prioritise the ambiguous cases.

## Prose companion

The LibraOS docs guide covers policy design, the firewall relationship, and success criteria: **https://docs.meganova.ai → LibraOS → Use Cases → Content Moderation**.
