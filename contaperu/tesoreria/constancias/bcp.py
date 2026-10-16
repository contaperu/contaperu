"""Los tres formatos del BCP, que son tres papeles distintos y no tres variantes del mismo.

| Formato | Lo que el banco llama | Lo que trae de propio |
|---|---|---|
| `bcp_terceros` | «Transferencia a cuentas de terceros BCP local» | las dos cuentas y el titular del destino; **ningún documento del beneficiario** |
| `bcp_cce` | «Transferencia a otros bancos locales» | el **RUC** y el CCI, la **comisión CCE aparte** del monto, e «ITF: Afecta» |
| `bcp_documentos` | «Pago de letras y facturas» (Telecrédito) | **la tabla de documentos**: proveedor, nº de doc, nº único, vencimiento e importe, uno por fila |

El tercero es el que destraba lo que se pedía —seleccionar comprobantes y pasarlos a pago—: es el banco mismo
declarando qué documentos cancela el cargo, o sea las `aplicaciones` sin que nadie las teclee. Por eso sus filas
salen como `referencias` del movimiento, cada una con **su** importe.

## Dos reglas que no se deducen del papel sino de los papeles

Las dos salieron de medir los 38 archivos reales del BCP, no de suponer:

1. **La primera cuenta del texto es la de cargo.** En los 38 la primera `ddd-ddddddd-d-dd` es una de las dos
   cuentas del contribuyente; nunca la del beneficiario. Hacía falta una regla porque el texto llega con las
   etiquetas y los valores desordenados —la tabla del PDF se deshace al pasarla a texto— y «la que sigue a
   *Datos de la cuenta de origen*» no existe como línea.
2. **El titular del destino es la línea anterior a su cuenta.** En los 23 que traen dos cuentas, sin excepción.
   En los 6 que traen una sola, el beneficiario no está en el texto y el nombre sale vacío: no se inventa.

## Lo que estos papeles NO dicen, y por eso el lector no lo pone

- **El ITF**, que el CCE declara como «Afecta» y no cuantifica. Se asienta con el importe que da el banco y nunca
  con una tasa (John, 13-oct-2026), así que ese movimiento llega después, por el extracto.
- **El tipo y la serie del comprobante.** La tabla de documentos da «546», que es el número con el que el banco
  conoce el papel, no la terna `tipo_cp · serie · numero` que identifica un comprobante en el estándar. Una
  referencia de clase `comprobante` necesita las cuatro claves, así que inventarlas sería inventar una sigla —lo
  que el repositorio no hace en ningún sitio—. Salen como `libre`, con el texto completo del renglón, y es el ERP
  o la conciliación (D3) quien las convierte en `comprobante` cuando tenga con qué.

Los archivos que fundaron el lector son constancias reales de un contribuyente peruano de 2026. **No entran al
repositorio**: viven en `privado/`, que `.gitignore` bloquea, y lo que entra son los fixtures anonimizados de
`tests/fixtures/constancias/`, con la estructura y los importes de los reales y con los RUC y los nombres de la
batería.
"""
from __future__ import annotations

import re

from ..movimientos import CARGO, PDF_TEXTO, Movimiento
from ..referencias import LIBRE, Referencia
from .comun import (ConstanciaIlegible, cuadrar_tres, cuenta_declarada, fecha_de, importe, importes,
                    junto_a, linea_con, moneda)

#: Una cuenta del BCP como la escribe el BCP. La primera del texto es la de cargo (ver la docstring).
CUENTA = re.compile(r"\d{3}-\d{7}-\d-\d{2}")

#: Un renglón de la tabla de «Pago de letras y facturas», leído **de derecha a izquierda**: el final tiene forma
#: fija —una fecha y tres importes— y el principio es un nombre con espacios, así que anclar por el final es lo
#: que permite que el proveedor se llame como quiera.
FILA_DE_DOCUMENTO = re.compile(
    r"^(?P<proveedor>\S.*?)\s+(?P<doc>\S+)\s+(?P<unico>\S+)\s+(?P<vence>\d{1,2}/\d{1,2}/\d{2,4})\s+"
    r"(?P<importes>(?:(?:S/\.?|US\$|\$)\s*-?[\d,]+\.\d{2}\s*){3})\s*$",
    re.MULTILINE)


def _titular_del_destino(texto: str) -> str:
    """El nombre del beneficiario: la línea de encima de la segunda cuenta. Vacío si no hay segunda cuenta."""
    lineas = texto.splitlines()
    vistas = 0
    for i, linea in enumerate(lineas):
        if CUENTA.search(linea):
            vistas += 1
            if vistas == 2:
                return lineas[i - 1].strip() if i else ""
    return ""


