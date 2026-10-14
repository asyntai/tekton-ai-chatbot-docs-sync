# Asyntai AI Chatbot Docs Sync

Keep the [Asyntai](https://asyntai.com) AI chatbot on your website up to date
with your documentation. Add this task after `git-clone` and every pipeline run
sends your Markdown and text files to the Asyntai knowledge base. The chatbot
then answers visitor questions from the latest version of your docs.

- One knowledge base entry per file, titled by its path.
- A changed file replaces its old entry, so nothing is duplicated.
- An unchanged file is skipped, so a run with no doc changes sends nothing.
- With `prune`, entries of deleted files are removed too.

Full guide: https://asyntai.com/documentation/integrations/tekton/

## Install

From Artifact Hub with the hub resolver (no install needed), or apply it once:

```bash
kubectl apply -f https://raw.githubusercontent.com/asyntai/tekton-ai-chatbot-docs-sync/main/task/ai-chatbot-docs-sync/1.0/ai-chatbot-docs-sync.yaml
```

## Set up the API key

Copy your API key from the Asyntai dashboard (Settings, API) and store it in a
Secret in the namespace where your pipelines run:

```bash
kubectl create secret generic asyntai-api-key --from-literal=api-key=YOUR_API_KEY
```

## Workspaces

| Name | Description |
| --- | --- |
| `source` | The checked out repository that holds the documentation. Read only. |

## Parameters

| Name | Default | Description |
| --- | --- | --- |
| `docs-path` | (required) | Folder or file to send, relative to the workspace root, for example `docs`. |
| `file-patterns` | `*.md,*.mdx,*.txt` | Comma-separated file name patterns to send. |
| `exclude` | `""` | Comma-separated patterns to skip, for example `drafts/*,CHANGELOG.md`. |
| `title-prefix` | `""` | Text put before every entry title, for example `Docs / `. |
| `website-id` | `""` | The Asyntai website to send to. Empty means the first website on the account. |
| `prune` | `"false"` | `"true"` removes entries whose file is gone. Needs `title-prefix`, and only touches entries with that prefix. |
| `dry-run` | `"false"` | `"true"` lists the files and sends nothing. |
| `api-key-secret` | `asyntai-api-key` | Name of the Secret that holds the API key. |
| `api-key-secret-key` | `api-key` | Key inside that Secret. |
| `base-url` | `https://asyntai.com` | The Asyntai server. Change it only for testing. |
| `image` | `docker.io/asyntai/ai-docs-sync:1.0.0@sha256:...` | The image that runs the sync. |

## Usage

Run the task after `git-clone` in the same workspace:

```yaml
- name: sync-docs
  runAfter: ["fetch"]
  taskRef:
    resolver: hub
    params:
      - name: kind
        value: task
      - name: name
        value: ai-chatbot-docs-sync
      - name: version
        value: "1.0"
      - name: catalog
        value: asyntai
  workspaces:
    - name: source
      workspace: shared
  params:
    - name: docs-path
      value: docs
    - name: title-prefix
      value: "Docs / "
    - name: prune
      value: "true"
```

A complete Pipeline and PipelineRun is in [samples/pipeline.yaml](samples/pipeline.yaml).

The step log ends with one summary line, for example:

```
Done. 2 added, 1 updated, 14 unchanged, 0 deleted, 0 skipped.
```

## Support

Questions and help: hello@asyntai.com or https://asyntai.com/documentation/integrations/tekton/
