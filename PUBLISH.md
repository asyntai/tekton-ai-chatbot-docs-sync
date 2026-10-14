# Publish to Artifact Hub

1. Create the public GitHub repo and push this folder to branch `main`:

   ```bash
   gh repo create asyntai/tekton-ai-chatbot-docs-sync --public \
     --description "Tekton Task: keep your Asyntai AI chatbot up to date with your docs" \
     --homepage https://asyntai.com/documentation/integrations/tekton/
   gh api -X PUT repos/asyntai/tekton-ai-chatbot-docs-sync/topics \
     -f "names[]=tekton" -f "names[]=tekton-task" -f "names[]=tekton-catalog" \
     -f "names[]=ai-chatbot" -f "names[]=documentation" -f "names[]=knowledge-base" \
     -f "names[]=ci-cd" -f "names[]=kubernetes" -f "names[]=artifacthub" -f "names[]=asyntai"
   ```

   Commit as `Asyntai <hello@asyntai.com>`.

2. Sign in at https://artifacthub.io (GitHub login), open Control Panel,
   Repositories, Add:
   - Kind: Tekton tasks
   - Name: `asyntai` (the samples and the docs use `catalog: asyntai`)
   - Display name: Asyntai
   - URL: `https://github.com/asyntai/tekton-ai-chatbot-docs-sync/task`
   - Branch: `main`
   - Versioning: directory

   No review. The tracker picks the repo up in about 30 minutes.

3. Copy the repository ID from the control panel into `artifacthub-repo.yml`
   (`repositoryID:`), push. Artifact Hub then shows Verified Publisher.

## New version

Add a new folder `task/ai-chatbot-docs-sync/<x.y>/` with the label
`app.kubernetes.io/version: "<x.y>"`. Keep the old folders. A new image needs a
new digest in the `image` param default.

## Checks before a push

```bash
ah lint --kind tekton-task --path task
python3 tests/e2e.py      # needs kubectl + a cluster with Tekton Pipelines
```
