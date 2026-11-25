## Qué cambia

<!-- Una frase. Si necesitas un párrafo para explicar el cambio, el cambio es demasiado grande. -->

## Por qué

<!-- El problema real, no la solución. Qué se rompía, qué se perdía, qué costaba. -->

## Cómo se probó

<!-- Obligatorio: comando exacto y salida real, no "funciona en local". -->

```
$ 
```

## Cómo se revierte

<!-- Obligatorio: el comando o el commit que deshace esto. "Se vuelve a desplegar" no es un plan. -->

## Checklist

- [ ] Rama corta, no trabajo sobre el tronco
- [ ] Tests que cubren el cambio, y fallaban antes del fix
- [ ] Revisión de alguien distinto al autor (con veredicto, no un "ok")
- [ ] CI verde
- [ ] Sin secretos, tokens ni rutas privadas en el diff
- [ ] Si toca PROD: el despliegue es un paso aparte y explícito
