# 0008 · `imputaciones` en la raíz: el archivo explica su propio asiento

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 |
| **Test** | `tests/test_imputaciones_en_el_documento.py::test_las_dos_vias_dan_exactamente_lo_mismo` |

## Motivación

Hasta la 0.3 la imputación —la cuenta que eligió quien contabiliza— llegaba **solo** como argumento
de la llamada. Un documento guardado tenía los hechos (`comprobantes`) y el efecto (`asiento`), pero no la decisión que
los une: no se podía saber con qué cuentas se armó su propio asiento.

El caso real es el de cualquiera que archive un mes: el archivo tiene que explicarse solo, que es lo que el propio
estándar promete cuando dice que un documento «se entiende solo, en cualquier máquina, sin consultar nada».

## Fuente

`API-DE-REGISTRO.md`, «El formato: uno solo, el del estándar». La forma la tenía ya la fachada: el
argumento `imputacion` de `exportar`, `diagnosticar` y `generar_asiento`.

## Especificación

Clave `imputaciones` en la raíz del documento: un objeto llaveado por el `id_externo` de cada comprobante,
con `cuenta_contable`, `centro_costo`, `cuenta_tercero` y `reparto[]`. Opcional.

**El argumento `imputacion` se conserva** para quien ya integraba así, y **las dos formas a la vez se rechazan**:
adivinar cuál manda sería elegir en silencio la cuenta de un comprobante. Un test comprueba que las dos vías dan
exactamente lo mismo por las cuatro operaciones que la reciben.

No va en la configuración guardada: la configuración es del entorno y la imputación es de cada comprobante.
