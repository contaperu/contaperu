"""Los dos formatos del BBVA: la operación suelta y la planilla.

| Formato | Lo que el banco llama | Lo que trae de propio |
|---|---|---|
| `bbva_operacion` | «Su operación ha sido realizada» (Consulta de Operaciones) | la cuenta del beneficiario con su nombre, y el documento con **letra** en vez de código |
| `bbva_masivos` | «Consulta de la Orden» (Pagos Masivos) | **un cargo con N abonos**, y sus dos comisiones declaradas aparte |

La planilla es el caso que obliga a que un lector de constancias devuelva **una lista** y no un movimiento: de un
solo papel salen el cargo por los abonos y, cuando no son cero, una comisión por otra plaza y una interbancaria,
que son tres movimientos de la misma cuenta. La enmienda 0028 ya decía que un cargo del banco es su propio
movimiento; aquí el banco lo escribe en tres renglones y confirma que así es como llega.

## El cuadre, que aquí lo pone el propio papel

`TOTAL CARGADO` tiene que ser el importe de los abonos más las dos comisiones. Está en los cuatro archivos reales
y es aritmética, así que el lector lo exige: si no cuadra, no sale nada. Y cuando la tabla de abonos sí viene,
sus importes tienen que sumar el importe cargado por abonos — **que en tres de los cuatro no viene**, porque la
tabla está detrás de un «Ver contenido de la planilla» que no se despliega al pasar el PDF a texto. Por eso las
filas de abono son opcionales y su ausencia no es un error: lo que el papel no dice, el lector no lo pone.

## La letra del documento, que se traduce con fuente a los dos lados

El BBVA identifica al beneficiario con una letra —`L - 41074220`— y declara la tabla **en el propio PDF**:
`R` RUC, `L` DNI, `P` pasaporte, `E` carné de extranjería, `M` identidad militar. Del otro lado está la Tabla 1
del Anexo 1 de la RS 112-2021, que es la que el motor ya usa en el comprobante. La identidad militar no existe
en la tabla de SUNAT, así que sale como `0` (Otros): es lo que hay, y es mejor que inventar un código.

## Y el banco del beneficiario, que no se parte a ojo

La fila de abono escribe el banco y el titular pegados —`INTERBANK JOEL YUPANQUI HURTADO`— sin nada que los
separe. No se adivina dónde acaba uno: **el propio documento trae al pie la lista de las 25 entidades** con las
que el BBVA opera, y es con ésa con la que se recorta. Si el pie no viene en el texto, los dos nombres se quedan
juntos y se dice en `datos_originales`; `tesoreria.banco_del_cci` no sirve para esto, porque devuelve el código
de tres dígitos y no el nombre —el repositorio no traduce ese código, que no tiene catálogo con fuente—.
"""
from __future__ import annotations

import re

from ..movimientos import CARGO, PDF_TEXTO, Movimiento
from ..referencias import LIBRE, Referencia
from .comun import ConstanciaIlegible, cuenta_declarada, fecha_de, importe, importes, junto_a, moneda

#: La letra con que el BBVA nombra el documento de identidad, contra la Tabla 1 del Anexo 1 de la RS 112-2021.
#: La tabla de la izquierda la declara el propio PDF; la de la derecha, SUNAT. `M` no tiene equivalente.
DOCUMENTO_POR_LETRA = {"R": "6", "L": "1", "P": "7", "E": "4", "M": "0"}

#: Un renglón de la relación de cuentas de abono: `nº  cuenta  BANCO TITULAR  letra - doc  importe  …`
FILA_DE_ABONO = re.compile(
    r"^\s*(?P<orden>\d+)\s+(?P<cuenta>\d{14,})\s+(?P<banco_y_titular>\S.*?)\s+"
    r"(?P<letra>[RLPEM])\s*-\s*(?P<doc>[\dA-Za-z]+)\s+(?P<importe>[\d,]+\.\d{2})",
    re.MULTILINE)

