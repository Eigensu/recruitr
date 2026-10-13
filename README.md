# Recruitr

Eigensu (Binge Consulting Recruitment Platform), a gamified recruitment CRM: a Next.js frontend
(`apps/frontend`) and a FastAPI/MongoDB backend (`apps/backend`) in one pnpm + Turborepo
workspace.

- Setup, commands and architecture: [`CLAUDE.md`](CLAUDE.md), plus the ones in each app directory.
- CI and running its checks locally: [`docs/CI.md`](docs/CI.md).

## Pull requests

Title every pull request `fix(<JIRA-KEY>): <summary>`, with the key of the Jira ticket the work
belongs to:

```
fix(KER-159): Fit the Add Candidate form three or four fields to a row
```

PRs are squash-merged, so the title becomes the commit subject on `main`. That keeps the ticket
key in the history as well as on the PR.
