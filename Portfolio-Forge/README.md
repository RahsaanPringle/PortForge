# Portfolio Forge

A local portfolio backlog for a human owner and a growing AI development team.
Create PBIs, select a project, classify work areas, refine requirements, discuss replies,
and track implementation and verification. This starter uses Python and JSON and has no external frontend dependencies.

## Folder layout and startup

Put the repo and target projects under the same parent folder, for example:

- Portfolio/
  - portfolio-forge/ (this repo)
  - Project-Alpha/
  - Project-Bravo/
  - Project-Charlie/

Python 3.10+ is required. No packages need installing.
Open this repo in VS Code and run:

```powershell
py server.py
```

On macOS/Linux use `python3 server.py`. Open http://localhost:8000.
Stop the earlier Agent Commons server first if it occupies port 8000, or use `py server.py --port 8080`.
Use this Python server rather than Live Server or opening the HTML file directly.

The server automatically registers itself and creates `data/portfolio.json` on first startup.
Register other projects using their existing direct sibling folder names. Registration does not create folders.
The server rejects path traversal and symlinks escaping the parent. Registered projects may have separate git repositories.

## Workflow

1. Register a project.
2. Create a PBI with a title, description, and type.
3. Ask Portfolio Admin in VS Code to refine that selected PBI.
4. Review proposed work areas, questions, dependencies, file changes, and acceptance criteria.
5. Mark Ready once acceptance criteria, assignment, and verification plan are present.
6. Manually assign implementation to a worker, then review results before marking Done.

The board is grouped by status. Each PBI has discussion comments, replies, and activity history.
Work areas are labels, not separate PBI types; a PBI may involve several areas.
Dependencies use PBI IDs and cannot form cycles. Unfinished dependencies prevent beginning work.
Readiness checks are basic completeness checks, not proof that the requirements are good.

## Manual Portfolio Admin agent

The definition is in `.github/agents/portfolio-admin.agent.md`.
Select **Portfolio Admin** in the VS Code agent picker. Start the server first and send:

> Refine PBI-1 in Portfolio Forge at http://localhost:8000. Read the current PBI and discussion through the API, inspect its registered project, classify its work areas, propose acceptance criteria and a verification plan, and post questions or your refinement summary. Do not implement the feature. Stop at Needs information or Ready as appropriate.

Make sure the agent has access to the registered project's folder. Add target folders to a VS Code multi-root workspace when necessary. Folder registration itself does not grant filesystem permissions.

For implementation, explicitly select a PBI, the target project, the worker role, and the allowed changes.
Worker changes should use an isolated branch/worktree. Do not let several workers edit the same checkout concurrently.
Only Portfolio Admin is configured in this starter; the other agent names are assignment labels for future definitions.

## API contract

All mutations require `Content-Type: application/json` and the latest `If-Match` ETag from GET `/api/state`.
Every successful mutation returns the entire updated state plus a new ETag. On HTTP 412, re-read and reassess before retrying.
Do not overwrite `portfolio.json` directly while the server runs.

| Method | Path | Body / purpose |
| --- | --- | --- |
| GET | `/api/meta` | Types, statuses, work areas, roles, and portfolio parent |
| GET | `/api/state` | All registered projects and PBIs; returns ETag |
| POST | `/api/projects` | `name`, `folder` |
| POST | `/api/pbis` | `projectId`, `title`, `description`, `type`; optional text planning fields |
| PATCH | `/api/pbis/{id}` | `actor` plus fields to update |
| POST | `/api/pbis/{id}/comments` | `actor`, `body`, optional `parentMessageId` |

PATCH supports title, description, projectId, type, status, assignedAgent, areas, dependencies,
acceptanceCriteria, implementationPlan, verificationPlan, and result.
Allowed actors are Owner or one of the named agent roles in `/api/meta` (excluding Unassigned).
Replies must reference a comment on the same PBI.

Statuses: Submitted, Triage, Refinement, Needs information, Ready, In progress, Blocked, Review, Done.
Ready and later work statuses require an assigned agent, acceptance criteria, and a verification plan.
Done additionally requires result text containing the worker's verification evidence.
The server records changes but does not enforce every lifecycle transition or verify reported evidence.

## Data and limitations

Back up `data/portfolio.json` while the server is stopped. Runtime data is ignored by git by default.
This has a new schema; old `blog-data.json` is not automatically imported or modified.
Existing Agent Commons files are not needed to run this starter.

The server binds to 127.0.0.1, checks Host and Origin, validates requests, serializes mutations,
and saves atomically. Run only one server against a data file. It has no login or role authentication:
actor labels indicate claimed authorship, not verified identity. It is a single-owner local prototype.
It does not read/write project source files, launch Copilot, poll requests, schedule work, or run background agents.
Those operations are performed only by manually invoked agents with their own tool permissions.

## Verification

```powershell
py -m unittest -v test_server.py
```

Integration tests cover persistence, concurrency, validation, readiness, replies, dependency cycles,
and project folder restrictions. Frontend syntax is also checked during creation; interactive browser behavior
and an actual Copilot invocation still need to be verified on the owner's machine.
