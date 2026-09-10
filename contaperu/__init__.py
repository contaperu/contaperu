"""ContaPerú — núcleo contable abierto del Perú.

Lee los comprobantes que emite SUNAT, arma la partida doble y los exporta al formato que pide
cada sistema contable. **Sin estado**: ni base de datos, ni archivos, ni sesiones, ni red. Todo
entra por parámetro y sale por retorno, así que cada llamada se explica sola y se puede repetir
mil veces con el mismo resultado.

El camino completo, de un XML a un Excel de asientos:

    from contaperu import Libro, lectores, validar, drivers, generar

    libro = Libro(ruc="20601234567", razon_social="MI EMPRESA SAC",
                  periodo="202601", tipo="compra")
    lote = lectores.archivos.Lote()
    lectores.archivos.expandir("comprobantes.zip", datos, lote=lote)
    res = lectores.archivos.convertir_xml(lote, libro)
    comprobantes = lectores.archivos.ordenar(res.comprobantes)
    validar.revisar(comprobantes, libro)
    exp = generar.generar(libro, comprobantes, "concar",
                          contab=configuracion, correlativos={"11": 1})

El estándar de datos que habla es `pe-ledger`; su esquema está en `estandar/`.
"""
from __future__ import annotations

from . import (asiento, catalogos, detracciones, drivers, formato, generar, lectores,
               operaciones, partida_doble, pcge, validar)
from .modelo import Comprobante, Libro, Observacion

__version__ = "0.2.0"
PE_LEDGER = "0.1"          # versión del estándar de datos, distinta de la de la librería

__all__ = [
    "Comprobante", "Libro", "Observacion",
    "asiento", "catalogos", "detracciones", "drivers", "formato", "generar", "lectores",
    "operaciones", "partida_doble", "pcge", "validar", "PE_LEDGER", "__version__",
]
