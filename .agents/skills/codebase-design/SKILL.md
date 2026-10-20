---
name: codebase-design
description: >-
  Diseño de módulos profundos (Ousterhout) y costuras limpias (seams). Maximización del apalancamiento de interfaces y localización de lógica para alta testabilidad.
tags: [arquitectura, diseno, deep-modules, seams, testabilidad, ousterhout, codigo]
version: 2.0.0
author: NeuralCrew / Hermes Fleet
license: MIT
platforms: [linux, macos, windows]
---

# Diseño de Código: Módulos Profundos y Costuras (Seams)

Habilidad canónica para diseñar **módulos profundos**: una gran cantidad de comportamiento y lógica de negocio encapsulada tras una interfaz pequeña, ubicada en una costura limpia (*seam*) y testeable directamente a través de esa interfaz. Basada en los principios de diseño de John Ousterhout (*A Philosophy of Software Design*) y Michael Feathers (*Working Effectively with Legacy Code*).

---

## Cuándo usar esta Skill (Triggers y Síntomas)

Usa esta skill inmediatamente cuando se presente cualquiera de estas situaciones:
- Peticiones del usuario: *"diseña la interfaz de este módulo"*, *"refactoriza este servicio"*, *"cómo organizo esta lógica para que sea testeable"*, o *"el código está muy acoplado y fragmentado"*.
- Diagnóstico de **código superficial (shallow)**: clases o funciones pasarela que solo delegan llamadas sin agregar valor, donde la interfaz tiene casi tantos parámetros y métodos como la lógica interna.
- Fricción de navegación: para entender un solo caso de uso, el agente o desarrollador debe saltar entre 5 archivos diminutos que no concentran estado ni decisiones (*shotgun surgery*).
- Dificultad para escribir tests unitarios limpios sin tener que mockear 10 dependencias internas.

---

## Vocabulario Canónico

Usa estos términos con precisión técnica en las discusiones y en el código; evita términos vagos como "componente", "servicio genérico" o "capa":

- **Módulo (Module)**: Cualquier pieza de software con una interfaz y una implementación. Es agnóstico a la escala: una función pura, una clase de dominio, un paquete o un módulo hexagonal.
- **Interfaz (Interface)**: Todo lo que un consumidor debe saber para usar el módulo correctamente: la firma de tipos, pero también las invariantes de negocio, pre/post-condiciones, modos de error esperados y contratos de rendimiento.
- **Implementación (Implementation)**: El cuerpo interno de código que ejecuta el comportamiento del módulo. Se mantiene privado y protegido del exterior.
- **Profundidad (Depth)**: Grado de apalancamiento que ofrece la interfaz. Un módulo es **profundo** cuando mucha complejidad queda oculta tras una interfaz simple y concisa. Es **superficial (shallow)** cuando la interfaz es casi tan compleja como lo que hace por dentro.
- **Costura (Seam)**: Un punto donde se puede alterar o interceptar el comportamiento del sistema sin necesidad de editar código en ese mismo lugar (ej. pasar un adapter o cliente como dependencia).
- **Adaptador (Adapter)**: La implementación concreta que satisface una interfaz en una costura (ej. un repositorio Postgres vs. un repositorio falso en memoria para tests).
- **Apalancamiento (Leverage)**: El beneficio para los consumidores: aprenden una interfaz pequeña y obtienen capacidades de alto nivel.
- **Localización (Locality)**: El beneficio para el mantenimiento: los bugs, cambios de esquema y validaciones se concentran en un único punto en lugar de regarse por todo el proyecto.

---

## Módulos Profundos vs. Módulos Superficiales

### Módulo Profundo (Preferir Siempre)
Interfaz pequeña + Implementación rica y autónoma:

```
┌─────────────────────────────────┐
│     Interfaz Pequeña (Simple)   │  ← Pocos métodos públicos, parámetros concisos
├─────────────────────────────────┤
│                                 │
│   Implementación Profunda       │  ← Reglas de negocio complejas, caché,
│   y Encapsulada                 │     manejo de errores y persistencia ocultos
│                                 │
└─────────────────────────────────┘
```

### Módulo Superficial (Anti-Patrón a Evitar)
Interfaz amplia + Implementación delgada (pasarela):

```
┌─────────────────────────────────┐
│       Interfaz Enorme           │  ← Demasiados métodos, DTOs redundantes
├─────────────────────────────────┤
│   Implementación Pasarela       │  ← Solo delega a otra clase sin valor real
└─────────────────────────────────┘
```

Al diseñar una interfaz, pregúntate siempre:
1. ¿Puedo reducir la cantidad de métodos públicos?
2. ¿Puedo simplificar los parámetros aceptando tipos de dominio en vez de argumentos sueltos?
3. ¿Puedo ocultar decisiones internas (reintentos, transacciones, validaciones) dentro de la implementación?

---

## Principios No Negociables de Diseño

1. **La profundidad es una propiedad de la interfaz, no de la implementación**: Un módulo profundo puede componerse internamente de funciones auxiliares privadas o clases de apoyo; lo vital es que no exponga esa fontanería a los consumidores.
2. **El test de eliminación (The Deletion Test)**: Imagina que eliminas el módulo. Si la complejidad desaparece, era un passthrough redundante. Si la complejidad se riega y reaparece duplicada en 5 consumidores distintos, el módulo estaba cumpliendo su rol y ganando su lugar.
3. **La interfaz es la superficie de pruebas**: Las pruebas automatizadas deben interactuar con el módulo a través de su interfaz pública, no espiando variables o métodos privados. Si necesitas testear detalles privados, la forma del módulo está mal planteada.
4. **Un adaptador = costura hipotética; dos adaptadores = costura real**: No introduzcas interfaces abstractas complejas si solo existe y existirá una única implementación. Diseña costuras donde realmente haya variación (ej. base de datos real vs. fake en tests).

---

## Diseño Orientado a la Testabilidad

Para que un módulo sea testeable sin sufrimiento:

1. **Acepta dependencias, no las instancies internamente**:
   ```typescript
   // Correcto (Costura testeable vía inyección)
   function procesarPago(orden: Orden, pasarela: PasarelaPago): ResultadoPago {}

   // Incorrecto (Acoplamiento rígido difícil de simular)
   function procesarPago(orden: Orden): ResultadoPago {
     const pasarela = new PasarelaStripe();
   }
   ```

2. **Retorna resultados, evita mutaciones ocultas**:
   ```typescript
   // Correcto (Función pura con retorno explícito)
   function calcularDescuento(carrito: Carrito): Descuento {}

   // Incorrecto (Efecto secundario mutando estado externo)
   function aplicarDescuento(carrito: Carrito): void {
     carrito.total -= 5000;
   }
   ```

3. **Superficie de contacto mínima**: Menos métodos públicos implican menos casos de prueba requeridos y menor fragilidad ante refactorizaciones futuras.
