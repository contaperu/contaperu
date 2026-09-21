# Migrar de `open-accounting` 0.3 a 1.0

Tres cambios en el documento y uno en la versión. Si produces documentos con el motor, no tienes que hacer nada: los
arma él. Si los escribes tú, esto es todo.

**El motor no acepta documentos que se declaren `0.3`**: se rechazan al leer el libro, con un mensaje que nombra los
tres cambios. Es una limpieza deliberada (John, 18-sep-2026) — ningún ERP de fuera los escribía todavía, así que
cargar con dos caminos en el lector no tenía a quién servir.

## 1 · La clave de versión

```diff
- "open_accounting": "0.3"
+ "open_accounting": "1.0"
```

Y si citas el esquema o los catálogos por su URL, el tag cambia:

```
https://raw.githubusercontent.com/contaperu/contaperu/open-accounting-1.0/estandar/open-accounting.schema.json
https://raw.githubusercontent.com/contaperu/contaperu/open-accounting-1.0/estandar/catalogos.json
```

## 2 · La imputación entra en el documento

Antes iba **solo** como argumento de la llamada, así que un archivo guardado no decía con qué cuentas se armó su
asiento. Ahora es un bloque de la raíz, llaveado por el `id_externo` de cada comprobante:

```diff
  {
    "open_accounting": "1.0",
    "libro": { "ruc": "20601234567", "periodo": "202601", "tipo": "compra" },
-   "comprobantes": [ { "…": "…" } ]
+   "comprobantes": [ { "…": "…", "id_externo": "compra-123" } ],
+   "imputaciones": {
+     "compra-123": { "cuenta_contable": "6343001", "centro_costo": "OBRA01" }
+   }
  }
```

**El argumento `imputacion` sigue valiendo**, así que si integrabas así no tienes que cambiar nada. Lo que no se puede
es mandar las dos formas a la vez: se rechaza, porque adivinar cuál manda sería elegir en silencio la cuenta de un
comprobante.

Dos cosas se exigen **solo cuando la imputación viene en el documento**:

- cada comprobante necesita su `id_externo` (el esquema lo pide con un condicional; sin `imputaciones` no lo pide);
- y con eso, ningún `id_externo` puede estar repetido — eso lo comprueba el motor, porque el esquema no puede decirlo.

Y una vale por las dos vías: **una llave que nombra a dos comprobantes se rechaza**, porque la misma cuenta se
aplicaría a los dos. Por el argumento se comprueban las llaves que la imputación usa; en el documento, todas. Hasta la
0.3 esto pasaba en silencio por el argumento, así que **es un cambio de comportamiento**: si mandabas dos filas con el
mismo id y las imputabas, ahora te lo dice.

El `id_externo` es **texto único libre**: un uuid es la forma recomendada, pero puedes usar el id de tu propia fila.

## 3 · Cada línea del asiento lleva su `clase`

**Solo te afecta si escribes el bloque `asiento` tú.** Es obligatoria, y son cinco valores: `activo`, `pasivo`,
`patrimonio`, `ingreso`, `gasto`.

```diff
  { "cuenta": "6343001", "debe_haber": "D", "importe": "10000.00", "rol": "principal",
+   "clase": "gasto",
    "documento": { "tipo_cp": "01", "serie_numero": "F001-123" } }
```

**Se saca del primer dígito de la cuenta**, que es el elemento del PCGE:

| Elemento | `clase` |
|---|---|
| 1 · 2 · 3 | `activo` |
| 4 | `pasivo` |
| 5 | `patrimonio` |
| 6 · 9 | `gasto` |
| 7 | `ingreso` |
| 8 · 0 | **ninguna** — el motor no genera asiento y lo dice |

**No se saca del rol**: en una compra de mercadería el rol es `principal` y la línea es un `activo`. Y el IGV
(`401111`, elemento 4) es `pasivo`: con `debe_haber: D` la línea dice que reduce un tributo por pagar, que es el
crédito fiscal.

La línea puede llevar además `documento.id_externo`, el id del comprobante que la originó, para enlazarla sin depender
de la serie y el número. Es opcional.

## 4 · `rol` y `libro.tipo` ya no son enums del esquema

Los valores no cambian —los seis roles de compras y ventas, y `venta` y `compra`—, así que **no tienes que tocar
nada**. Lo que cambia es dónde se validan: en [`catalogos.json`](catalogos.json), publicado con el tag.

Si tu código validaba contra el enum del esquema, ahora lee el catálogo. Y hay una regla nueva que te conviene
aprovechar: **si recibes un `rol` que no conoces, contabiliza la línea con `clase`, `debe_haber` e `importe`**. Así el
día que entre un rol nuevo —la percepción, el anticipo, el banco— tu integración no se rompe.

`libro.tipo` no funciona igual: un valor que no conozcas **sí** es un error, porque no hay forma de adivinar qué hacer
con un registro desconocido.

## Cómo compruebas que quedó bien

```bash
python -m contaperu.puertas.cli diagnosticar mi-mes.json
```

Y si produces documentos con tu propio código, corre la [batería de conformidad](conformidad/): los casos de esquema
se ejecutan con cualquier validador de JSON Schema draft 2020-12, sin el motor.
