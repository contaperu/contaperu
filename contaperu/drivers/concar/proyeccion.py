"""La línea neutral, proyectada a las 41 columnas del Excel de CONCAR.

Lo que aquí se decide es FORMATO de CONCAR, no contabilidad: el código de moneda de su T.G. 03
(MN/US), los flags de conversión, los cortes de la glosa a 40 y 30 caracteres, el importe partido en
soles o dólares, la tasa del IGV entera, el área de la detracción. La contabilidad —qué cuenta, qué
sentido, cuántas líneas— ya viene resuelta en la línea (`asiento/motor.py`).

La regla de este módulo: **el Excel no cambia ni una celda** respecto del que se validó en
producción. Lo vigila `tests/test_snapshot_concar.py`, con 42 casos congelados antes de separar la
contabilidad de su formato (11-sep-2026); hoy son 52.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from ...asiento.configuracion import MONEDAS_CODIGO
from ...asiento.faltas import SinCodigoDeMoneda
from ...asiento.indice import Cabecera
from ...asiento.lineas import LineaDiario
from ...asiento.motor import cabecera_de, lineas_del_comprobante, serie_numero_de
from ..kit import Opciones, celdas
from ...pcge import clase_de
from ...igv import tasa_calculada
from ...modelo import CENTIMO, Comprobante, Libro, numero_sin_ceros, serie_y_numero
from ..contrato import centro_en_anexo
from . import datos
from .datos import COLUMNAS, MARCA_CONVERSION, OPCIONES, TIPO_CONVERSION


def codigo_moneda(moneda: str, config: dict) -> str:
    """Columna E: el código de la T.G. 03. CONCAR solo admite MN y US (rechaza ME); otra moneda
    detiene la exportación en vez de inventarse un código."""
    moneda = (moneda or "PEN").upper()
    codigo = (config.get(MONEDAS_CODIGO) or {}).get(moneda)
    if not codigo:
        raise SinCodigoDeMoneda([moneda])
    return codigo


# Los importes viajan como texto exacto; openpyxl los quiere `float` para darles formato numérico (`drivers.kit.celdas`).
_fecha = celdas.fecha
_importe = celdas.importe


def _cabecera(c: Comprobante | Cabecera) -> Cabecera:
    return c if isinstance(c, Cabecera) else cabecera_de(c)


def fila(linea: LineaDiario, c: Comprobante | Cabecera, config: dict) -> dict[str, Any]:
    """Una línea neutral → una fila del Excel (claves 'A'..'AO', en el orden de la plantilla). `c` es la cabecera del
    comprobante (`asiento.indice`) o el propio comprobante: de ahí salen la glosa de la F y la tasa de la AO."""
    cabecera = _cabecera(c)
    es_usd = linea.moneda == "USD"
    importe = _importe(linea.importe)
    doc, ref, det = linea.documento or {}, linea.referencia or {}, linea.detraccion or {}
    f: dict[str, Any] = {col: "" for col in COLUMNAS}
    f.update({
        "B": linea.sub_diario, "C": linea.correlativo, "D": _fecha(linea.fecha),
        "E": codigo_moneda(linea.moneda, config),
        # F: la glosa de la cabecera, igual en todas las filas del comprobante; W: la de la línea, con
        # su prefijo. Una sola glosa, dos largos: lo único que cambia es lo que admite CONCAR.
        "F": cabecera.glosa[:40], "W": linea.glosa[:30],
        # Con el T.C. del comprobante la conversión es especial ('C'); sin él, CONCAR lo busca en su tabla.
        # **Solo en moneda extranjera**, que es como está validado el Excel que importa un CONCAR real: un
        # apunte en soles no se convierte. Desde la 2.2 la línea puede traer T.C. también en PEN —lo pide
        # STARSOFT en todas sus filas—, así que aquí se mira la moneda y no solo si el campo viene lleno.
        "G": celdas.numero(linea.tipo_cambio) if (es_usd and linea.tipo_cambio) else "",
        "H": "C" if (es_usd and linea.tipo_cambio) else TIPO_CONVERSION,
        "I": MARCA_CONVERSION, "J": _fecha(linea.fecha),
        "K": linea.cuenta, "L": linea.contraparte_doc, "M": linea.centro_costo, "N": linea.debe_haber,
        "O": importe, "P": importe if es_usd else "", "Q": importe if not es_usd else "",
        "R": doc.get("tipo", ""), "S": doc.get("serie_numero", ""),
        # Sin fecha, T y U quedan en None y no en "": así salían antes de separar el asiento de su
        # formato, y el snapshot lo fija. En el .xlsx las dos son la misma celda vacía.
        "T": _fecha(doc.get("fecha_emision"), None), "U": _fecha(doc.get("fecha_vencimiento"), None),
        "X": linea.anexo_auxiliar,
        # AO: CONCAR solo admite la tasa entera. Se redondea desde los importes del comprobante y no
        # desde la tasa de la línea, que ya va redondeada a 2 decimales: redondear dos veces puede
        # dar otro entero.
        "AO": (tasa_igv_entera(Decimal(cabecera.igv), Decimal(cabecera.base_gravada))
               if linea.tasa_igv not in ("", None) else ""),
    })
    if linea.rol == "detraccion":
        # El área (T.G. 26) es un número propio de cada empresa y solo va en esta fila (Excel validado).
        # No se corta a los 3 caracteres de la plantilla: cortar un código lo manda a OTRA área en silencio.
        f["V"] = str(config.get("detraccion_area") or "")
    if ref:
        f.update({"Z": ref.get("tipo", ""), "AA": ref.get("serie_numero", "")[:20],
                  "AB": _fecha(ref.get("fecha"))})
    if det:
        base = _importe(det.get("base"))
        f.update({"AI": det.get("codigo_interno", ""), "AJ": celdas.numero(det.get("tasa", "")),
                  "AK": base if es_usd else "", "AL": base if not es_usd else ""})
    return f


def filas(c: Comprobante | Cabecera, lineas: list[LineaDiario], config: dict) -> list[dict[str, Any]]:
    """Las líneas de UN comprobante → sus filas del Excel. `c` es su cabecera o el propio comprobante."""
    cabecera = _cabecera(c)
    return [fila(ln, cabecera, config) for ln in lineas]


def filas_de_comprobante(c: Comprobante, config: dict, limites: tuple[date, date], correlativo: str,
                         opciones: Opciones = OPCIONES, es_venta: bool = False) -> list[dict[str, Any]]:
    """Un comprobante → sus filas del Excel de CONCAR (claves 'A'..'AO'): su asiento neutral, proyectado.

    Era `asiento.asiento()`, la puerta de siempre hacia las columnas de CONCAR; salió del núcleo el 12-sep-2026 para
    que el núcleo no importe un driver. La moneda se comprueba antes que nada, como siempre: un EUR no llega a buscar
    su cuenta."""
    codigo_moneda(c.moneda, config)
    lineas = lineas_del_comprobante(c, config, limites, correlativo, opciones, es_venta, centro_en_anexo(datos, config))
    return filas(c, lineas, config)


def tasa_igv_entera(igv: Decimal, base_gravada: Decimal) -> Any:
    """Columna AO: la tasa DEL COMPROBANTE, sacada de su base y su IGV, redondeada a entero.

    Nada escrito a mano (John, 10-sep-2026): la tasa es la de cada comprobante —18, 10.5 o 0— y
    CONCAR solo admite enteros, así que se redondea al exportar (ROUND_HALF_UP, como todo el motor).
    Hasta ese día había un 18 de respaldo para «IGV sin base» y una regla que llevaba el 10.5 al 10:
    las dos suponían una tasa en vez de leerla. Sin IGV la celda va vacía (así la lleva un registro
    real), y sin base de la que leerla también: ese comprobante no llega aquí, la validación lo para
    antes con IGV_NO_CUADRA. OJO: la plantilla describe la columna con «valores validos 0,10,18»
    (`datos.py`), así que un 10.5 % que salga 11 hay que comprobarlo con la primera importación real.
    """
    t = tasa_calculada(igv, base_gravada)
    return "" if t is None else int(t.to_integral_value(rounding=ROUND_HALF_UP))



def no_caben(libro: Libro, comprobantes: list[Comprobante], config: dict) -> dict[str, list[Comprobante]]:
    """Lo que el Excel de CONCAR no puede llevar, por motivo (`datos.MOTIVOS`).

    Un código no se corta: una serie cortada sería otra serie, y el asiento entraría con un documento que no
    existe. Hasta la 2.7 esto se cortaba en silencio; ahora el comprobante no sale y la aplicación lo enseña, que
    es lo que ya hacían CONTASIS y el resto del contrato. Las dos glosas SÍ se siguen cortando, porque son texto
    libre: cortadas dicen lo mismo."""
    largo_s, largo_aa = datos.LARGOS_DE_CODIGO["S"], datos.LARGOS_DE_CODIGO["AA"]
    fuera = []
    for c in comprobantes:
        referencia = serie_y_numero(c.ref_serie, numero_sin_ceros(c.ref_numero)) if c.ref_serie or c.ref_numero else ""
        if len(serie_numero_de(c, OPCIONES)) > largo_s or len(referencia) > largo_aa:
            fuera.append(c)
    return {datos.MOTIVOS["largo"]: fuera}


# ── El camino inverso: de las columnas de CONCAR a la línea neutral ──────────────────────────────────────────────
# Era como se obtenía la línea cuando el asiento nacía en columnas (hasta la 0.7), y se conserva con su driver. No
# rellena los campos que llegaron después (`rol`, `tipo_cp`, el código SUNAT de la detracción). Qué significa cada
# columna está en `datos.CABECERAS`, con los títulos literales de la plantilla oficial y sus notas.


def _texto_de(v: Any) -> str:
    if isinstance(v, date):
        return v.isoformat()
    return "" if v is None else str(v).strip()


def _importe_exacto(v: Any) -> str:
    """A texto con 2 decimales. Los importes salen del asiento como float para openpyxl;
    aquí vuelven a ser exactos, que es como viajan en el estándar."""
    if v is None or v == "":
        return ""
    return str(Decimal(str(v)).quantize(CENTIMO))


_numero_o_vacio = celdas.numero_o_vacio


def desde_fila(fila: dict, monedas: dict[str, str] | None = None) -> LineaDiario:
    """Una fila en columnas de CONCAR -> una línea de diario neutral.

    `monedas` traduce el código del ERP al ISO 4217 ('MN' -> 'PEN'); si no se pasa, el código
    se transporta tal cual.
    """
    monedas = monedas or {}
    codigo = _texto_de(fila.get("E"))
    documento = {
        "tipo": _texto_de(fila.get("R")),
        "serie_numero": _texto_de(fila.get("S")),
        "fecha_emision": _texto_de(fila.get("T")),
        "fecha_vencimiento": _texto_de(fila.get("U")),
    }
    referencia = {
        "tipo": _texto_de(fila.get("Z")),
        "serie_numero": _texto_de(fila.get("AA")),
        "fecha": _texto_de(fila.get("AB")),
    }
    detraccion = {
        "codigo_interno": _texto_de(fila.get("AI")),
        "tasa": celdas.texto_exacto(fila.get("AJ")),
        "base": _importe_exacto(fila.get("AK") or fila.get("AL")),
    }
    return LineaDiario(
        cuenta=_texto_de(fila.get("K")),
        debe_haber=_texto_de(fila.get("N")),
        importe=_importe_exacto(fila.get("O")),
        # CONCAR no lleva una columna de clase: no le hace falta, porque su plan de cuentas vive en su sistema. Al
        # volver a línea neutral se deriva de la cuenta, igual que al armarla, o el documento no validaría.
        clase=clase_de(_texto_de(fila.get("K"))),
        sub_diario=_texto_de(fila.get("B")),
        correlativo=_texto_de(fila.get("C")),
        fecha=_texto_de(fila.get("D")),
        moneda=monedas.get(codigo, codigo),
        tipo_cambio=celdas.texto_exacto(fila.get("G")),
        glosa=_texto_de(fila.get("W")),
        contraparte_doc=_texto_de(fila.get("L")),
        centro_costo=_texto_de(fila.get("M")),
        anexo_auxiliar=_texto_de(fila.get("X")),
        documento={k: v for k, v in documento.items() if v},
        referencia={k: v for k, v in referencia.items() if v},
        detraccion={k: v for k, v in detraccion.items() if v not in ("", None)},
        tasa_igv=_numero_o_vacio(fila.get("AO")),
    )


def a_lineas(filas: list[dict], config: dict | None = None) -> list[LineaDiario]:
    """Todas las filas de un asiento -> líneas neutrales. `config` solo se usa para
    devolverle a la moneda su código ISO."""
    codigos = (config or {}).get(MONEDAS_CODIGO) or {}
    monedas = {v: k for k, v in codigos.items()}
    return [desde_fila(f, monedas) for f in filas]
