---
name: orbstack-best-practices
description: "Use when running OrbStack or Docker on macOS hosts"
tags: [orbstack, docker, macos, contenedores, rosetta, virtualizacion, devops]
license: MIT
compatibility: hermes, opencode, bash
metadata:
  hermes:
    tags: [orbstack, docker, macos, virtualization, containers, devops]
    category: devops
---

# OrbStack Container & Linux VM Management (macOS)

Comprehensive guidelines for operating OrbStack as a high-performance, lightweight alternative to Docker Desktop and Colima on Apple Silicon and Intel macOS.

## 1. Core Architecture Advantages

- **Instant Startup**: Near-instant VM boot times with minimal CPU/RAM idle footprint.
- **Direct Domain & IP Routing**: Containers receive direct routable IPs on the host network (`container-name.orb.local`), eliminating complex port mapping.
- **Native File Sharing**: Two-way file sharing using VirtioFS with near-native I/O throughput.

---

## 2. Command Line Operations (`orb`)

### A. Managing Linux Virtual Machines
```bash
# Launch a lightweight Ubuntu machine
orb create ubuntu:24.04 my-server

# Run commands directly inside the VM from macOS host
orb -m my-server uname -a

# Open a shell inside the machine
orb -m my-server

# List and manage running machines
orb list
orb stop my-server
orb delete my-server
```

### B. Docker Engine Configuration
```bash
# Switch Docker context to OrbStack
docker context use orbstack

# Verify active engine
docker info | grep "Server Version"
```

---

## 3. Performance & Resource Optimization

1. **Rosetta 2 Emulation**: Enable x86_64 emulation via Rosetta for running legacy Intel Docker images on Apple Silicon with 5x higher performance than QEMU.
2. **Dynamic Memory Allocation**: Do not manually set fixed RAM ceilings; let OrbStack dynamically borrow and release host memory to the macOS kernel.
3. **Volume Mounts**: Place heavy database volumes in native OrbStack Linux filesystems rather than macOS bind mounts when running write-heavy workloads.
