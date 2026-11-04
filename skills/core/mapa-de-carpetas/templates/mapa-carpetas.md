# 📁 Mapa de carpetas — <RAÍZ / CLIENTE>

> Generado con skill `mapa-de-carpetas` (SCAN → MAP → RULES → VERIFY).
> Fecha: AAAA-MM-DD · Raíz escaneada: <ruta o Drive folder ID>
> Fuente única de verdad: `/opt/data/brain/folder-maps/<raiz>.md` + `carpetas.md` en la raíz.

## Árbol

```
<pegar árbol de scan_tree.py / drive_map.py>
```

## Carpetas

| Ruta / ID | Propósito | Qué va aquí | Qué NO va | Ejemplos |
|-----------|-----------|-------------|-----------|----------|
| `<ruta>` | <para qué existe esta carpeta> | <tipos de archivo aceptados> | <lo que está prohibido> | <1-2 ejemplos reales> |
| `<ruta>` | <...> | <...> | <...> | <...> |

## Reglas de ruteo

| Tipo de documento | Carpeta destino | Regla de nombre |
|-------------------|-----------------|-----------------|
| Informe de cliente | `Informes/` | `AAAA-MM-DD_informe_<cliente>_<tema>.docx` |
| Contrato / legal | `Legal/` | `<cliente>_<tipo-contrato>_AAAA.ext` |
| Assets de marca | `Brand/` | `logo_<marca>_<variante>.png` |
| Material de campaña | `Campañas/<nombre-campaña>/` | `<AAAA>-<mes>_<campaña>_<asset>.png` |
| ... | ... | ... |

## Reglas de la casa (invariantes)

1. **Un documento de cliente → carpeta del cliente.** Nunca en carpetas genéricas.
2. **No crear carpetas nuevas sin autorización** del Admin; cualquier carpeta nueva se
   registra aquí ANTES de crearse (en las dos copias del mapa).
3. **Nombres kebab-case descriptivos:** `AAAA-MM-DD_tipo_cliente_descripcion.ext`.
   Prohibidos: "nuevo", "final2", "copia", "sin nombre", "aqui".
4. **Verificación post-escritura:** read-back de la ruta; si quedó fuera → mover y anotar.

## Log de cambios

- AAAA-MM-DD — registro inicial (scan de <raíz>).
- AAAA-MM-DD — <cambio de estructura + autorización usada>.