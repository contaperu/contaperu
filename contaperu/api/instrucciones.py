"""Lo que hay que saber antes de armar un documento, y lo que hay que saber para usar ESTE servidor.

Son dos cosas y estaban en una sola: el texto que el servidor MCP le da a un agente empezaba por el camino
de **sus** herramientas —`leer_xml_ubl`, `validar_comprobantes`, `generar_asiento`— y seguía con las reglas
del dominio. `INTEGRAR.md` le pide a todo integrador que se traiga ese texto «aunque no traigas nada más»,
y ahí estaba el problema: quien monta su propio MCP encima del motor **no tiene esas herramientas**, así
que traerlo entero le promete a su agente cosas que no puede llamar, lo que es peor que no traer nada.

Desde la 3.4.0 son dos nombres:

- **`REGLAS`**: las reglas del dominio, y **no nombran ninguna herramienta**. Esto es lo que se trae quien
  construye su propia capa de agente, y lo que le evita el error que un modelo comete con más seguridad:
  importes en negativo, la sigla de su ERP en vez del código de SUNAT, la retención del IGV confundida con
  una detracción. Lo vigila un test: si una regla nueva nace citando una herramienta, salta.
- **`INSTRUCCIONES`**: la presentación de este servidor y el camino de sus herramientas, con `REGLAS`
  dentro. Es lo que el servidor MCP del motor anuncia, y no ha cambiado ni un byte de lo que decía.

Y viven en la capa `api` y no en `puertas` porque el único nombre que la guía manda importar **no puede
estar en una puerta**: la api no puede importar `puertas` (las capas lo prohíben), así que un integrador
que solo use la librería estaba obligado a importar un servidor entero para leer un texto. Desde aquí,
`contaperu.api.REGLAS` existe, y `from contaperu.puertas.servidor_mcp import INSTRUCCIONES` sigue valiendo.
"""
from __future__ import annotations

PRESENTACION = """\
Núcleo contable del Perú. Convierte comprobantes de SUNAT en asientos y en los archivos que
importan los sistemas contables peruanos. Todo es determinista y sin estado.
"""

CAMINO = """\
El camino normal:
  1. `leer_xml_ubl` o `leer_propuesta_sire` si tienes archivos de SUNAT; si ya tienes los datos
     estructurados, arma tú el documento `open-accounting` (mira el recurso del esquema).
  2. `validar_comprobantes` para ver qué observaciones hay antes de nada.
  3. `generar_asiento` para las líneas de diario, o `exportar` directamente al formato del ERP.
  4. `resumen` para saber cuánto es el libro, y `por_cuenta` para ver en qué cuentas cayó.

Y dos que se leen en vez de llamarse: el recurso de la configuración dice qué se configura de cada
sistema, y el de los campos del comprobante, cuáles los pone el documento y cuáles el sistema.
"""

REGLAS = """\
Reglas que conviene tener claras antes de armar un documento:
  - Los importes van SIEMPRE en positivo. Una nota de crédito se marca con su tipo —`07`, o `87`
    si es de no domiciliado—, nunca con importes negativos: quien resta es la contabilidad.
  - `tipo_cp` es el código de la Tabla 10 de SUNAT, no la sigla del sistema contable.
  - La `retencion` de un comprobante es la de renta de 4ta de un recibo por honorarios. La
    retención del IGV del 3 % NO es una detracción y no entra en el asiento.
  - Cada contribuyente tiene su plan de cuentas y sus sub-diarios: van en `configuracion`, con lo
    general en la raíz y lo de cada sistema contable en su sección (`concar`, `csv`, `contasis`).
    Lo que se configura lo declara cada sistema; ningún valor por defecto es la verdad de nadie.
  - La cuenta, el centro de costo, la cuenta del total y el reparto de CADA comprobante los decide
    quien revisa, y no van en el documento: llegan aparte, en `imputacion`, por el `id_externo` del
    comprobante — {"fila-8": {"cuenta_contable": "636301", "centro_costo": "OBRA01"}}. Lo que no
    traiga sale de la `configuracion`.
  - Lo ya anotado en otros periodos del mismo RUC llega en `claves_previas`, cada uno como
    [tipo_cp, serie, numero, contraparte_doc]: un comprobante que coincide sale con
    DUPLICADO_PERIODO_ANTERIOR, porque SUNAT lo rechazaría. En ventas el cliente no cuenta.
  - Una cuenta contable no se inventa: se contrasta con el Plan Contable General. Que una cuenta no
    esté en el PCGE no la invalida —las divisionarias las abre cada empresa—, pero conviene saberlo.
  - El estado de un comprobante, su origen, si está apartado y lo que se le observó **no los dice el
    papel**: los pone el sistema que lo recibe, y ponerlos tú es decidir por él.

Si algo no se puede hacer bien, la operación falla y dice por qué. No se inventa una cuenta,
ni un tipo de documento, ni una equivalencia del PCGE.
"""

INSTRUCCIONES = f"{PRESENTACION}\n{CAMINO}\n{REGLAS}"