#: La cabecera de la planilla: nº de orden, descripción, fecha, hora y la cuenta de cargo, todo en un renglón.
CABECERA_DE_PLANILLA = re.compile(
    r"^(?P<orden>\d{6,})\s+(?P<descripcion>\S.*?)\s+(?P<fecha>\d{1,2}/\d{1,2}/\d{4})\s+[\d:]{5,8}\s+"
    r"(?P<cuenta>[\d\-]{14,})\s*$",
    re.MULTILINE)

#: Lo que el BBVA cobra por una planilla, en el orden en que lo escribe. Cada una, si no es cero, es su propio
#: movimiento (enmienda 0028) y no un descuento del importe.
COMISIONES = ("Comisión por Otra Plaza", "Comisión Interbancaria")


def _entidades(texto: str) -> list[str]:
    """La lista de bancos que el propio documento trae al pie, de más largo a más corto.

    Se ordena por longitud para que «Banco de Comercio» gane a «Banco», que si no recortaría de menos."""
    return sorted((e.strip() for e in re.findall(r"^-\s*(.+)$", texto, re.MULTILINE)), key=len, reverse=True)


def _partir_banco(junto: str, entidades: list[str]) -> tuple[str, str]:
    """Separa el banco del titular usando la lista del pie. Si no reconoce ninguno, devuelve el texto entero
    como titular: unirlos de menos es un dato incompleto, pero cortar por donde no toca es un dato falso."""
    for entidad in entidades:
        if junto.upper().startswith(entidad.upper()):
            return (junto[:len(entidad)].strip(), junto[len(entidad):].strip())
    return ("", junto.strip())


def operacion(texto: str, cuentas=()) -> list[Movimiento]:
    """«Su operación ha sido realizada»: una transferencia suelta, con su beneficiario y sin comisión."""
    numero = junto_a(texto, "Número de Operación", r"\d+")
    if not numero:
        raise ConstanciaIlegible("bbva_operacion: no trae número de operación")
    del_cargo = junto_a(texto, "Número de Cuenta de Cargo", r"[\d\-]{10,}")
    beneficiario = junto_a(texto, "Cuenta / Tarjeta / Servicio Beneficiario", r"[^\n]+")
    partido = re.match(r"(?P<cuenta>[\d\-]{10,})\s+(?P<nombre>\S.*)", beneficiario)

    cargado = junto_a(texto, "Importe Cargado", r"[^\n]+")
    return [Movimiento(cuenta=cuenta_declarada(del_cargo, cuentas), referencia=numero,
                       fecha=fecha_de(texto, "Fecha / Hora"), sentido=CARGO, origen=PDF_TEXTO,
                       importe=importe(texto, "Importe Cargado"), moneda=moneda(cargado),
                       descripcion=junto_a(texto, "Tipo de Operación", r"[^\n]+") or "Transferencia BBVA",
                       contraparte_nombre=partido.group("nombre").strip() if partido else "",
                       referencias=_orden_interna(texto),
                       datos_originales={"formato": "bbva_operacion", "cuenta_cargo": del_cargo,
                                         "cuenta_destino": partido.group("cuenta") if partido else ""})]


