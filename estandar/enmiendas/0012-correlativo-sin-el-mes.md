# 0012 · `correlativo` sin el mes, y el mes en su propio campo

| | |
|---|---|
| **Estado** | borrador |
| **Compatibilidad** | cambio de significado |
| **Nivel** | estándar |
| **Versión** | — |
| **Test** | — |

## Motivación

Hoy `linea.correlativo` lleva **dos datos pegados**: el mes y el número del asiento dentro de su sub-diario.
Para el periodo `202507`, el cuarto asiento del registro de ventas es `"070004"`.

Lo confiesa el propio esquema, que describe el campo como «Número del asiento dentro del sub-diario **y el
mes**» (`open-accounting.schema.json`). Un campo cuya descripción lleva un «y» suele ser dos campos.

**La prueba de que están pegados es que todo el mundo los despega.** Los dos drivers de asientos que existen
hacen aritmética de cadenas sobre el valor, y cada uno en una dirección:

| Dónde | Qué hace |
|---|---|
| `drivers/starsoft/proyeccion.py` (`voucher`) | `correlativo[2:]` — le quita el mes, porque STARSOFT numera `0001` |
| `drivers/concar/xlsx.py` (`_numero`) | `int(correlativo[2:])` — le quita el mes para comparar contra 9999 |
| `drivers/concar/xlsx.py` (`_sub_diarios`) | `correlativo[:2]` para guardar el mes y **volver a concatenarlo** |

Es decir: el núcleo pega dos datos, y después tres sitios los separan —uno de ellos solo para recomponerlos—.
Un campo que se parte con un `[2:]` en cada consumidor no está bien modelado.

**Con el cambio, cada destino toma lo que necesita y nadie corta cadenas:**

```
STARSOFT   VOUCHER  = correlativo                 ->  0004
CONCAR     columna C = mes + correlativo          ->  070004
un ERP     el número del asiento, sin adornos     ->  0004
```

**Propuesto por John el 21-sep-2026**, al revisar el JSON de una venta con los dos drivers delante.

**Qué falta para pasar a `con caso real`:** un sistema de destino que pida el mes por separado, o uno que
numere de otra forma —continuo por año, o por serie— y al que `MMNNNN` le quede estrecho. Hoy los dos sistemas
que hay caben en el formato actual a costa de cortarlo, que es una molestia, no un impedimento. Eso es lo que
separa esta enmienda de una que haya que hacer ya.

## Fuente

- **La plantilla oficial de CONCAR**, que describe su columna C: «Los dos primeros dígitos son el mes y los
  otros 4 siguientes un correlativo» (`drivers/concar/datos.py`, cabeceras verificadas contra
  `plantilla-concar.xlsx`). El formato `MMNNNN` es **de CONCAR**, no de la contabilidad.
- **El vídeo de compras de STARSOFT** (6:15): «el correlativo de comprobantes o vouchers debe iniciar siempre
  en el número uno». Sin mes.
- **El propio código del motor**, citado arriba: tres recortes en dos drivers.

## Especificación

Dos formas de hacerlo, con distinta compatibilidad. La decisión es cuál.

**A · Aditiva — añadir `mes` y no tocar `correlativo`.** Entra como campo opcional, que según el estándar
«no cambia la versión»: un consumidor que no lo conozca lo ignora. El precio es que el mes queda escrito dos
veces, y los drivers seguirían cortando igual, así que **no resuelve el problema**: solo lo documenta.

**B · La propuesta — `correlativo` pasa a ser solo el número.**

```json
{"correlativo": "0004", "mes": "07"}
```

- `correlativo`: texto, opcional, el número del asiento dentro de su sub-diario, con ceros a la izquierda
  hasta el ancho que use el sistema (hoy 4). Sin el mes.
- `mes`: texto, opcional, `MM`. Redundante con `libro.periodo` **a propósito**: la línea del asiento tiene que
  poder viajar sola, y hoy ya lo hace.

Quien recomponga `MMNNNN` lo hace concatenando, que es lo que ya hace CONCAR en su resumen.

**Es un cambio de significado, no aditivo**, y por eso no puede entrar sin más: el estándar promete que «un
valor publicado no se quita ni cambia de significado». Un consumidor que hoy lea `correlativo` esperando
`070004` recibiría `0004` y lo daría por bueno sin enterarse. Las opciones son una `open-accounting` **2.0**,
o un campo nuevo con otro nombre y `correlativo` marcado como heredado.

**Lo que NO cambia en ningún caso:**

- **Las huellas.** El `correlativo` está fuera de la huella del asiento a propósito (`../LEEME.md`), así que
  ninguna huella publicada se mueve. Es lo que hace este cambio barato de probar.
- **El archivo de CONCAR.** Su columna C sigue llevando `070004`: el driver concatena al proyectar, como hoy
  recorta. Lo que cambia es dónde vive la costura.
- **La numeración.** Sigue arrancando en 1 por sub-diario y por mes (`asiento.numerar_en_orden`).
