# Migrar de `open-accounting` 2.0 a 3.0

**Un bloque se va y el item que queda crece.** Si produces documentos con el motor no tienes nada que hacer: los
arma él. Si los escribes tú, esto es todo — y es más corto que la lista de campos nuevos, porque **la traducción es
mecánica y nada se pierde**.

**El motor no acepta documentos que se declaren `2.0`**: se rechazan al leer el libro, con un mensaje que nombra lo
que cambia. Es la misma decisión que la 1.0 tomó con la 0.3 y la 2.0 con la 1.0 — leer dos versiones cuesta dos
caminos en el lector y una regla de cuál gana.

Y lo que lo hace asumible aquí: **el bloque que se va nació el 10-oct-2026**, en la 9.1.0. Nadie de fuera produce
documentos con él y la aplicación que integra el motor no lo consume, así que aplica la regla de John del
18-sep-2026: *«como todavía ningún ERP no lo usa, puedes hacer la limpieza para que esté bien»*.

## 1 · La clave de versión

```diff
- "open_accounting": "2.0"
+ "open_accounting": "3.0"
```

Y si citas el esquema o los catálogos por su URL, el tag cambia:

```
https://raw.githubusercontent.com/contaperu/contaperu/open-accounting-3.0/estandar/open-accounting.schema.json
https://raw.githubusercontent.com/contaperu/contaperu/open-accounting-3.0/estandar/catalogos.json
```

## 2 · `constancias[]` se va: un pago es un movimiento más

**Una sola entrada para tesorería**, igual que `comprobantes[]` es la única de una compra o de una venta. La
traducción, campo a campo:

| Lo que era de la constancia | Dónde va ahora |
|---|---|
| `numero` | **`constancia`** — y ojo, no `referencia`: ése es el número que le da **el banco**. Los dos conviven porque una detracción pagada desde un banco tiene los dos |
| `fecha` · `importe` · `moneda` | los mismos nombres |
| `cuenta_origen` | **`cuenta`**, el mismo campo con que un movimiento apunta a su cuenta del maestro |
| `concepto` | **`descripcion`** |
| `beneficiario: {tipo_doc, doc, nombre}` | **`contraparte_tipo_doc`, `contraparte_doc`, `contraparte_nombre`**, planos y con los mismos nombres que en un comprobante |
| `medio_pago` · `referencias[]` · `origen` · `confianza` · `datos_originales` | los mismos nombres |
| — | **`sentido`, que es nuevo y obligatorio**: `cargo` si el dinero sale, `abono` si entra. Una constancia no lo decía porque siempre era un pago; un movimiento sí |

```diff
  {
    "open_accounting": "3.0",
    "libro": { "ruc": "20601234567", "periodo": "202608", "tipo": "tesoreria" },
-   "constancias": [
-     { "numero": "00012345678", "fecha": "2026-08-14", "importe": "4711.00",
-       "cuenta_origen": "bbva-soles", "concepto": "Detraccion F001-123",
-       "beneficiario": { "doc": "20602222226", "nombre": "PROVEEDOR SAC" },
-       "medio_pago": "003", "origen": "pdf_texto", "confianza": "0.92",
-       "referencias": [ { "clase": "comprobante", "datos": { "tipo_cp": "01", "serie": "F001", "numero": "123" } } ] }
-   ]
+   "movimientos": [
+     { "constancia": "00012345678", "fecha": "2026-08-14", "importe": "4711.00", "sentido": "cargo",
+       "cuenta": "bbva-soles", "descripcion": "Detraccion F001-123",
+       "contraparte_doc": "20602222226", "contraparte_nombre": "PROVEEDOR SAC",
+       "medio_pago": "003", "origen": "pdf_texto", "confianza": "0.92",
+       "referencias": [ { "clase": "comprobante", "datos": { "tipo_cp": "01", "serie": "F001", "numero": "123" } } ] }
+   ]
  }
```

Y el `$def` cambia de nombre: **`referencia_de_constancia` → `referencia_de_pago`**, porque es lo que cancela un
pago venga de donde venga. Sus cuatro clases y sus claves no cambian.

