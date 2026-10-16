# Approval mechanisms

There are two distinct mechanisms. An approval button is not evidence that its
caller has permission, or that an external business action has executed.

| | Mission Decision | Tool Action Approval |
|---|---|---|
| Purpose | Resolve a decision within a running mission | Authorize a pending side-effecting tool action |
| Current cookbook entry | Marketing Team / Mission Console | Dedicated tutorial pending contract verification |
| Client surface | `POST /agents/v1/{lead}/jobs/{job}/decisions/{decision}` | Use the selected Runtime version's pending-action API and role/group/self-approval policy |
| Observable success | Decision resolved; dependent mission work resumes | Approved action executes and returns a business receipt |
| Boundary | Unauthorized caller denied; gate remains pending until a valid decision | Rejected action executes zero times; unauthorized caller cannot approve |
| What it does not establish | Permission to execute arbitrary external business mutations | Permission to read/write another customer's business records |

The mission client has offline tests for waiting, replay and permission errors.
Those tests do not verify the live server's access control. Existing personal
assistant documentation describes restrictions on its pinned Runtime; newer
source fields alone are not a verified end-to-end permission contract.

The [P1 verification task](https://github.com/libraos/libraos/issues/1728) will
establish the version/role matrix and separate executable tests before a general
approval tutorial is advertised as runnable. [Pack mission templates](https://github.com/libraos/libraos/issues/1660)
are a separate dependency.
