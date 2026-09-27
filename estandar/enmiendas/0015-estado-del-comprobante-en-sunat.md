# 0015 · `estado_sunat`: lo que SUNAT dice del comprobante en su registro

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 1.0 (aditivo: no sube la versión, avanza el tag) |
| **Test** | `tests/test_sire_txt.py::test_el_estado_de_sunat_se_transporta_tal_cual` |

## Motivación

Un caso real, con números. En un registro de ventas de **52 filas** ya declarado ante SUNAT, **cinco** comprobantes
venían con todos sus importes en cero —tres facturas y dos notas de crédito— y eran exactamente los cinco que SUNAT
marcaba con «Est. Comp» = `2`. Tres señales se movían juntas y el motor no veía ninguna: el estado, los trece importes
en cero y el tipo de cambio en `0.000` en vez de `1.000`. Sus correlativos caían **en medio de la serie** (116, 117,
118, 120 … 122, 123, 124), que es la firma de un comprobante dado de baja: se declara igual para que el correlativo no
quede con huecos.

Sin ese campo nadie podía distinguir un comprobante dado de baja de uno al que le falta el importe, y el motor lo
trataba como lo segundo: a las tres facturas les ponía el aviso «Importe total en cero» —que sugiere un dato por
rellenar que no existe— y a las dos notas de crédito **nada**, porque ese aviso llevaba una condición que lo callaba
en las notas. Las cinco pedían cuenta contable, que a un comprobante dado de baja no se le pone.

## Fuente

- **Campo 35 del Anexo N.° 2 de la RS 112-2021/SUNAT** (propuesta del RVIE, ventas): «Estado del comprobante de pago»,
  nemotécnico «Est. Comp». Longitud **2**, **alfanumérico**. Parte del Registro: **No**.
- **Campo 40 del Anexo 8 de la RS 040-2022/SUNAT, §8.4** (propuesta del RCE, compras): el mismo nombre y el mismo
  nemotécnico. Longitud **1**, **numérico**. Parte del Registro: **No**.

Los dos con las mismas dos reglas, literales: «**En la propuesta se muestra datos a título referencial**» y «**Este
campo no es considerado para la construcción del archivo de texto (txt), que complementa la propuesta**».

**Y ninguno de los dos anexos publica su tabla de valores.** Describen el campo —nombre, longitud, formato— y no dicen
qué significa cada código. Eso es lo que condiciona la especificación entera.

## Especificación

Campo **`estado_sunat` en el comprobante**, opcional: texto de hasta **dos caracteres**, y **sin patrón**, porque los
dos anexos le dan formatos distintos (alfanumérico de 2 en ventas, numérico de 1 en compras) y el estándar admite los
dos.

**Se transporta verbatim y NO condiciona ninguna regla.** Nada de `zfill`, nada de `upper()`, nada de traducirlo a un
booleano ni a una palabra: poner en mayúsculas un código cuyo alfabeto no se conoce ya sería decidir algo sin fuente.
Quien lo reciba lo enseña; quien decida con él se está inventando su significado.

**Es dato del sistema, no del documento** (`modelo.CAMPOS_DEL_SISTEMA`): no lo dice el papel. Ninguna factura impresa
lleva un «Est. Comp»; solo lo lleva el registro de la Administración. Y el efecto de que esté en ese tramo es el que se
quiere de una API de registro: **nadie puede dictarle a un motor que SUNAT dice algo de un comprobante**.

**No entra en la cabecera del asiento** (`tests/test_cabecera.py::DEL_PROCESO`) ni en ninguna huella: no cambia ningún
importe, ninguna cuenta ni ningún sentido. **No se escribe en el TXT del SIRE**, por la segunda regla de la norma.

## Qué decide entonces que un comprobante no lleve asiento

El **importe**, no este campo. `asiento.sin_efecto_contable` mira que el total, el IGV y la retención estén en cero y
que no haya detracción, y eso es lo que hace que un comprobante no pida cuenta ni centro, no gaste número de vóucher y
no produzca líneas de diario —configurable con `asentar_sin_efecto_contable`, apagado de fábrica—.

Dos razones, y la segunda es la que lo hace mejor y no solo más prudente:

1. «No mueve dinero» se comprueba mirando el documento; «estado 2» se apoya en una tabla que nadie publicó.
2. Atrapa más casos. Un comprobante en cero que llegue de un XML, de una foto o dictado por un ERP tampoco tiene
   asiento que armar, y no trae estado ninguno.

Y el comprobante **sigue en el registro** que se declara a SUNAT: el asiento es una cosa y el registro es otra, y el
correlativo necesita su fila. Por eso SUNAT los declara en cero en vez de quitarlos.

## El día que haya tabla de valores

Si SUNAT la publica, la traducción **no vive en este campo**, que seguirá siendo el dato tal como vino. El sitio es un
catálogo propio con su fuente, como los del medio de pago o del motivo de la nota, o el `estado` de la línea, que este
estándar ya tiene **reservado** con `anulado` entre sus valores. Queda escrito para que dentro de un año nadie lo
«arregle» traduciendo aquí.

Nota para quien lea el código de una aplicación: el `2` sí se trata como anulado en el servicio de **consulta de
validez de comprobantes** de SUNAT, que es otra tabla del mismo organismo y con la que una aplicación puede poner la
palabra. El motor no la pone, porque para el campo 35 no tiene fuente.
