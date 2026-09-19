"""La huella del asiento: una cifra que dice «este contenido ya salió».

El Excel de CONCAR **se suma** al importarlo: importar dos veces la misma exportación duplica los asientos, y
es el error más caro del flujo real. Las APIs de fuera lo atajan con un id externo y una clave de
idempotencia (QuickBooks `SyncToken`, Xero `Idempotency-Key`; ver `REFERENCIAS.md`); aquí, donde el
destino es un archivo y no una API, lo que se puede hacer es dejar en cada exportación una huella
determinista de lo que salió, para que quien la guarde reconozca la exportación si vuelve a aparecer.

Es la huella del **contenido del asiento**, no del archivo:

- va sobre las líneas neutrales (`LineaDiario.a_dict()`), **en el orden en que salen** —el orden es
  parte del asiento: principal, IGV, retención, tercero, detracción— y no se reordenan;
- con **todo** lo que dice el asiento: sub-diario, fecha, cuentas, sentidos, importes (texto exacto),
  glosas, documento, referencia y detracción. Un céntimo la cambia; una configuración que mueva el
  sub-diario también, porque es otro asiento;
- **menos tres campos**, cada uno por su motivo, y los tres están en `SIN`.

Lo que queda fuera, y por qué (todos con la misma prueba: si entrara, la huella diría que dos contenidos
iguales son distintos):

- **`correlativo`** — la misma exportación, repetida tras un «deshacer», arranca en otro número y sigue
  siendo la misma. La pregunta que responde la huella es «¿este contenido ya salió?»; la del correlativo la
  responden los bytes del archivo.
- **`clase`** — es función total de `cuenta`, que sí entra. No aporta información, así que excluirla no puede
  hacer que dos asientos distintos compartan huella. **Esto solo es cierto mientras el motor rechace una
  `clase` que contradiga su cuenta**: si algún día se acepta, `clase` tiene que volver a entrar.
- **`documento.id_externo`** — es el id del sistema que produjo el comprobante, no contenido contable. Y es el
  caso que la huella existe para atajar: al reexportar tras un «deshacer», la aplicación recrea sus filas con
  ids nuevos, así que con el id dentro la misma tanda daría otra huella y el aviso de lote repetido se
  apagaría justo cuando hace falta.

`SIN` admite **rutas con punto** para alcanzar un campo de un bloque —la misma convención que `kit/columnas`—,
porque un campo anidado en `SIN` sin eso no haría nada y la huella cambiaría en silencio.

La fórmula es contrato: sha256 de `json.dumps(cuerpo, sort_keys=True, ensure_ascii=False,
separators=(",", ":"))`. Cambiarla invalida todas las huellas guardadas por quien la persista, así que
se anuncia como cambio de comportamiento (`CHANGELOG.md`) y `tests/test_huella.py` la fija con un
valor literal. Sin reloj y sin estado, como todo el núcleo.
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable

SIN = ("correlativo", "clase", "documento.id_externo")


def _sin_lo_excluido(d: dict) -> dict:
    """El dict de una línea sin los campos de `SIN`, alcanzando también los de sus bloques por su ruta con punto.
    Un bloque que se queda vacío desaparece, como ya hace `a_dict()` con lo vacío."""
    fuera: set[str] = {c for c in SIN if "." not in c}
    anidados: dict[str, set[str]] = {}
    for camino in SIN:
        if "." in camino:
            bloque, campo = camino.split(".", 1)
            anidados.setdefault(bloque, set()).add(campo)
    salida = {}
    for clave, valor in d.items():
        if clave in fuera:
            continue
        if clave in anidados and isinstance(valor, dict):
            valor = {k: v for k, v in valor.items() if k not in anidados[clave]}
            if not valor:
                continue
        salida[clave] = valor
    return salida


def huella(lineas: Iterable) -> str:
    """La huella hexadecimal (sha256) de estas líneas de diario, en su orden."""
    cuerpo = []
    for ln in lineas:
        d = ln.a_dict() if hasattr(ln, "a_dict") else dict(ln)
        cuerpo.append(_sin_lo_excluido(d))
    texto = json.dumps(cuerpo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
