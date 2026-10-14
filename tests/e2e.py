#!/usr/bin/env python3
"""Run the task in a real Tekton cluster against a stand-in Asyntai API.

Needs kubectl on PATH, pointed at a cluster with Tekton Pipelines installed
(for example kind + the Tekton release.yaml). Everything happens in the
namespace asyntai-e2e, which the runner deletes and creates again.

    python3 tests/e2e.py

Every scenario is one PipelineRun: a seed task writes the docs into a fresh
volume (as root, like git-clone does), then the real task file runs on it.
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TASK = os.path.join(ROOT, "task", "ai-chatbot-docs-sync", "1.0",
                    "ai-chatbot-docs-sync.yaml")
NS = "asyntai-e2e"
API_KEY = "test-key-2f8a1c"
BASE_URL = "http://fake-asyntai.%s.svc.cluster.local:8080" % NS

PASSED, FAILED = [], []


def check(name, condition, detail=""):
    if condition:
        PASSED.append(name)
        print("  PASS  %s" % name)
    else:
        FAILED.append(name)
        print("  FAIL  %s" % name)
        if detail:
            print("        %s" % str(detail)[-600:])


def kubectl(*args, stdin=None, check_rc=True):
    proc = subprocess.run(["kubectl", "-n", NS] + list(args), input=stdin,
                          capture_output=True, text=True)
    if check_rc and proc.returncode != 0:
        raise SystemExit("kubectl %s failed: %s" % (" ".join(args), proc.stderr))
    return proc.stdout


def apply(manifest):
    return kubectl("apply", "-f", "-", stdin=json.dumps(manifest))


def api(path, method="GET"):
    code = ("import urllib.request,sys;"
            "r=urllib.request.Request('http://127.0.0.1:8080%s',method='%s',"
            "data=b'' if '%s'=='POST' else None);"
            "sys.stdout.write(urllib.request.urlopen(r).read().decode())"
            % (path, method, method))
    return json.loads(kubectl("exec", "deploy/fake-asyntai", "--",
                              "python3", "-c", code))


def setup():
    subprocess.run(["kubectl", "delete", "namespace", NS, "--wait=true",
                    "--ignore-not-found"], capture_output=True)
    subprocess.run(["kubectl", "create", "namespace", NS], check=True,
                   capture_output=True)
    with open(os.path.join(HERE, "fake_api.py"), encoding="utf-8") as handle:
        fake = handle.read()
    apply({"apiVersion": "v1", "kind": "ConfigMap",
           "metadata": {"name": "fake-api"}, "data": {"fake_api.py": fake}})
    apply({"apiVersion": "apps/v1", "kind": "Deployment",
           "metadata": {"name": "fake-asyntai"},
           "spec": {"selector": {"matchLabels": {"app": "fake-asyntai"}},
                    "template": {
                        "metadata": {"labels": {"app": "fake-asyntai"}},
                        "spec": {"containers": [{
                            "name": "api", "image": "python:3.13-alpine",
                            "command": ["python3", "-u", "/app/fake_api.py"],
                            "ports": [{"containerPort": 8080}],
                            "readinessProbe": {"tcpSocket": {"port": 8080}},
                            "volumeMounts": [{"name": "app",
                                              "mountPath": "/app"}]}],
                            "volumes": [{"name": "app", "configMap": {
                                "name": "fake-api"}}]}}}})
    apply({"apiVersion": "v1", "kind": "Service",
           "metadata": {"name": "fake-asyntai"},
           "spec": {"selector": {"app": "fake-asyntai"},
                    "ports": [{"port": 8080, "targetPort": 8080}]}})
    kubectl("create", "secret", "generic", "asyntai-api-key",
            "--from-literal=api-key=" + API_KEY)
    kubectl("create", "secret", "generic", "wrong-key",
            "--from-literal=api-key=not-the-key")
    kubectl("apply", "-f", TASK)
    kubectl("rollout", "status", "deploy/fake-asyntai", "--timeout=180s")


BASE_FILES = {
    "README.md": "# Project\n\nThe readme of the repository itself.",
    "docs/index.md": "# Welcome\n\nAsyntai answers questions on your website.",
    "docs/pricing.md": "# Pricing\n\nThe Starter plan covers one website.",
    "docs/guides/setup.md": "# Setup\n\nPaste the script tag before the body ends.",
    "docs/drafts/wip.md": "# Draft\n\nThis page is not ready for readers yet.",
    "docs/tiny.md": "short",
    "docs/logo.png": "not text at all, and not a pattern match either",
    "docs/notes.txt": "Plain text notes that are long enough to send.",
    "docs/.hidden/secret.md": "# Hidden\n\nA hidden folder must never be read.",
}


def seed_script(files):
    lines = ["set -e", "cd $(workspaces.out.path)", "rm -rf ./* ./.[!.]* || true"]
    for name, text in files.items():
        folder = os.path.dirname(name)
        if folder:
            lines.append("mkdir -p '%s'" % folder)
        lines.append("cat > '%s' <<'DOC_EOF'\n%s\nDOC_EOF" % (name, text))
    return "\n".join(lines) + "\n"


RUN = [0]


def sync_taskruns(name):
    # One -l with both labels: a second -l flag replaces the first.
    return json.loads(kubectl(
        "get", "taskrun", "-l",
        "tekton.dev/pipelineRun=%s,tekton.dev/pipelineTask=sync" % name,
        "-o", "json"))["items"]


def run(files, params, secret="asyntai-api-key", timeout=240):
    """Start one PipelineRun and wait for it. Returns (succeeded, reason, log)."""
    RUN[0] += 1
    name = "sync-%d" % RUN[0]
    params = dict({"base-url": BASE_URL, "docs-path": "docs"}, **params)
    params["api-key-secret"] = secret
    apply({
        "apiVersion": "tekton.dev/v1", "kind": "PipelineRun",
        "metadata": {"name": name},
        "spec": {
            "timeouts": {"pipeline": "%ds" % timeout},
            "workspaces": [{"name": "shared", "volumeClaimTemplate": {"spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": "64Mi"}}}}}],
            "pipelineSpec": {
                "workspaces": [{"name": "shared"}],
                "tasks": [
                    {"name": "seed",
                     "workspaces": [{"name": "out", "workspace": "shared"}],
                     "taskSpec": {
                         "workspaces": [{"name": "out"}],
                         "steps": [{"name": "write",
                                    "image": "python:3.13-alpine",
                                    "script": "#!/bin/sh\n" + seed_script(files)}]}},
                    {"name": "sync", "runAfter": ["seed"],
                     "taskRef": {"name": "ai-chatbot-docs-sync"},
                     "workspaces": [{"name": "source", "workspace": "shared"}],
                     "params": [{"name": k, "value": v}
                                for k, v in params.items()]},
                ]}}})
    deadline = time.time() + timeout + 30
    status = {}
    while time.time() < deadline:
        status = json.loads(kubectl("get", "pipelinerun", name, "-o", "json"))
        conds = status.get("status", {}).get("conditions", [])
        if conds and conds[0].get("status") in ("True", "False"):
            break
        # A step that cannot start (missing Secret) sits in
        # CreateContainerConfigError until the timeout; stop early.
        trs = sync_taskruns(name)
        if trs:
            pod = trs[0].get("status", {}).get("podName")
            if pod:
                raw = kubectl("get", "pod", pod, "-o", "json", check_rc=False)
                if raw:
                    for cs in json.loads(raw).get("status", {}).get(
                            "containerStatuses", []):
                        waiting = cs.get("state", {}).get("waiting", {})
                        if waiting.get("reason") == "CreateContainerConfigError":
                            return False, "CreateContainerConfigError", \
                                waiting.get("message", "")
        time.sleep(2)
    conds = status.get("status", {}).get("conditions", [{}])
    ok = conds[0].get("status") == "True"
    reason = conds[0].get("reason", "")
    trs = sync_taskruns(name)
    log = ""
    if trs:
        tr_cond = trs[0].get("status", {}).get("conditions", [{}])[0]
        if tr_cond.get("reason") == "CreateContainerConfigError":
            return False, tr_cond["reason"], tr_cond.get("message", "") +                 json.dumps(trs[0].get("status", {}).get("steps", []))
    if trs and trs[0].get("status", {}).get("podName"):
        log = kubectl("logs", trs[0]["status"]["podName"], "-c", "step-sync",
                      check_rc=False)
    return ok, reason, log


def titles(state):
    return sorted(e["title"] for e in state["entries"])


def main():
    print("Setting up namespace %s" % NS)
    setup()

    print("\nFirst run")
    api("/__reset", "POST")
    # The first run pulls the images into the node, so it may take longer.
    ok, reason, log = run(BASE_FILES, {}, timeout=600)
    state = api("/__state")
    expected = ["drafts/wip.md", "guides/setup.md", "index.md", "notes.txt",
                "pricing.md"]
    check("the PipelineRun succeeds", ok, reason + log)
    check("every matching file became an entry", titles(state) == expected,
          titles(state))
    check("the file under ten characters was skipped", "skip" in log, log)
    check("the hidden folder was not read",
          not any("secret" in t for t in titles(state)))
    check("the readme outside docs-path was not sent",
          not any("README" in t for t in titles(state)))
    by_title = {e["title"]: e for e in state["entries"]}
    check("the text of a file arrived whole",
          by_title.get("pricing.md", {}).get("content")
          == BASE_FILES["docs/pricing.md"], by_title.get("pricing.md"))
    check("the summary counts them as added", "5 added" in log, log)
    check("the step ran as a non-root user and could still read the files",
          ok and len(state["entries"]) == 5)
    first_ids = sorted(e["id"] for e in state["entries"])

    print("\nSecond run, nothing changed")
    api("/__state")
    calls_before = len(state["calls"])
    ok, reason, log = run(BASE_FILES, {})
    state = api("/__state")
    new_calls = state["calls"][calls_before:]
    check("the PipelineRun succeeds", ok, reason + log)
    check("every entry was left exactly as it was",
          sorted(e["id"] for e in state["entries"]) == first_ids)
    check("no text was sent again",
          not any(c["method"] in ("POST", "DELETE") for c in new_calls),
          new_calls)
    check("the summary counts them as unchanged", "5 unchanged" in log, log)

    print("\nThird run, one file changed")
    changed = dict(BASE_FILES)
    changed["docs/pricing.md"] = "# Pricing\n\nThe Pro plan covers ten websites."
    ok, reason, log = run(changed, {})
    state = api("/__state")
    by_title = {e["title"]: e for e in state["entries"]}
    check("the PipelineRun succeeds", ok, reason + log)
    check("the entry now holds the new text",
          by_title["pricing.md"]["content"] == changed["docs/pricing.md"])
    check("the entry count did not grow", len(state["entries"]) == 5)
    check("the summary says 1 updated", "1 updated" in log, log)

    print("\nPrefix, exclude and prune")
    api("/__reset", "POST")
    ok, reason, log = run(BASE_FILES, {"title-prefix": "Docs / ",
                                       "exclude": "drafts/*"})
    state = api("/__state")
    check("the PipelineRun succeeds", ok, reason + log)
    check("the prefix is on every title",
          all(t.startswith("Docs / ") for t in titles(state)), titles(state))
    check("the excluded folder was not sent",
          not any("drafts" in t for t in titles(state)), titles(state))
    ok, reason, log = run({k: v for k, v in BASE_FILES.items()
                           if k != "docs/guides/setup.md"} | {
                               "docs/manual.md": "# Manual\n\nAdded by hand to the docs."},
                          {"exclude": "drafts/*,manual.md"})
    check("a run without a prefix succeeds", ok, reason + log)
    ok, reason, log = run({k: v for k, v in BASE_FILES.items()
                           if k != "docs/guides/setup.md"},
                          {"title-prefix": "Docs / ", "exclude": "drafts/*",
                           "prune": "true"})
    state = api("/__state")
    check("the prune run succeeds", ok, reason + log)
    check("the entry of the deleted file is gone",
          "Docs / guides/setup.md" not in titles(state), titles(state))
    check("entries without the prefix were not touched",
          "guides/setup.md" not in titles(state) and "index.md" in titles(state),
          titles(state))
    check("the summary counts the deletion", "1 deleted" in log, log)

    print("\nDry run")
    api("/__reset", "POST")
    ok, reason, log = run(BASE_FILES, {"dry-run": "true"})
    state = api("/__state")
    check("the PipelineRun succeeds", ok, reason + log)
    check("the log says nothing was sent", "Nothing was sent" in log, log)
    check("the API was not called", state["calls"] == [], state["calls"])

    print("\nErrors")
    ok, reason, log = run(BASE_FILES, {}, secret="wrong-key")
    check("a wrong key fails the PipelineRun", not ok, reason)
    check("the log repeats what the API said", "Invalid API key" in log, log)
    check("the key is never printed", API_KEY not in log and "not-the-key" not in log)
    ok, reason, log = run(BASE_FILES, {}, secret="no-such-secret")
    check("a missing Secret stops the task", not ok, reason)
    check("Kubernetes names the missing Secret", "no-such-secret" in log, log)
    ok, reason, log = run(BASE_FILES, {"docs-path": "documentation"})
    check("a missing folder fails the PipelineRun", not ok, reason)
    check("the message names the missing folder", "documentation" in log, log)

    print("\n%d passed, %d failed" % (len(PASSED), len(FAILED)))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
