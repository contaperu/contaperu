"""Comprobantes: el papel de una compra o una venta, y lo que se lee de él.

Es el espejo de `tesoreria/` sobre el otro lado del motor. Tesorería agrupa la forma del dinero —el movimiento,
su imputación, la cuenta, la referencia—; aquí se agrupa la forma del comprobante, que hasta la 12.11 vivía
repartida: el hecho en `modelo/`, lo que el ERP decide en `asiento/`, sus lectores en `lectores/` y la suma del
mes en `contable/`. La asimetría se veía en una tabla: `Movimiento` e `ImputacionDeMovimiento` eran vecinos y
`Comprobante` e `Imputacion` estaban en paquetes distintos, aunque son la misma pareja del otro libro.

**Qué hay aquí, y qué no.** Hay la forma de un hecho y lo que hace falta para leerla:

- `Comprobante` — una fila del registro de compras o de ventas, con lo que dice el papel y nada más, y su
  **identidad** (`clave_de`, `identidad_de`): los cuatro datos que deciden si dos comprobantes son el mismo.

**No hay asiento**, que es lo que SALE de un comprobante y vive en `asiento/`, igual que el asiento de un
movimiento no vive en `tesoreria/`. **No hay tributos**: el IGV, las detracciones y la validación son de
`tributos/`, que es el paquete de lo peruano —aquí se dice QUÉ es un comprobante, allí DÓNDE rige—, y la hoja
de ruta lo reserva para `jurisdicciones/pe` (hito J4). Separarlos ahora es lo que evita moverlos dos veces.

**Las rutas viejas siguen sirviendo y no avisan**, porque esto no retiró nada: `contaperu.modelo` reexporta
estos nombres como siempre. Lo demuestra que la superficie pública pase sin regenerarse.
"""
from __future__ import annotations

from .comprobante import (CAMPOS_DEL_DOCUMENTO, CAMPOS_DEL_SISTEMA, CAMPOS_DE_LA_REVISION, CONDICIONES_PAGO,
                          NOTAS, NOTAS_CREDITO, NOTAS_DEBITO, ORIGENES, RETIRADOS_EN_0_3, Comprobante,
                          Observacion, clave_de, identidad_de)

__all__ = [
    "CAMPOS_DEL_DOCUMENTO", "CAMPOS_DEL_SISTEMA", "CAMPOS_DE_LA_REVISION", "CONDICIONES_PAGO", "Comprobante",
    "NOTAS", "NOTAS_CREDITO", "NOTAS_DEBITO", "ORIGENES", "Observacion", "RETIRADOS_EN_0_3", "clave_de",
    "identidad_de",
]
