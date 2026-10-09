# Hermes-Agent — Todo List Web App

A single-file, dependency-free task manager. No build step, no framework, no CDN: `index.html` is the whole app.

**Live:** https://cliffchong.github.io/Hermes-Agent/

## Features

| Feature | Notes |
|---|---|
| Add tasks | Type and press `Enter`, or click **Add**; input is trimmed, blanks ignored, 300-char cap |
| Mark done / not done | Native checkbox (custom-painted), stores a completion timestamp shown under the task |
| Delete | Per-row delete button, with a 6-second **Undo** toast and `Ctrl`/`Cmd` + `Z` |
| Rename | Double-click the task text, or use the pencil button. `Enter` saves, `Esc` cancels |
| Filters | All / Active / Done with live counts, plus **Clear completed** |
| Local storage | Everything persists in `localStorage` under `helen.todo.v1` (`{v, tasks, filter, theme}`); stored data is validated on read, and write failures degrade gracefully |
| Theme | Auto (follows `prefers-color-scheme`), light, or dark — persisted |

## Interface

- **Surface:** designed as an *operate* surface — the composer is the single visual focus, the list keeps the density; no hero, no filler cards.
- **Tokens:** warm paper neutrals with one teal accent, serif title over a precise sans UI, mono only for keyboard hints.
- **Accessibility:** `aria-pressed` filter state, labelled controls, an `aria-live` region for announcements, `:focus-visible` rings, 44px touch targets, `prefers-reduced-motion` honoured.
- **Contrast:** measured in-browser — body text 15.4:1 (light) / 15.6:1 (dark); every secondary label ≥ 4.5:1.
- **Safety:** the DOM is built with `textContent`, so stored input is never parsed as HTML.

## Keyboard

| Key | Action |
|---|---|
| `/` | Focus the task input |
| `Enter` | Add the task / save a rename |
| `Esc` | Cancel a rename, dismiss the undo toast |
| `Ctrl`/`Cmd` + `Z` | Undo the last delete or clear |

## Running locally

Open `index.html` in a browser — that is the entire setup (`localStorage` works over `file://` too). For a served copy:

```bash
python3 -m http.server 8787
# then open http://127.0.0.1:8787/
```

Add `?demo=1` to load sample tasks without writing to storage.

## Deployment

`.github/workflows/deploy-pages.yml` publishes the site to GitHub Pages on every push to `main`:

1. **build** — checks out the repo, configures Pages, sanity-checks `index.html` (it fails if the storage wiring is missing), stages it into `_site/`, and stamps the artifact with the commit SHA.
2. **deploy** — `actions/deploy-pages` publishes the artifact to the `github-pages` environment.

The live page carries a `<!-- deploy <sha> -->` comment in its `<head>`, so a deployed revision can always be traced back to a commit.

### One-time setup (must be done once, outside the workflow)

A Pages site cannot be created by the workflow itself — `POST /repos/{owner}/{repo}/pages` is a repository-administration call, and the automatic `GITHUB_TOKEN` has no admin rights (`Create Pages site failed: Resource not accessible by integration`). It therefore has to be enabled once, out of band:

- GitHub UI: **Settings → Pages → Source: GitHub Actions**, or
- API: `POST /repos/{owner}/{repo}/pages` with a token holding the **Pages: write** permission.

Once the site exists with `build_type: workflow`, every push to `main` deploys automatically; `enablement: true` is intentionally absent from the workflow for the reason above.