**Lo que distingue ahora una línea de extracto de un pago** no es una etiqueta: es el **`saldo`**, que solo un
extracto trae, y el **`origen`**, que dice cómo se leyó. El porqué, con los tres argumentos de la 2.0 revisados, en
[la enmienda 0025](enmiendas/0025-una-sola-entrada-para-tesoreria.md).

## 3 · Tres cosas que el esquema no decía y ahora sí

Ninguna es un campo nuevo: son validaciones que vivían **solo en el motor**, así que si validabas con el JSON
publicado aceptabas cosas que el motor rechaza.

- **Las claves de cada clase de referencia.** `comprobante` lleva `tipo_cp`, `serie`, `numero` y
  `contraparte_doc`; `tributo`, `codigo` y `periodo`; `cuenta_propia`, `cuenta`; `libre`, `texto`. Y **al menos una
  con contenido**.
- **El `origen` es un enum de cinco**: `manual`, `archivo`, `api`, `pdf_texto`, `vision`. **No son los del
  comprobante** —`xml` y `sire` no son cosas de un banco—, y los dos últimos son los que marcan lectura asistida.
  Si usabas otro valor, ahora para: antes validaba y **dejaba de salir marcado para revisión en silencio**.
- **La moneda es ISO 4217** (`^$|^[A-Z]{3}$`), igual que en el comprobante. Un `"soles"` ya no vale. **Sin enum a
  propósito**: quien enumera monedas es el maestro de cuentas, y una tercera se declara primero como cuenta.

## 4 · Dos bloques nuevos, los dos opcionales

No hay que usarlos; si no vienen, todo funciona como antes.

**`extractos[]`** — la cabecera de cada hoja: `{cuenta, desde, hasta, saldo_inicial, saldo_final, total_cargos,
total_abonos}`, y solo `cuenta` es obligatoria. Con ella un documento guardado **se puede volver a comprobar** y se
comprueba el saldo final declarado, que antes era inalcanzable. Dos del mismo `id` se rechazan, y el bloque y el
argumento `saldos_iniciales` para la misma cuenta también: no hay regla que diga cuál gana.

**`imputaciones_de_movimientos`** — por `id_externo` del movimiento, la contrapartida que pone tu ERP:

```json
"imputaciones_de_movimientos": {
  "mov-881": {"cuenta_contable": "4212100", "contraparte_doc": "20602222226", "centro_costo": "OBRA01"},
  "mov-882": {"reparto": [{"importe": "3000.00", "cuenta_contable": "4212100"},
                          {"importe": "1500.00", "cuenta_contable": "6391000", "centro_costo": "ADMIN"}]},
  "mov-883": {"cuenta_propia": "bbva-dolares"}
}
```

La 104 **no** va aquí: sale de la cuenta bancaria que declaras en el maestro. Esto pone la otra cara. **Con el
bloque, cada movimiento necesita su `id_externo`**, y una llave que no sea de ninguno se rechaza. El `reparto` suma
el importe exacto, con el ITF fuera. Y `cuenta_propia` es la única vía para declarar un traspaso entre tus cuentas,
que es lo que la NIC 7 §9 excluye de los flujos.

## Lo que NO cambia

- **Los cuatro obligatorios de un movimiento**: `cuenta`, `fecha`, `importe` y `sentido`. El importe sigue siendo
  siempre positivo.
- **Los cuatro obligatorios de una línea del asiento**: `cuenta`, `debe_haber`, `importe`, `clase`.
- **Ninguna salida.** El Excel de CONCAR y el de CONTASIS quedan celda a celda idénticos, y ninguna huella cambia:
  esto no toca una línea del camino del comprobante.
- **El catálogo**: ni un valor nuevo. Las cuatro clases de referencia y los tres efectos de tesorería son los
  mismos.
- **El motor todavía no asienta un movimiento.** Lo que esta versión cierra es el **contrato**: ya se puede decir
  todo lo que el motor necesitará. Falta la tasa del ITF con su norma y un archivo del sub-diario de bancos que
  CONCAR haya aceptado (el hito D6).

## Si guardas documentos de la 2.0

El motor no los lee. La traducción es la tabla de arriba y no pierde nada; el único campo que hay que **añadir** es
el `sentido`, que para una constancia es siempre `cargo` si era un pago. Y si lo que tienes es un archivo ya
exportado —un Excel de CONCAR, un TXT del SIRE—, no hay nada que migrar: eso no es un documento del estándar.
