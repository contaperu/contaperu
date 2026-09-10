## Qué cambia y por qué

<!-- El qué ya lo dice el diff. Explica el porqué. -->

## Si tocas una regla contable

- [ ] Lleva **la fuente al lado**: norma, resolución o archivo real que la justifica.
- [ ] Hay un **test con un caso real** que el sistema de destino aceptó de verdad.

## Siempre

- [ ] `pytest` en verde (sin red y sin credenciales).
- [ ] **Ningún dato real**: ni comprobantes de clientes, ni RUC de empresas que existen, ni razones
      sociales reales. Lo que entra en la historia de un repositorio público no sale nunca más.
- [ ] Sin dependencias nuevas en el núcleo (si un driver necesita una, va como extra opcional).
- [ ] El asiento **cuadra**: `partida_doble.cuadra()` antes de escribir bytes.
