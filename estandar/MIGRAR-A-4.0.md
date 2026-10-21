# Migrar a `open-accounting` 4.0

**Un solo cambio, y es un renombrado:** el campo `retencion` del comprobante pasa a llamarse
**`retencion_4ta`**, y nace **`retencion_igv`** para la otra retención que el Perú tiene y que hasta
ahora no cabía en ninguna parte.

Si tu documento no trae `retencion`, **no tienes nada que hacer**: solo subir el número.

## Qué cambia

| 3.3 | 4.0 |
|---|---|
| `comprobante.retencion` | `comprobante.retencion_4ta` |
| — | `comprobante.retencion_igv`: `{porcentaje, monto}`, opcional |
| `"open_accounting": "3.3"` | `"open_accounting": "4.0"` |

```diff
  {
    "tipo_cp": "02", "serie": "E001", "numero": "45",
    "inafecto": "2000.00", "total": "2000.00",
-   "retencion": "160.00"
+   "retencion_4ta": "160.00"
  }
```

Y lo que antes no se podía decir:

```diff
  {
    "tipo_cp": "01", "serie": "F002", "numero": "9969",
    "base_gravada": "630.00", "igv": "113.40", "total": "743.40",
+   "retencion_igv": { "porcentaje": "3.00", "monto": "22.30" }
  }
```

**No las confundas, y por eso se separan:** `retencion_4ta` es la renta de 4ta del 8 % que muestra un
recibo por honorarios, y `retencion_igv` es el 3 % del Régimen de Retenciones del IGV que el comprador
agente de retención le retiene al proveedor de una factura. Son dos tributos distintos con el mismo
nombre en castellano.

## Por qué, si un renombrado cuesta una mayor

Porque el nombre genérico ya costó dos averías, y las dos están documentadas:

1. Alguien escribió `retencion_4ta` —el nombre específico, el que parece natural— donde el campo se
   llamaba `retencion`. El lector lo filtraba en silencio y **el mes se exportó sin su línea de
   retención**: solo se veía leyendo las celdas del Excel.
2. Una aplicación volcó en ese campo el 3 % del IGV de una factura, porque no había dónde ponerlo.
   El motor lo cazó con `RETENCION_NO_APLICA` y dos facturas acabaron observadas.

Con el campo escrito `retencion_4ta` —igual que la cuenta configurada, que ya se llamaba así—, la
primera avería es imposible de cometer: lo que alguien escribía por intuición es ahora lo correcto.

La decisión entera está en [la enmienda 0034](enmiendas/0034-un-nombre-por-retencion.md), y el campo
nuevo en [la 0005](enmiendas/0005-retencion-de-igv.md).

## Si mandas el nombre viejo, el motor te lo dice

No falla con «clave desconocida»: nombra **las dos** a las que pudiste referirte, que es justo lo que
no se pudo decir la primera vez.

```
retencion se renombró en open-accounting 4.0: la de renta de 4ta de un recibo por honorarios es
`retencion_4ta`, y la del régimen de retenciones del IGV de una factura es `retencion_igv`
({porcentaje, monto}). Son dos tributos distintos
```

## Lo que NO cambia

- **Ni una celda de ningún Excel.** Los snapshots de CONCAR y de CONTASIS quedan byte a byte: un
  archivo de salida no lleva dentro el nombre de un campo. Es el criterio de salida de esta versión.
- **El asiento de un recibo por honorarios**, que sigue partiéndose igual: gasto por el total,
  retención al haber en su cuenta de tributos y al profesional el neto.
- **El rol `retencion` de una línea de asiento**, que es genérico a propósito: lo retenido no siempre
  es renta de 4ta, y su bloque dice de qué tributo se trata con el código del Catálogo 05.
- **La cuenta configurada `cuentas.retencion_4ta`**, que ya se llamaba así. Cambiar su clave rompería
  la configuración guardada de cada contribuyente sin ganar nada.
- **`retencion_igv` no entra en ningún asiento**, ni de compras, ni de ventas, ni en el neutral: no
  es un hecho del comprobante sino del pago. Sí llega a la cabecera que ve un driver, para que el
  dato no se pierda por el camino — hoy ninguno lo usa.

## Y si vienes de más atrás

Hay que pasar por cada salto: [`MIGRAR-A-1.0.md`](MIGRAR-A-1.0.md),
[`MIGRAR-A-2.0.md`](MIGRAR-A-2.0.md) y [`MIGRAR-A-3.0.md`](MIGRAR-A-3.0.md).
