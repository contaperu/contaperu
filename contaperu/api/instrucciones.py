"""Lo que hay que saber antes de armar un documento, y lo que hay que saber para usar ESTE servidor.

Son dos cosas y estaban en una sola: el texto que el servidor MCP le da a un agente empezaba por el camino
de **sus** herramientas —`leer_xml_ubl`, `validar_comprobantes`, `generar_asiento`— y seguía con las reglas
del dominio. Quien monta su propio MCP encima del motor **no tiene esas herramientas**, así que traerse el
texto entero le promete a su agente cosas que no puede llamar, lo que es peor que no traer nada.

Desde la 3.4.0 son dos nombres:

- **`REGLAS`**: las reglas del dominio, y **no nombran ninguna herramienta**. Esto es lo que se trae quien
  construye su propia capa de agente, y lo que le evita el error que un modelo comete con más seguridad:
  importes en negativo, la sigla de su ERP en vez del código de SUNAT, la retención del IGV confundida con
  una detracción. Lo vigila un test: si una regla nueva nace citando una herramienta, salta.
- **`INSTRUCCIONES`**: la presentación de este servidor, las reglas y el camino de sus herramientas. Es lo
  que el servidor MCP del motor anuncia.

**Y desde la 15.15.0 las reglas tienen nombre y ámbito**: `REGLAS_POR_CLAVE`, con dos ámbitos.

- **`documento`**: lo que vale para cualquiera que arme un documento `open-accounting`, llame como llame al
  motor —los importes en positivo, la Tabla 10, las dos retenciones, la detracción, el no domiciliado, el plan
  de cuentas propio, la cuenta que no se inventa y lo que no dice el papel—. No nombran nada de la llamada.
- **`llamada`**: lo que solo vale para quien llama a estas operaciones con sus argumentos —`configuracion`,
  `imputacion`, `claves_previas`— y lo que hace la operación cuando no puede.

Hacía falta porque `REGLAS` era un solo texto y quien tiene otra forma de llamar no podía traérsela entera: un
conector que no tiene `imputacion` ni `claves_previas` le estaría hablando a su modelo de dos argumentos que no
existen. Ahora se trae las del documento por su clave, y `REGLAS` sigue siendo la unión, en el mismo orden.

**Las reglas van ANTES del camino desde la 15.15.0, y caben en 2 048 caracteres**, porque Claude Code solo lee
los primeros 2 048 de las instrucciones de un servidor (medido el 21-nov-2026). Hasta entonces el texto medía
3 832 y las reglas empezaban en el 831: la del no domiciliado y las cinco siguientes no le llegaban a un
desarrollador que conectara este servidor a su Claude Code. Lo vigila `RECORTE_DEL_CLIENTE` en
`tests/test_servidor_mcp.py`, y es un trinquete: una regla nueva paga su sitio acortando otra.

Y viven en la capa `api` y no en `puertas` porque el único nombre que la guía manda importar **no puede
estar en una puerta**: la api no puede importar `puertas` (las capas lo prohíben), así que un integrador
que solo use la librería estaba obligado a importar un servidor entero para leer un texto. Desde aquí,
`contaperu.api.REGLAS` existe, y `from contaperu.puertas.servidor_mcp import INSTRUCCIONES` sigue valiendo.
"""
from __future__ import annotations

from ..drivers import DE_SERIE, contrato

PRESENTACION = """\
Núcleo contable del Perú: de comprobantes de SUNAT a asientos y archivos contables, determinista y sin estado.
"""

CAMINO = """\
El camino normal:
  1. `leer_xml_ubl` o `leer_propuesta_sire` si tienes archivos de SUNAT; si ya tienes los datos
     estructurados, arma tú el documento `open-accounting` (mira el recurso del esquema).
  2. `validar_comprobantes` para ver qué observaciones hay antes de nada.
  3. `generar_asiento` para las líneas de diario, o `exportar` directamente al formato del ERP.
  4. `resumen` para saber cuánto es el libro, y `por_cuenta` para ver en qué cuentas cayó.

Y tres que se leen en vez de llamarse: el recurso de la configuración dice qué se configura de cada
sistema; el de los campos del comprobante, cuáles los pone el documento y cuáles el sistema; y el de los
catálogos de SUNAT trae los códigos del bloque `no_domiciliado` y el convenio de cada país.
"""

