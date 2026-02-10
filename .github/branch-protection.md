# Branch Protection Rules

Recommended branch protection rules for the `main` branch.

## Recommended Settings

- **Require pull request reviews**: 1 approval minimum
- **Require status checks to pass**: Frontend, Backend, E2E Tests
- **Require branches to be up to date** before merging
- **No force pushes** to `main`
- **No deletions** of `main`

## Apply via GitHub CLI

```bash
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["Frontend","Backend","E2E Tests"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

Replace `{owner}/{repo}` with `HatmanStack/plot-palette`.

## Apply via GitHub UI

1. Go to **Settings** > **Branches** > **Add branch protection rule**
2. Branch name pattern: `main`
3. Check:
   - Require a pull request before merging (1 approval)
   - Require status checks to pass before merging
     - Add: `Frontend`, `Backend`, `E2E Tests`
   - Require branches to be up to date before merging
4. Save changes
