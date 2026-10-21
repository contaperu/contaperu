# 0034 · Un nombre por retención: `retencion` pasa a ser `retencion_4ta`

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | cambio de significado |
| **Nivel** | mayor |
| **Versión** | open-accounting 4.0 |
| **Test** | `tests/test_retenciones.py`, `tests/test_serializacion.py` |

## Motivación

El Perú tiene dos retenciones que en castellano se llaman igual, y el comprobante tenía **un** campo
llamado `retencion`:

| | Qué es | Dónde aparece | Tasa |
|---|---|---|---|
| **Renta de 4ta** | lo que el pagador le retiene al profesional independiente | recibo por honorarios (tipo `02`) | 8 % del honorario bruto |
| **Régimen de Retenciones del IGV** | lo que el comprador *agente de retención* le retiene al proveedor | factura (tipo `01`) | 3 % del importe total |

Ese nombre genérico **costó dos averías de verdad**, y las dos están documentadas en el repositorio:

1. **Un dato que se perdió sin aviso.** Alguien escribió `retencion_4ta` —el nombre específico, el que
   parece natural— donde el campo se llamaba `retencion`. El lector lo filtraba en silencio y **el mes
   se exportó entero sin su línea de retención**: solo se veía leyendo las celdas del Excel. De ahí
   salió el rechazo de claves desconocidas de `de_dict` (3.10) y su caso en `test_serializacion.py`.
2. **Un dato que aterrizó en la columna equivocada** (20-oct-2026). Una aplicación que integra el
   motor volcó en ese campo el 3 % del IGV que SUNAT declara de una factura, porque **no había dónde
   ponerlo**: dos facturas de producción acabaron observadas con `RETENCION_NO_APLICA`. El aviso del
   motor era lo único que estaba bien.

La segunda avería es el **caso real** que la enmienda [0005](0005-retencion-de-igv.md) esperaba, y
las dos juntas dicen que el problema no era el mapeo de nadie: era el nombre.

## Fuente

Renta de 4ta: art. 74 de la Ley del Impuesto a la Renta y la R.S. 013-2007/SUNAT (la suspensión).
Régimen de Retenciones del IGV: R.S. 037-2002/SUNAT; el 3 % rige desde el 01-03-2014, por la
R.S. 033-2014/SUNAT.

## Especificación

El campo `retencion` del comprobante pasa a llamarse **`retencion_4ta`**. Mismo tipo (importe de dos
decimales, positivo), mismo significado, mismo efecto en el asiento: en un recibo por honorarios
parte el asiento en gasto por el total, retención al haber y cuenta por pagar por el neto.

La cabecera del asiento que ve un driver lo renombra igual (`Cabecera.retencion_4ta`).

**La grafía es `4ta` y no `cuarta` a propósito:** la cuenta configurada ya se llama
`cuentas.retencion_4ta` en los tres drivers de salida y en la configuración publicada, con el título
«Renta de 4ta que le retienes». Con el campo escrito igual, **la avería 1 es imposible de cometer**:
lo que alguien escribía por intuición es ahora lo correcto.

### Lo que NO se renombra, y por qué

| | Qué es | Se queda |
|---|---|---|
| El **rol** `retencion` de una línea de asiento | el papel de esa línea; su bloque dice de qué tributo es, con el código del Catálogo 05 | sí: es genérico a propósito, porque lo retenido no siempre es renta de 4ta |
| La **cuenta** `cuentas.retencion_4ta` | configuración de cada contribuyente | sí: cambiar su clave rompería la configuración guardada de cada RUC, sin ganar nada |

Un campo, un rol y una cuenta pueden compartir nombre sin que vuelva el agujero —`detraccion` es las
tres cosas a la vez—, porque lo que protege no es la diferencia de nombre sino que el comprobante
**rechace lo que no es suyo**.

### Migrar

Quien manda `retencion` recibe un `ValueError` que nombra **las dos** a las que pudo referirse
(`RENOMBRADOS_EN_4_0`), en vez de «clave desconocida»: que es justo lo que no se pudo decir la
primera vez. La guía está en [`../MIGRAR-A-4.0.md`](../MIGRAR-A-4.0.md).

### Lo que esta enmienda NO mueve

Ni una celda de un Excel. De los siete snapshots congelados del motor, el renombrado cambia **uno**
—el del documento del estándar, y solo el nombre de la clave—; los cuatro de CONCAR y CONTASIS y los
dos de líneas y papeles derivados quedan byte a byte, porque un Excel no lleva dentro el nombre de un
campo. Es el criterio de salida de este cambio y lo comprueba la batería.
