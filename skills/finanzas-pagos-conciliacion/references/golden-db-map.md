# golden.db — mapa de tablas (verificado en vivo en PROD)

- **pagos**: `id, fecha, marca, monto, beneficiario, fuente (pse|netcash|aval|avalpay|ecollect|libro|...), id_externo, detalle, categoria, concepto, sede, duplicado_de`. Pendiente = `categoria IS NULL OR 'por clasificar'`, siempre con `duplicado_de IS NULL`.
- **pregunta_dia** (`dia` PK, `ids`, `enviada_en`): mapeo global número→pago del día. Se PISA entre marcas (PRIMARY KEY por día).
- **pregunta_dia_marca** (`dia`+`marca` PK, `ids`, `enviada_en`): pin autoritativo por marca; lo escribe `preguntas.py` y lo lee `respuestas_marca.py`. Los ids están en el mismo orden en que se numeró la pregunta.
- **clasificacion_journal** (`ts, pago_id, antes, despues, categoria, concepto, sede`): auditoría de cada escritura. `despues='respuesta manual (gate)'` = vía `respuestas_marca.py`; `'respuesta manual'` = vía `respuestas.py` legacy.
- **conceptos_aprendidos** (`patron, categoria, concepto, sede, monto_ref`): reglas aprendidas por beneficiario para el clasificador automático.

## Probe de lectura (PROD)
Preparar el script Python localmente (sintaxis validada al vuelo) → `scp /tmp/x.py prod:/tmp/x.py` → `ssh prod 'docker cp /tmp/x.py hermes-agent:/tmp/x.py && docker exec hermes-agent python3 /tmp/x.py'`. Abrir la DB SIEMPRE read-only: `sqlite3.connect("file:/opt/data/finanzas-casinos/golden.db?mode=ro", uri=True)`. Reglas de staging, deny rules y saneo: skill `fleet-profile-forensics`.
