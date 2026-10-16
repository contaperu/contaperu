"""Comprobantes: el papel de una compra o una venta, y lo que se lee de él.

Es el espejo de `tesoreria/` sobre el otro lado del motor. Tesorería agrupa la forma del dinero —el movimiento,
su imputación, la cuenta, la referencia—; aquí se agrupa la forma del comprobante, que hasta la 12.11 vivía
repartida: el hecho en `modelo/`, lo que el ERP decide en `asiento/`, sus lectores en `lectores/` y la suma del
mes en `contable/`. La asimetría se veía en una tabla: `Movimiento` e `ImputacionDeMovimiento` eran vecinos y
`Comprobante` e `Imputacion` estaban en paquetes distintos, aunque son la misma pareja del otro libro.

**Qué hay aquí, y qué no.** Hay la forma de un hecho y lo que hace falta para leerla:

- `Comprobante` — una fila del registro de compras o de ventas, con lo que dice el papel y nada más, y su
  **identidad** (`clave_de`, `identidad_de`): los cuatro datos que deciden si dos comprobantes son el mismo.
- `Imputacion` y `Parte` — **lo que el ERP decide** sobre un comprobante y que el papel no dice: la cuenta, el
  centro, la cuenta del total, el código de la detracción, que una factura quedó anulada por una nota, y el
  reparto de la base. Llega aparte, con el `id_externo` como llave. Es la pareja de `Comprobante` igual que
  `ImputacionDeMovimiento` lo es de `Movimiento`, y por eso están juntas: tenerlas en paquetes distintos era la
  asimetría que esto vino a arreglar.
- `resumen.del_libro` — **cuánto es un mes**: la base, el IGV y el total, cada moneda por su lado y con la nota
  de crédito restando. Estaba en `contable/`, el paquete de lo que no depende del país, y no cumplía su
  criterio: para sumar un libro hay que saber qué códigos de la Tabla 10 son nota de crédito. Su hermano
  `por_cuenta`, el pre-mayor, sí lo cumple y se quedó allí.
- Los **lectores**: `xml_ubl` (el XML UBL 2.1 de SUNAT), `sire_txt` (el TXT de la propuesta) y `archivos`, que
  desarma el ZIP y reparte. Son la puerta de entrada de este libro y de ningún otro.

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
from .imputacion import Imputacion, Parte

__all__ = [
    "CAMPOS_DEL_DOCUMENTO", "CAMPOS_DEL_SISTEMA", "CAMPOS_DE_LA_REVISION", "CONDICIONES_PAGO", "Comprobante",
    "Imputacion", "NOTAS", "NOTAS_CREDITO", "NOTAS_DEBITO", "ORIGENES", "Observacion", "Parte",
    "RETIRADOS_EN_0_3", "clave_de", "identidad_de",
]
