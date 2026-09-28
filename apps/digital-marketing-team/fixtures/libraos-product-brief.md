# LibraOS Product Brief

Source owner: LibraOS product team  
Audience: developer marketing and developer relations  
Status: approved demo context

## Product thesis

LibraOS is an operating system and runtime for digital employees. A leader can
give one high-level mission to a digital employee, which can assemble the
specialists required for that mission, create a dependency-aware task graph,
run independent work in parallel, pass structured outputs between employees,
request human approval at authority boundaries, and return one finished
deliverable.

The core interaction is:

`Mission → Team → Task graph → Execution → Deliverable`

LibraOS is designed for organizational work rather than one prompt followed by
one chatbot response. The product message is: **Build a digital team, not
another chatbot.**

## Developer proof points

- One runtime coordinates multiple named digital employees.
- Tasks are explicit runtime objects with one accountable owner, inputs,
  dependencies, expected outputs, permitted tools, approval rules, and
  completion criteria.
- Independent tasks can execute concurrently under a configured concurrency
  limit.
- Downstream employees consume structured output objects rather than raw chat
  transcripts.
- Knowledge and memory are native LibraOS modules. External MCP tools can be
  added when a mission needs them, but the runtime does not require GBrain or a
  collection of sponsor products.
- Public actions, outbound communication, irreversible changes, and spend can
  be held behind human approval.
- Mission events provide a durable, inspectable audit trail for employee,
  task, handoff, approval, and report state changes.
- Final reports preserve section-level employee attribution and source
  references from the runtime records.
- LibraOS supports self-hosted and private deployment patterns for teams that
  need control over models, knowledge, and policy.

## Primary developer audience

The primary audience is AI application developers and engineering teams that
currently assemble agent systems from separate components for orchestration,
context, memory, tools, permissions, review, and deployment.

Their common pain points include fragmented APIs, inconsistent context and
memory abstractions, separate permission models, weak auditability, and the
effort required to turn an agent prototype into supervised organizational
work.

## Recommended positioning

Primary message: **One mission. One runtime. Many digital employees.**

Developer message: **Build the employee, not the infrastructure around it.**

The strongest demonstration is a leader entering one objective once and then
watching LibraOS choose the team, break down the work, execute dependencies,
ask for one meaningful approval, and return an accountable deliverable.

## Activation and measurement

The primary developer activation event is the first successful digital
employee run that produces a source-backed task result. Account signup alone
is not the success event.

For a launch campaign, distinguish total signups from qualified signups. A
qualified signup should show developer intent through a meaningful product
action such as creating or running a digital employee.

## Messaging guardrails

- Do not claim that LibraOS publishes or takes external action without the
  configured approval and permission boundary.
- Do not invent performance, pricing, customer, security-certification, or
  conversion claims.
- Describe external systems as optional MCP or adapter integrations when they
  materially help a mission.
- Keep the public cookbook thin. The commercial runtime, policy engine,
  enterprise permissions, audit infrastructure, and control plane remain
  LibraOS platform capabilities.

## Source reference

Use this URI when citing this brief:

`cookbook://digital-marketing-team/libraos-product-brief`
