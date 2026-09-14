"""La huella del asiento: una cifra que dice «este contenido ya salió».

El Excel de CONCAR **se suma** al importarlo: importar dos veces la misma exportación duplica los asientos, y
es el error más caro del flujo real. Las APIs de fuera lo atajan con un id externo y una clave de
idempotencia (QuickBooks `SyncToken`, Xero `Idempotency-Key`; ver `REFERENCIAS.md`); aquí, donde el
destino es un archivo y no una API, lo que se puede hacer es dejar en cada exportación una huella
determinista de lo que salió, para que quien la guarde reconozca la exportación si vuelve a aparecer.

Es la huella del **contenido del asiento**, no del archivo:

- va sobre las líneas neutrales (`LineaDiario.a_dict()`), **en el orden en que salen** —el orden es
  parte del asiento: principal, IGV, retención, tercero, detracción— y no se reordenan;
- **sin el `correlativo`**: la misma exportación, repetida tras un «deshacer», arranca en otro
  número y sigue siendo la misma. La pregunta que responde es «¿este contenido ya salió?»;
  la del correlativo la responden los bytes del archivo;
- con todo lo demás: sub-diario, fecha del asiento, cuentas, sentidos, importes (texto exacto),
  glosas, documento, referencia y detracción. Un céntimo la cambia; una configuración que mueva el
  sub-diario también, porque es otro asiento.

La fórmula es contrato: sha256 de `json.dumps(cuerpo, sort_keys=True, ensure_ascii=False,
separators=(",", ":"))`. Cambiarla invalida todas las huellas guardadas por quien la persista, así que
se anuncia como cambio de comportamiento (`CHANGELOG.md`) y `tests/test_huella.py` la fija con un
valor literal. Sin reloj y sin estado, como todo el núcleo.
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable

SIN = ("correlativo",)


def huella(lineas: Iterable) -> str:
    """La huella hexadecimal (sha256) de estas líneas de diario, en su orden."""
    cuerpo = []
    for ln in lineas:
        d = ln.a_dict() if hasattr(ln, "a_dict") else dict(ln)
        cuerpo.append({k: v for k, v in d.items() if k not in SIN})
    texto = json.dumps(cuerpo, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()
