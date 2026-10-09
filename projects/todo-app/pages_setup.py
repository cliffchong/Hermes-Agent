#!/usr/bin/env python3
"""Helpers for finishing the GitHub Pages setup for cliffchong/Hermes-Agent.

Stages:
  enable   – wait for the PAT to gain Pages:write, then create the Pages site (build_type=workflow)
  deploy   – trigger the deploy workflow (workflow_dispatch, else an empty commit) and wait for the run
  status   – print Pages site + latest run state
Never prints the token.
"""
import json, subprocess, sys, time, urllib.error, urllib.request

REPO = "cliffchong/Hermes-Agent"
API = "https://api.github.com"
TOK = open("/home/codespace/.hermes/secrets/github_pat").read().strip()
REPO_DIR = "/workspaces/Hermes-Agent"


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method)
    r.add_header("Authorization", "Bearer " + TOK)
    r.add_header("Accept", "application/vnd.github+json")
    r.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode(errors="replace")


def pages_site():
    code, body = req("GET", f"/repos/{REPO}/pages")
    return body if code == 200 else None


def create_pages():
    return req("POST", f"/repos/{REPO}/pages", {"build_type": "workflow"})


def latest_run():
    code, body = req("GET", f"/repos/{REPO}/actions/runs?per_page=1")
    if code != 200 or not body.get("workflow_runs"):
        return None
    r = body["workflow_runs"][0]
    return {"id": r["id"], "status": r["status"], "conclusion": r["conclusion"],
            "sha": r["head_sha"][:7], "url": r["html_url"], "event": r["event"]}


def stage_enable(timeout_s=240, every=15):
    """Poll until the token can create the Pages site, then create it."""
    deadline = time.time() + timeout_s
    attempt = 0
    while True:
        attempt += 1
        site = pages_site()
        if site:
            print(f"[{attempt}] Pages already exists: {site.get('html_url')} (build_type={site.get('build_type')})")
            return True
        code, body = create_pages()
        msg = body.get("message") if isinstance(body, dict) else str(body)[:80]
        print(f"[{attempt}] POST /pages -> {code} {msg}")
        if code in (200, 201, 409):
            print("    Pages site is enabled.")
            return True
        if time.time() >= deadline:
            print("    still no Pages:write on the token — giving up for now.")
            return False
        time.sleep(every)


def stage_deploy(wait_s=420, every=15):
    code, body = req("POST", f"/repos/{REPO}/actions/workflows/deploy-pages.yml/dispatches", {"ref": "main"})
    if code in (204, 201):
        print("workflow_dispatch accepted.")
    else:
        print(f"workflow_dispatch -> {code} {(body or {}).get('message') if isinstance(body, dict) else body}")
        print("falling back to an empty commit on main to trigger the workflow.")
        subprocess.run(["git", "-C", REPO_DIR, "commit", "--allow-empty", "-q",
                        "-m", "ci: trigger Pages deploy"], check=True)
        push = subprocess.run(["git", "-C", REPO_DIR, "push", "origin", "main"],
                              capture_output=True, text=True)
        print(push.stdout.strip() or push.stderr.strip())
    sha = subprocess.run(["git", "-C", REPO_DIR, "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    deadline = time.time() + wait_s
    seen = None
    while time.time() < deadline:
        run = latest_run()
        if run:
            if seen != (run["id"], run["status"], run["conclusion"]):
                seen = (run["id"], run["status"], run["conclusion"])
                print(f"run {run['id']} [{run['event']}] {run['status']}/{run['conclusion']} sha={run['sha']} {run['url']}")
            if run["status"] == "completed" and run["sha"] == sha:
                return run
        time.sleep(every)
    print("timed out waiting for the run to finish.")
    return latest_run()


def stage_status():
    site = pages_site()
    print("pages:", json.dumps({k: site.get(k) for k in ("html_url", "status", "build_type", "cname")}) if site else "NOT ENABLED")
    print("latest run:", latest_run())


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "status"
    if stage == "enable":
        ok = stage_enable()
        sys.exit(0 if ok else 3)
    elif stage == "deploy":
        run = stage_deploy()
        sys.exit(0 if run and run.get("conclusion") == "success" else 1)
    else:
        stage_status()
