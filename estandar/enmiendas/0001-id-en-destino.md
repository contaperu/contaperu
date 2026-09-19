# 0001 · `linea.id_en_destino`: el id del asiento en el sistema de destino

| | |
|---|---|
| **Estado** | reservada |
| **Compatibilidad** | aditivo |
| **Nivel** | estándar |
| **Versión** | — |
| **Test** | — |

## Motivación

Un ERP que importa el asiento le pone su propio identificador. Para que una segunda llamada sepa que
ese asiento ya está allá —y no lo duplique— el id del destino tiene que poder volver en la línea.

**Falta el caso real:** ningún sistema de destino de los que hay hoy devuelve nada. CONCAR y CONTASIS importan un
archivo y no contestan. El día que un ERP conteste con sus ids, esta enmienda pasa a `con caso real`.

## Fuente

`REFERENCIAS.md`: Merge lo llama `remote_id` y Rutter `platform_id`; las dos APIs unificadas lo declaran de
solo lectura, porque lo escribe el destino y no quien manda.

## Especificación

Campo `id_en_destino` en la línea del asiento, texto libre, opcional. Lo escribe **el destino**, nunca el
motor.

**Se llamaba `id_externo` hasta el 18-sep-2026** y se renombró antes de existir, porque la enmienda 0009 mete
`linea.documento.id_externo` —el id del sistema que **produjo** el comprobante— a un solo nivel de distancia. Dos
campos con el mismo nombre y sentidos opuestos se confunden, y renombrar uno después de publicarlo cuesta una versión
del estándar. El nombre nuevo dice de qué lado es.
