# Asyntai AI Chatbot Docs Sync for Tekton

A Tekton Task that keeps the [Asyntai](https://asyntai.com) AI chatbot on your
website up to date with your documentation. Run it after `git-clone`, and every
pipeline run sends your Markdown and text files to the Asyntai knowledge base.

- Task: [task/ai-chatbot-docs-sync/1.0](task/ai-chatbot-docs-sync/1.0/README.md)
- Guide: https://asyntai.com/documentation/integrations/tekton/

## Quick start

```bash
kubectl create secret generic asyntai-api-key --from-literal=api-key=YOUR_API_KEY
kubectl apply -f https://raw.githubusercontent.com/asyntai/tekton-ai-chatbot-docs-sync/main/task/ai-chatbot-docs-sync/1.0/ai-chatbot-docs-sync.yaml
```

Then add the task to your pipeline after `git-clone`. A full example is in
[samples/pipeline.yaml](task/ai-chatbot-docs-sync/1.0/samples/pipeline.yaml).

## Tests

`tests/e2e.py` runs the task in a real Tekton cluster (for example kind with
Tekton Pipelines) against a stand-in Asyntai API, and checks adding, skipping
unchanged files, updating, prefix, exclude, prune, dry run and the error cases.

```bash
python3 tests/e2e.py
```

## License

MIT
