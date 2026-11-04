# Perfiles reales en Hermes PROD — verificado 24/08/2026

Fuente: `ls /opt/hermes/data/profiles/` y `grep -A 60 "profile_routes:" /opt/hermes/data/config.yaml` en VPS prod (169.58.189.222), vía cadena SSH contenedor → root@10.0.7.1 → ssh -i /root/.ssh/id_ed25519 root@169.58.189.222.

## Perfiles activos

`default` (Ragnar/admin), `helmer`, `jacqueline`, `nancy`, `yulieth`, `neural-admin-test`.

**NO existen perfiles `golden-game`/`lucky-club` desplegados** — fueron reemplazados por perfiles por persona (Engram #252, #272). Lo que queda de ellos son plantillas sin desplegar en `/opt/data/hermes-casinos-repo/profiles/{golden-game,lucky-club}/`.

## Ruteo WhatsApp (profile_routes — fuente de verdad)

Un solo número WhatsApp compartido; cada persona tiene 3 formas de chat_id apuntando a su perfil:

| Perfil | Persona | Número plano | JID | LID |
|---|---|---|---|---|
| helmer | Helmer (gerente Golden) | 573166909310 | 573166909310@s.whatsapp.net | 109165234127014@lid |
| jacqueline | Jacqueline (Luz Miryam Jacqueline Guzmán Restrepo) | 573166909018 | 573166909018@s.whatsapp.net | 138023102591227@lid |
| yulieth | Yulieth | 573107864877 | 573107864877@s.whatsapp.net | 194373190996209@lid |
| nancy | Nancy (geógrafa, pagos Golden, novia de Jonathan) | 573214094625 | 573214094625@s.whatsapp.net | 42743615213574@lid |
| default | Jonathan (admin) | 573166910728 | 573166910728@s.whatsapp.net | 43001262956766@lid |

Nota: `cogollosour` era el nombre previo del perfil de pruebas de Jonathan; normalizado a `default` con api_server y whatsapp desactivados en secundarios (fix doble adapter, Engram #272).

## Reglas duras

- PROHIBIDO enviar WhatsApp proactivo a 573166909310 / 573166909018 / 573107864877 sin orden explícita del usuario (Engram #252). El envío proactivo existe vía `POST /send` del bridge (127.0.0.1:3000 en prod) con chatId JID/LID/número; anti-echo en `recentlySentIds`.
- El allowlist REAL del bridge viene de `WHATSAPP_ALLOWED_USERS` en `/opt/hermes/.env` del prod (env_file del compose), NO de config.yaml. Cambios en env requieren RECREAR el contenedor (`docker compose up -d`), no solo restart.