ENCABEZADO = "Reglas que conviene tener claras antes de armar un documento:\n"

# Los sistemas que tienen sección propia en la configuración, derivados del contrato de cada driver de serie: la
# lista estaba escrita a mano —`concar`, `csv`, `contasis`— y se quedó tres drivers por detrás. Los de serie y no
# `drivers.DRIVERS`, que buscaría los de terceros al importar la api (eso se paga al arrancar una puerta, no aquí),
# y así las reglas dicen lo mismo en toda instalación. `tests/test_servidor_mcp.py` las compara con
# `describir_configuracion`, que es lo que la configuración valida de verdad.
SISTEMAS_CON_SECCION = tuple(nombre for nombre, modulo in DE_SERIE.items() if contrato.seccion_por_defecto(modulo))

REGLAS_POR_CLAVE: dict[str, dict[str, str]] = {
    "documento": {
        "importes_en_positivo": (
            "Los importes van SIEMPRE en positivo: una nota de crédito se marca con su tipo (`07`, `87` o `97`), "
            "nunca en negativo."),
        "tabla_10": "`tipo_cp` es el código de la Tabla 10 de SUNAT, no la sigla del sistema contable.",
        "dos_retenciones": (
            "Hay DOS retenciones: `retencion_4ta`, la renta de 4ta (8 %) de un recibo por "
            "honorarios, la única que entra en el asiento, y `retencion_igv`, el 3 % que un agente de retención le retiene a "
            "una factura. La del IGV NO es una detracción."),
        "detraccion": (
            "La detracción va por su `codigo` del Catálogo 54, contrastado con la tabla del contribuyente; no se "
            "deduce del porcentaje del PDF, que varios códigos comparten."),
        "no_domiciliado": (
            "La factura de un proveedor del EXTERIOR (documento tipo `0`) es un `91`, con notas `97` y `98`, en "
            "compras y con lo comprado en `valor_no_gravado`, sin IGV; su renta retenida va en el bloque "
            "`no_domiciliado`, no en `retencion_4ta`, y en SOLES aunque sea en dólares."),
        "plan_de_cuentas": (
            "Cada contribuyente tiene su plan de cuentas y sus sub-diarios; ningún valor por defecto es la verdad de "
            "nadie."),
        "cuenta_no_se_inventa": (
            "Una cuenta contable no se inventa: se contrasta con el PCGE, aunque no estar en él no la invalida (las "
            "divisionarias son de cada empresa)."),
        "lo_que_pone_el_sistema": (
            "El estado, el origen, si está apartado y lo observado no los dice el papel: los pone el sistema que "
            "lo recibe."),
    },
    "llamada": {
        "configuracion": (
            "El plan y los sub-diarios van en `configuracion`: lo general en la raíz y cada sistema en su sección "
            f"({', '.join(f'`{nombre}`' for nombre in SISTEMAS_CON_SECCION)})."),
        "imputacion": (
            "La cuenta, el centro de costo, la cuenta del total y el reparto de cada comprobante van en `imputacion`, "
            "por su `id_externo`, y no en el documento; lo que falte sale de la `configuracion`."),
        "claves_previas": (
            "Lo anotado en otros periodos del RUC va en `claves_previas` ([tipo_cp, serie, numero, "
            "contraparte_doc]): lo que coincida sale DUPLICADO_PERIODO_ANTERIOR; en ventas no cuenta el cliente."),
        "falla_y_dice_por_que": "Lo que no se puede hacer bien falla y dice por qué: nada se inventa.",
    },
}

# La unión, en el orden de arriba: primero las del documento, que son las de todos.
REGLAS = ENCABEZADO + "".join(f"- {texto}\n" for reglas in REGLAS_POR_CLAVE.values() for texto in reglas.values())

INSTRUCCIONES = f"{PRESENTACION}\n{REGLAS}\n{CAMINO}"