def _comun(texto: str, tipo: str, cuentas, sena: str) -> dict:
    """Lo que los tres comparten: el número de operación, la fecha, la cuenta de cargo y el sentido."""
    operacion = junto_a(texto, "Número de operación", r"\d+")
    if not operacion:
        raise ConstanciaIlegible(f"{tipo}: no trae número de operación")
    del_papel = CUENTA.findall(texto)
    if not del_papel:
        raise ConstanciaIlegible(f"{tipo}: no trae ninguna cuenta")
    return {"referencia": operacion,
            "cuenta": cuenta_declarada(del_papel[0], cuentas),
            "fecha": fecha_de(texto, "Fecha de proceso"),
            "constancia": junto_a(texto, "Código de solicitud", r"\d+"),
            "sentido": CARGO,
            "origen": PDF_TEXTO,
            "datos_originales": {"formato": tipo, "cuenta_cargo": del_papel[0],
                                 # «Pago de letras y facturas» va al lado de su etiqueta; los otros dos tipos
                                 # salen en un renglón suelto, con la etiqueta en el de arriba.
                                 "tipo_operacion": (junto_a(texto, "Tipo de operación", r"[^\n]+")
                                                    or linea_con(texto, sena))}}


def _lo_que_cobra_el_banco(campos: dict, cuanto, divisa: str, como_se_llama: str, concepto: str) -> Movimiento:
    """La comisión como su propio movimiento (enmienda 0028), y **sin la referencia del pago**.

    Esto último lo enseñó armar el asiento de los papeles reales, no leerlos: `Movimiento.clave` es
    `(cuenta, referencia)` cuando hay referencia, porque «la del banco basta y sobra: es suya y no se repite
    dentro de una cuenta». Darle al cobro el número de operación del pago los hacía **el mismo movimiento**, y el
    motor descartaba el segundo como repetido — con razón: la clave decía que lo era.

    Y no se inventa un número derivado (`…-COM`): el banco no le dio ninguno a este cobro, y fabricar una
    referencia bancaria es de la misma familia que inventar una sigla. Sin referencia, la clave se cae a lo que
    siempre hay —cuenta, fecha, sentido, importe y descripción—, que es justamente el caso para el que ese
    camino existe. El número de la operación de la que salió se queda en `datos_originales`."""
    suyos = {**campos["datos_originales"], "concepto": concepto, "operacion": campos["referencia"]}
    return Movimiento(importe=cuanto, moneda=divisa, descripcion=como_se_llama,
                      **{**campos, "referencia": "", "datos_originales": suyos})


def _orden_interna(texto: str) -> list:
    """La orden de pago de la empresa (`Referencia OP 14292`), que es la llave con la que ella une el pago a lo
    que paga. No es un documento tributario y no tiene clase propia: viaja en `libre`, que existe para esto."""
    orden = junto_a(texto, "Referencia", r"OP\s*\d+")
    return [Referencia(clase=LIBRE, datos={"texto": re.sub(r"\s+", " ", orden)})] if orden else []


def terceros(texto: str, cuentas=()) -> list[Movimiento]:
    """«Transferencia a cuentas de terceros BCP local»: un solo cargo, sin comisión y sin documento del destino."""
    campos = _comun(texto, "bcp_terceros", cuentas, "Transferencia a cuentas de terceros")
    campos["datos_originales"]["cuenta_destino"] = (CUENTA.findall(texto) + ["", ""])[1]
    return [Movimiento(importe=importe(texto, "Monto"), moneda=moneda(junto_a(texto, "Monto", r"[^\n]+")),
                       descripcion=campos["datos_originales"]["tipo_operacion"] or "Transferencia a terceros BCP",
                       contraparte_nombre=_titular_del_destino(texto),
                       referencias=_orden_interna(texto), **campos)]


