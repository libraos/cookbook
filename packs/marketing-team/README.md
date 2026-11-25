# Marketing team pack

The team behind [`apps/digital-marketing-team`](../../apps/digital-marketing-team/): a Head of Marketing who turns one mission into a department, a task graph and approval gates, and synthesizes one attributed report.

| File | What it is |
| --- | --- |
| [`pack.yaml`](pack.yaml) | Team manifest: director, knowledge, missions |
| [`missions/autonomous-marketing-department.yaml`](missions/autonomous-marketing-department.yaml) | The mission contract: planning, scheduling, handoffs, approvals, report |
| [`missions/autonomous-marketing-department.example.yaml`](missions/autonomous-marketing-department.example.yaml) | An example mission input |
| [`knowledge/libraos-product-brief.md`](knowledge/libraos-product-brief.md) | Source the research employees cite; ingested by the app's setup script |

**Status: contract.** The app calls the kernel's built-in `head-of-marketing` mission engine; it does not install this pack as a mission template. The last live verification used kernel v0.3.0 with `LIBRA_OS_WORKFLOWS_ENABLED=true` and PostgreSQL; the app's README covers setup and what to expect from smaller local models.
