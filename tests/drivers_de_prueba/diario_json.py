"""Un sistema contable de mentira que importa sus asientos en JSON, uno por comprobante.

Es la forma de lo que pedirá un legacy nuevo como STARSOFT (`ARQUITECTURA.md`, «STARSOFT: qué se sabe y qué falta»):
canal `legacy`, forma `desde_lineas` con el índice de cada comprobante, un cuerpo JSON en vez de un Excel, y un
`no_caben` propio. No viaja en el paquete: prueba que el contrato v1 ya cubre lo que ese driver necesitará sin tocar el
núcleo.
"""
from __future__ import annotations

import json

from contaperu.asiento import glosa_de
from contaperu.asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from contaperu.drivers.kit import OpcionesArchivo

NOMBRE = "diario_json"
CANAL = "legacy"
FORMATOS = {"compra": "diario_json", "venta": "diario_json"}
OPCIONES = OpcionesArchivo(extension=".json")
CONTENT_TYPE = "application/json"
EXIGE = frozenset()
CONFIGURACION = CONFIGURACION_DEL_ASIENTO
LARGO_GLOSA = 60


def nombre(libro, opciones=OPCIONES) -> str:
    return f"diario_{libro.ruc}_{libro.periodo}_{libro.tipo}{opciones.extension}"


def no_caben(libro, comprobantes, config) -> dict:
    return {f"con una glosa de más de {LARGO_GLOSA} caracteres":
            [c for c in comprobantes if len(glosa_de(c)) > LARGO_GLOSA]}


def desde_lineas(libro, lineas, config, opciones=OPCIONES, *, indice=()) -> tuple[bytes, dict]:
    asientos = [{"sub_diario": entrada.sub_diario, "numero": entrada.correlativo,
                 "comprobante": entrada.cabecera.a_dict(),
                 "lineas": [linea.a_dict() for linea in entrada.lineas(lineas)]}
                for entrada in indice]
    cuerpo = {"libro": libro.a_dict(), "asientos": asientos}
    return json.dumps(cuerpo, ensure_ascii=False, indent=1).encode("utf-8"), {"asientos": len(asientos)}
