# Concepts: skills, agents, packs, missions and apps

The cookbook is organized by what you are building. Each layer builds on the one below it.

```
apps        how a person or a partner product runs a team       apps/
  │
missions    what a team must deliver, and under which rules      packs/<pack>/missions/
  │
packs       who is on the team                                   packs/<pack>/pack.yaml
  │
agents      who does the work, with which role and rules         agent files, employees
  │
skills      what an agent can do                                 search_web, fetch_url, read_pdf …
```

| Layer | Answers | Example |
| --- | --- | --- |
| **Skill** | What can an agent *do*? | `search_web`, `fetch_url`, `knowledge_search` |
| **Agent / employee** | Who does the work, with what role and rules? | a market researcher with `search_web` and `fetch_url` |
| **Pack** | Who is on the team? | a director plus specialists, their knowledge and safety rules |
| **Mission** | What must the team deliver, under which rules? | workstreams, task limits, allowed tools, evidence rules, approval gates, report sections |
| **App** | How does someone run it? | a mission console, or your own product calling the kernel |

## Where things live

| Folder | Contains |
| --- | --- |
| [`get-started/`](../get-started/) | A local kernel and your first agent |
| [`recipes/`](../recipes/) | One agent solving one task, each paired with a docs guide |
| [`packs/`](../packs/) | Reusable teams and their missions |
| [`apps/`](../apps/) | Complete applications that run agents or teams |

## Missions

A mission is a repeatable job for a pack's team. The director turns a mission request into a plan (tasks, owners, dependencies, approval gates), the specialists work in dependency order with their outputs and sources recorded, and the director synthesizes one attributed deliverable. People stay in control at the gates the mission declares, and nothing reaches the outside world without approval.

Today the kernel's mission engine runs the marketing team only, with its prompts compiled in. Loading mission templates from packs is proposed in [libraos/libraos#1660](https://github.com/libraos/libraos/issues/1660).
