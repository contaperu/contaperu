"""Un ERP nuevo de mentira que recibe los TRES libros en el estándar, tesorería incluida.

Existe para probar que el motor arma el asiento del dinero **por la api** sin tocar todavía el driver de serie: en
la 12.9 `generar_asiento` ya sabe hacerlo y el que viaja en el paquete (`drivers/asiento_contable`) aún no declara
el libro, porque declararlo sin el camino de `exportar` dejaría a `exportar` dando el mensaje engañoso que la 12.6
quitó. Así que el contrato se prueba con éste, como se probó con `diario_json` lo que pedía STARSOFT.

Canal `erp` y vocabulario `neutral`, que es lo que hace posible el asiento de tesorería: con vocabulario legacy el
libro se para en `LibroQueTodaviaNoSeNumera`, porque su sub-diario espera un archivo real que lo pida.
"""
from __future__ import annotations

import json

from contaperu.drivers.kit import OpcionesArchivo

NOMBRE = "erp_tesoreria"
CANAL = "erp"
VOCABULARIO = "neutral"
FORMATOS = {"compra": "erp_tesoreria_json", "venta": "erp_tesoreria_json", "tesoreria": "erp_tesoreria_json"}
OPCIONES = OpcionesArchivo(extension=".json")
CONTENT_TYPE = "application/json"
EXIGE = frozenset()
CONFIGURACION: tuple = ()


def nombre(libro, opciones=OPCIONES) -> str:
    return f"erp_{libro.ruc}_{libro.periodo}_{libro.tipo}{opciones.extension}"


def desde_lineas(libro, lineas, config, opciones=OPCIONES, *, indice=()) -> tuple[bytes, dict]:
    cuerpo = {"libro": libro.a_dict(), "asiento": [linea.a_dict() for linea in lineas],
              "entradas": len(indice)}
    return json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"), {"entradas": len(indice)}
