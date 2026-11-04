---
name: tilt
description: "Use when running Tilt for multi-service local dev"
tags: [tilt, tiltfile, kubernetes, docker-compose, live-update, local-dev, devops]
license: MIT
compatibility: hermes, opencode, bash
metadata:
  hermes:
    tags: [tilt, tiltup, kubernetes, docker-compose, local-dev, live-update, devops]
    category: devops
---

# Tilt Multi-Service Local Development & Orchestration

Operational guide for configuring, launching, and debugging containerized development stacks with Tilt.

## 1. Core Principles

- **Fast Feedback Loops**: Use `live_update()` to sync changed source code directly into running containers without triggering full image rebuilds.
- **Unified Observability**: Stream logs and track health endpoints across multiple microservices simultaneously.
- **Portability**: Keep the `Tiltfile` declarative in Starlark syntax.

---

## 2. Common Tilt Workflows

### A. Launching the Stack (`tilt up`)
```bash
# Launch Tilt in headless / terminal stream mode
tilt up --stream

# Launch with web UI on a custom port
tilt up --port 10350

# Check status of running services
tilt get uiresources
```

### B. Tearing Down Environment
```bash
tilt down --delete-namespaces
```

---

## 3. Tiltfile Architecture Patterns

### Pattern: Docker Compose Orchestration with Live Reload
```python
# Tiltfile
docker_compose('docker-compose.yml')

# Enable live sync for backend service
docker_build(
    'my-app-backend',
    '.',
    live_update=[
        sync('./src', '/app/src'),
        run('pip install -r requirements.txt', trigger=['requirements.txt']),
    ]
)
```

### Pattern: Kubernetes Dev Deployment
```python
k8s_yaml('k8s/*.yaml')
k8s_resource('auth-service', port_forwards='8080:8080')
```

---

## 4. Best Practices for Headless Environments

1. **Avoid TTY Dependencies**: Always run `tilt up --stream` when automated inside CI/CD or by autonomous agents.
2. **Resource Throttling**: Configure resource triggers (`trigger_mode=TRIGGER_MODE_MANUAL`) for heavy build steps to prevent CPU thrashing.
