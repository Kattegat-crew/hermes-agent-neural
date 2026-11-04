---
name: vps-deployment-ops
description: >-
  Aprovisionamiento, despliegue y operaciones en el VPS. Gestión de Docker Compose, acceso SSH desde contenedores, Nginx Proxy Manager y servicios systemd.
tags: [vps, deploy, ssh, docker, nginx, systemd, infra, devops]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
---

# Operaciones y Despliegue en VPS

Habilidad canónica para aprovisionar servidores, desplegar el stack de contenedores Docker de la flota Hermes, gestionar sitios web y portales estáticos tras Nginx Proxy Manager, y ejecutar comandos en el host mediante SSH de forma segura.

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"despliega esto en el VPS"*, *"aprovisiona el nuevo servidor"*, *"ejecuta este comando en el host"*, *"configura el portal estático tras Nginx"*, o *"reinicia el servicio systemd"*.
- Configuración inicial de una máquina Ubuntu/Debian limpia (Docker, Docker Compose, Tailscale, ufw).
- Despliegue y actualización de portales web estáticos (Vite, Astro, HTML) con proxy inverso Nginx.
- Ejecución de comandos del host desde dentro de un contenedor o sandbox vía SSH (`10.0.2.1` o Tailscale IP).

---

## 1. Aprovisionamiento Base y Seguridad del VPS

Para preparar un VPS limpio para la flota:

```bash
# 1. Dependencias esenciales y Docker Engine
sudo apt-get update && sudo apt-get install -y curl git jq ufw fail2ban htop rsync
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Configurar Firewall (UFW)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (Nginx / Certbot)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 41641/udp # Tailscale
sudo ufw enable
```

---

## 2. Ejecución Host ↔ Contenedor vía SSH

Cuando un agente dentro de un contenedor necesita interactuar con el host o invocar binarios locales (como `composio`, `tailscale` o herramientas CLI fuera del contenedor):

```bash
# Conexión por red interna de Docker hacia el host
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@10.0.2.1 "<comando_en_el_host>"

# Comprobar estado de servicios en el host
ssh -o BatchMode=yes root@10.0.2.1 "systemctl status hermes-agent.service --no-pager"
```

---

## 3. Despliegue de Portales Web y Sitios Estáticos

Flujo para desplegar portales web, galerías o documentación servida por Nginx:

1. **Construcción y Sincronización**:
   ```bash
   # Compilar localmente o en worktree
   npm run build
   
   # Sincronizar directorio de salida hacia la ruta persistente del VPS
   rsync -avz --delete ./dist/ /opt/data/sites/<nombre-sitio>/public/
   ```
2. **Configuración de Nginx / Nginx Proxy Manager (NPM)**:
   * Servir archivos desde `/opt/data/sites/<nombre-sitio>/public/`.
   * Forzar HTTPS con certificado Let's Encrypt automático.
   * Configurar fallback para SPAs (`try_files $uri $uri/ /index.html;`).

---

## Gotchas y Errores Críticos en VPS

1. **Permisos en volúmenes compartidos**: Todo lo desplegado bajo `/opt/data/` debe tener permisos de lectura para el usuario web (`www-data` o `hermes` `uid 10000`). Si un deploy corre como `root`, ejecutar `chown -R hermes:hermes /opt/data/sites/<nombre-sitio>`.
2. **Puertos en conflicto**: Antes de levantar contenedores con Compose, validar puertos ocupados en el host con `ss -tulpn | grep :<puerto>`.
3. **Pérdida de variables en SSH**: Las sesiones SSH no interactivas (`ssh user@host "cmd"`) no cargan `~/.bashrc`. Cargar entornos explícitamente: `source /opt/data/config/.env && <comando>`.