def masivos(texto: str, cuentas=()) -> list[Movimiento]:
    """«Consulta de la Orden»: el cargo de la planilla y sus comisiones, cada una como su propio movimiento.

    Devuelve de uno a tres movimientos de la misma cuenta, y las filas de abono —cuando el texto las trae— van
    como `referencias` del cargo, cada una con su importe: es un pago que cancela N cosas, que es exactamente lo
    que `referencias` modela y la razón de que no haga falta ningún bloque nuevo."""
    cabecera = CABECERA_DE_PLANILLA.search(texto)
    if not cabecera:
        raise ConstanciaIlegible("bbva_masivos: no se encontró la cabecera de la planilla "
                                 "(nº de orden, descripción, fecha y cuenta de cargo)")
    del_cargo = cabecera.group("cuenta")
    comun = {"cuenta": cuenta_declarada(del_cargo, cuentas), "referencia": cabecera.group("orden"),
             "fecha": fecha_de(texto, "Fecha y Hora de Ejecución"), "sentido": CARGO, "origen": PDF_TEXTO}

    abonado = importe(texto, "Importe cargado por abonos")
    divisa = moneda(junto_a(texto, "Importe cargado por abonos", r"[^\n]+"))
    cobradas = [(nombre, importe(texto, nombre)) for nombre in COMISIONES]
    total = importe(texto, "TOTAL CARGADO")
    suma = abonado
    for _nombre, cuanto in cobradas:
        suma = suma + cuanto
    if suma != total:
        raise ConstanciaIlegible(f"bbva_masivos: el papel dice TOTAL CARGADO {total} y los abonos más las "
                                 f"comisiones suman {suma}")

    entidades = _entidades(texto)
    filas, de_las_filas, pie = [], None, False
    for fila in FILA_DE_ABONO.finditer(texto):
        banco, titular = _partir_banco(fila.group("banco_y_titular"), entidades)
        pie = pie or not banco
        suyo = importes(fila.group("importe"))[0]
        filas.append(Referencia(clase=LIBRE, importe=suyo, datos={"texto":
                     f"{titular} · {fila.group('letra')}-{fila.group('doc')} · "
                     f"{banco or 'banco no reconocido'} {fila.group('cuenta')}"}))
        de_las_filas = suyo if de_las_filas is None else de_las_filas + suyo
    if filas and de_las_filas != abonado:
        raise ConstanciaIlegible(f"bbva_masivos: las {len(filas)} filas de abono suman {de_las_filas} y el papel "
                                 f"dice que cargó {abonado} por abonos")

    suyos = {"formato": "bbva_masivos", "cuenta_cargo": del_cargo,
             "abonos": junto_a(texto, "Abonos procesados", r"\d+"),
             "planilla": cabecera.group("descripcion").strip()}
    if pie:
        suyos["aviso"] = "alguna fila de abono no trae un banco reconocible: el nombre va completo en el titular"

    unico = filas[0] if len(filas) == 1 else None
    solo = FILA_DE_ABONO.search(texto) if unico else None
    cargo = Movimiento(importe=abonado, moneda=divisa, descripcion=suyos["planilla"] or "Pago de proveedores",
                       contraparte_nombre=_partir_banco(solo.group("banco_y_titular"), entidades)[1] if solo else "",
                       contraparte_doc=solo.group("doc") if solo else "",
                       contraparte_tipo_doc=DOCUMENTO_POR_LETRA.get(solo.group("letra"), "0") if solo else "",
                       referencias=_orden_interna(texto) + filas, datos_originales=suyos, **comun)

    salen = [cargo]
    for nombre, cuanto in cobradas:
        if cuanto:
            # Sin la referencia de la planilla, y por la misma razón que en el BCP: `Movimiento.clave` es
            # `(cuenta, referencia)`, así que compartirla haría de las dos cosas un solo movimiento y el motor
            # descartaría la segunda como repetida. Las dos comisiones del BBVA se distinguen entre sí por su
            # descripción, que es lo que la clave larga mira.
            salen.append(Movimiento(importe=cuanto, moneda=divisa, descripcion=nombre,
                                    datos_originales={**suyos, "concepto": nombre.lower().replace(" ", "_"),
                                                      "operacion": comun["referencia"]},
                                    **{**comun, "referencia": ""}))
    return salen


def _orden_interna(texto: str) -> list:
    """La orden de pago de la empresa, cuando el papel la lleva. En el BBVA viene con cola —`OP 12477 BANCA
    AUTOMATIC`—, así que se recorta al número, que es lo que identifica la orden."""
    orden = junto_a(texto, "Referencia", r"OP\s*\d+")
    return [Referencia(clase=LIBRE, datos={"texto": re.sub(r"\s+", " ", orden)})] if orden else []
