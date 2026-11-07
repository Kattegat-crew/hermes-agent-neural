# Informe PEGUELO — plantilla de 10 líneas

Usar exactamente este orden. Máximo 10 líneas visibles; el detalle va al JSON.

```
PEGUELO · <fecha> · <session_id> · <título>
Score <n>/8 · tools <fallos>/<total> (<%>) · repeticiones <n> · correcciones <n>
1. Pedido: <qué quería el humano, 1 línea>
2. Entregado: <qué quedó, 1 línea + evidencia (#idx o ruta)>
3. Mal hecho: <máx 3, cada uno con #idx o métrica>
4. Crítica hostil: <2 líneas sin defensa>
5. Correcciones del humano: <cita textual o "ninguna">
6. Lecciones (máx 3): <regla → destino (skill/memoria/brain/guard/nada)>
7. Aplicado ahora: <parche o memoria concreta, o "nada (bajo riesgo insuficiente)">
8. Propuesto con OK: <guard/cambio que requiere aprobación, o "nada">
9. Sin evidencia: <afirmaciones que no puedo probar, o "nada">
10. Próxima vez distinto: <1 frase operativa y verificable>
```

## Reglas de redacción

- Español, sin relleno, sin «quedo atento».
- Cada línea de la 3 cita `#idx` o una métrica del dossier. Sin cita, no va.
- Si el score es 8/8, la línea 3 dice qué se hizo bien y qué se automatizó; no se convierte en autoelogio.
- Si la sesión es de cron (sin humano), escribir «archivado» en la línea 5 y omitir la respuesta al usuario.
- El informe se guarda en `/opt/data/brain/ops/session-retros/YYYY-MM-DD-<session_id>.md` junto al JSON.
