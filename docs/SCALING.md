# Scaling: from one workstation to a larger company

**Read this first.** Spend Leakage Finder was built and tested to run on one workstation, and for a company of 500 to 2,500 people that is usually enough. Docker and Kubernetes are not needed to prove the idea. This page shows the path if your needs grow, and says plainly where it is untested.

## Three stages

| Stage | What it is | When it fits |
|---|---|---|
| 1. One workstation | Python scripts and Ollama installed directly | Trying it, a pilot, one team |
| 2. Docker Compose | The same two containers on one server | Repeatable runs, a shared server, handing it to IT |
| 3. Kubernetes | The same containers scheduled across several machines | Many contracts and invoices at once (hundreds of files, several finance teams), where one workstation becomes the bottleneck. |

## Stage 2: Docker Compose
Covered in the setup guide ("Option B"). `compose.yaml` defines the model container and the project container. The project reads the model's address from an environment variable (`OLLAMA_URL`), so no code change is needed to move the model to another machine.

## Stage 3: Kubernetes
The files in `deploy/k8s/` are a starting point:

- `ollama.yaml`: the model server, a storage claim for the model files, and a service the project can reach inside the cluster.
- `pull-model.yaml`: a one-off job that downloads the model.
- `job.yaml`: runs the project once as a Kubernetes Job.

Build and publish the image, then edit the image name in `job.yaml`:
```powershell
docker build -t <your-registry>/spend-leakage-finder:0.1 .
docker push <your-registry>/spend-leakage-finder:0.1
kubectl apply -f deploy/k8s/ollama.yaml
kubectl apply -f deploy/k8s/pull-model.yaml
kubectl apply -f deploy/k8s/job.yaml
```
To try it on a laptop, use a local cluster such as kind or minikube.

**Status: not run.** These files were written from Kubernetes documentation and checked only for valid YAML. They are a sketch for discussion, not a tested deployment.

## What Kubernetes would and would not give you
- **Gives:** several model servers behind one address, restarts if one fails, scheduled runs (for example a weekly job), resource limits, and a standard way for a platform team to operate it.
- **Does not give:** better answers or lower risk by itself. The privacy and approval controls come from the design of the project, not the platform.
- **Costs:** a platform team to run it, GPU scheduling that takes real effort, and storage and network rules to design. For a pilot, this is more work than the project itself.

## Another PoV
Most companies this size should stop at stage 2, or even stage 1. Kubernetes earns its place when many teams share the service, or when your IT department already runs everything on it and expects new tools to fit. If neither is true, it is decoration.

## Sovereignty note
Every stage keeps the model and the data inside your own environment. Moving to a cluster in your own data centre or a regional cloud keeps that true; moving to a hosted AI service would not.