def cce(texto: str, cuentas=()) -> list[Movimiento]:
    """«Transferencia a otros bancos locales»: el cargo y **su comisión como movimiento propio** (enmienda 0028).

    Los tres importes —transferido, comisión y total— salen del texto en un orden que no es el de sus etiquetas,
    así que se identifican por aritmética y no por posición: `cuadrar_tres`. Que cuadren es la prueba de la
    lectura; si no cuadran, no sale nada."""
    campos = _comun(texto, "bcp_cce", cuentas, "Transferencia a otros bancos locales")
    bloque = texto[texto.find("Datos de la transferencia"):texto.find("Datos del beneficiario")]
    transferido, comision = cuadrar_tres(importes(bloque), "bcp_cce")
    divisa = moneda(bloque)

    # El titular se busca **dentro del bloque del beneficiario** y no en todo el texto: el papel trae dos
    # «Titular», y el de arriba es el del contribuyente. Con el texto desordenado, el de origen sale como una
    # etiqueta suelta —`Titular` seguida de `Cuenta`—, así que preguntar por el primero devolvía «Cuenta».
    del_beneficiario = texto[texto.find("Datos del beneficiario"):]
    campos["datos_originales"].update({"cci_destino": junto_a(del_beneficiario, "CCI", r"[\d\-]+"),
                                       "banco_destino": junto_a(del_beneficiario, "Banco", r"[^\n]+"),
                                       "itf": junto_a(del_beneficiario, "ITF", r"\w+")})
    pago = Movimiento(importe=transferido, moneda=divisa,
                      descripcion=campos["datos_originales"]["tipo_operacion"] or "Transferencia interbancaria",
                      contraparte_doc=junto_a(del_beneficiario, "RUC", r"\d{11}"), contraparte_tipo_doc="6",
                      contraparte_nombre=junto_a(del_beneficiario, "Titular", r"[^\n]+"),
                      referencias=_orden_interna(texto), **campos)
    if not comision:
        return [pago]
    return [pago, _lo_que_cobra_el_banco(campos, comision, divisa, "Comisión CCE", "comision_cce")]


def documentos(texto: str, cuentas=()) -> list[Movimiento]:
    """«Pago de letras y facturas»: un cargo cuyas referencias **las declara el banco**, una por documento.

    Es el único de los cinco formatos que dice qué cancela el pago, y por eso es el que convierte una constancia
    en `aplicaciones` sin que nadie teclee nada.

    **El importe del cargo es la suma de la columna TOTAL**, que es lo que se paga por cada documento: su monto
    más su interés. El `Monto` que la constancia pone arriba no sirve para eso, y lo enseñaron los dos únicos
    papeles de los siete que traen interés, que no lo declaran igual:

    | Documento | MONTO | INTERÉS | TOTAL | el `Monto` de arriba dice |
    |---|---|---|---|---|
    | una **letra** (2B LATAM) | 33 045,00 | 143,68 | 33 188,68 | **33 188,68** — con el interés |
    | una **factura** (INGENIEROS) | 76 167,55 | 89,25 | 76 256,80 | **76 167,55** — sin el interés |

    Con un papel de cada clase **no hay regla que escribir**: podría ser letra contra factura y podría ser otra
    cosa. Así que el lector no la inventa — usa los TOTAL, que no son ambiguos, y comprueba que el `Monto`
    declarado coincida **con una de las dos sumas**. Eso basta para lo que el cuadre tiene que probar, que es que
    la tabla se leyó entera y no se perdió una fila al cortar la página; si no coincide con ninguna, no sale nada.

    El interés **no** sale como movimiento aparte. La enmienda 0028 manda eso para lo que cobra el banco; esto lo
    cobra el proveedor por pagarle tarde, así que es parte de lo que se le paga y va en el importe de su fila."""
    campos = _comun(texto, "bcp_documentos", cuentas, "Pago de letras y facturas")
    declarado = importe(texto, "Monto")
    divisa = moneda(junto_a(texto, "Monto", r"[^\n]+"))

    filas, suma_de_montos, cargado = [], None, None
    for fila in FILA_DE_DOCUMENTO.finditer(texto):
        monto, _interes, de_la_fila = importes(fila.group("importes"))
        texto_de_la_fila = (f"{fila.group('proveedor').strip()} · doc {fila.group('doc')} · "
                            f"único {fila.group('unico')} · vence {fila.group('vence')}")
        filas.append(Referencia(clase=LIBRE, importe=de_la_fila, datos={"texto": texto_de_la_fila}))
        suma_de_montos = monto if suma_de_montos is None else suma_de_montos + monto
        cargado = de_la_fila if cargado is None else cargado + de_la_fila
    if not filas:
        raise ConstanciaIlegible("bcp_documentos: no se pudo leer ninguna fila de la tabla de documentos")
    if declarado not in (suma_de_montos, cargado):
        raise ConstanciaIlegible(f"bcp_documentos: la operación declara {declarado} y las {len(filas)} filas "
                                 f"suman {suma_de_montos} sin interés y {cargado} con él; falta alguna fila")

    campos["datos_originales"].update({"documentos": junto_a(texto, "Documentos Total", r"\d+"),
                                       "monto_declarado": str(declarado)})
    unico = filas[0].datos["texto"].split(" · ")[0] if len(filas) == 1 else ""
    return [Movimiento(importe=cargado, moneda=divisa, descripcion="Pago de letras y facturas",
                       contraparte_nombre=unico, referencias=_orden_interna(texto) + filas, **campos)]
