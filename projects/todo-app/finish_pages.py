#!/usr/bin/env python3
"""Switch cliffchong/Hermes-Agent Pages to workflow mode and run the deploy pipeline.

1. waits (bounded) for the PAT to gain Pages:write, then PUT build_type=workflow
2. triggers .github/workflows/deploy-pages.yml and waits for the run
3. verifies the live URL carries the workflow's deploy stamp
4. on any failure, restores legacy (branch) mode so the site never goes dark
"""
import json, os, re, subprocess, sys, time, urllib.error, urllib.request

REPO = "cliffchong/Hermes-Agent"
API = "https://api.github.com"
SITE = "https://cliffchong.github.io/Hermes-Agent/"
REPO_DIR = "/workspaces/Hermes-Agent"
TOK = open("/home/codespace/.hermes/secrets/github_pat").read().strip()


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


def get_site():
    code, body = req("GET", f"/repos/{REPO}/pages")
    return body if code == 200 else None


def restore_legacy():
    code, body = req("PUT", f"/repos/{REPO}/pages", {"build_type": "legacy", "source": {"branch": "main", "path": "/"}})
    print(f"restore legacy -> {code} {body if code not in (200, 204) else 'ok'}")


def wait_for_pages_write(timeout_s=None, every=15):
    if timeout_s is None:
        timeout_s = int(os.environ.get("PAGE_WRITE_WAIT_S", "240"))
    deadline = time.time() + timeout_s
    n = 0
    while True:
        n += 1
        code, body = req("PUT", f"/repos/{REPO}/pages", {"build_type": "workflow"})
        msg = body.get("message") if isinstance(body, dict) else str(body)[:80]
        print(f"[{n}] PUT build_type=workflow -> {code} {msg}", flush=True)
        if code in (200, 204):
            return True
        if time.time() >= deadline:
            return False
        time.sleep(every)


def latest_run():
    code, body = req("GET", f"/repos/{REPO}/actions/runs?per_page=1")
    if code != 200 or not body.get("workflow_runs"):
        return None
    r = body["workflow_runs"][0]
    return {"id": r["id"], "status": r["status"], "conclusion": r["conclusion"],
            "sha": r["head_sha"][:7], "url": r["html_url"], "event": r["event"]}


def trigger_and_wait(wait_s=420, every=15):
    sha = subprocess.run(["git", "-C", REPO_DIR, "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    code, body = req("POST", f"/repos/{REPO}/actions/workflows/deploy-pages.yml/dispatches", {"ref": "main"})
    print(f"workflow_dispatch -> {code}", flush=True)
    if code not in (204, 201):
        print("falling back to an empty commit to trigger the run.", flush=True)
        subprocess.run(["git", "-C", REPO_DIR, "commit", "--allow-empty", "-q", "-m", "ci: trigger Pages deploy"], check=True)
        p = subprocess.run(["git", "-C", REPO_DIR, "push", "origin", "main"], capture_output=True, text=True)
        print(p.stdout.strip() or p.stderr.strip(), flush=True)
        sha = subprocess.run(["git", "-C", REPO_DIR, "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
    print("waiting for a run on", sha, flush=True)
    deadline = time.time() + wait_s
    seen = None
    while time.time() < deadline:
        run = latest_run()
        if run and (run["id"], run["status"], run["conclusion"]) != seen:
            seen = (run["id"], run["status"], run["conclusion"])
            print(f"  run {run['id']} [{run['event']}] {run['status']}/{run['conclusion']} sha={run['sha']} {run['url']}", flush=True)
        if run and run["status"] == "completed" and run["sha"] == sha:
            return run
        time.sleep(every)
    return latest_run()


def check_live(attempts=10, every=15):
    import urllib.request as u
    for i in range(attempts):
        try:
            with u.urlopen(SITE + "?cb=" + str(i), timeout=20) as r:
                html = r.read().decode("utf-8", "replace")
            stamp = re.search(r"<!--\s*deploy (\w+)[^>]*-->", html)
            print(f"  live check {i+1}: HTTP {r.status}, {len(html)} bytes, stamp={stamp.group(1)[:7] if stamp else 'none'}", flush=True)
            if r.status == 200 and stamp:
                return stamp.group(1)[:7]
        except Exception as e:
            print(f"  live check {i+1}: {e}", flush=True)
        time.sleep(every)
    return None


if __name__ == "__main__":
    if not wait_for_pages_write():
        print("STOP: the PAT still has no Pages:write permission; nothing changed.", flush=True)
        print(json.dumps({k: get_site().get(k) for k in ("html_url", "status", "build_type")}, indent=1))
        sys.exit(3)
    site = get_site()
    print("pages mode now:", site.get("build_type"), "| status:", site.get("status"), flush=True)

    run = trigger_and_wait()
    print("run result:", run, flush=True)
    if not run or run.get("conclusion") != "success":
        print("deploy did not succeed — restoring legacy branch mode to keep the site live.", flush=True)
        restore_legacy()
        print("pages after restore:", json.dumps({k: get_site().get(k) for k in ("html_url", "build_type", "status")}), flush=True)
        sys.exit(1)

    stamp = check_live()
    head = subprocess.run(["git", "-C", REPO_DIR, "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    print(f"workflow deployed stamp={stamp} | repo HEAD={head}", flush=True)
    sys.exit(0 if stamp else 2)
