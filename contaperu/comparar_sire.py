"""Comparar lo que generamos con lo que SUNAT ya tiene en el SIRE.

Nace del contraste manual del 25-ago-2026, que encontró el fallo de estructura (40
campos en vez de 33) ANTES de subir nada. Aquí queda como herramienta para repetirlo
cada mes en un comando, que es lo que convierte "creo que está bien" en "lo comparé".

Las dos entradas hablan formatos distintos y por eso se normalizan:

- **Lo nuestro**: el archivo de "Reemplazar propuesta" — 33 campos informados y palote
  final, sin cabecera.
- **Lo de SUNAT**: la EXPORTACIÓN del detalle (menú Exportar → ticket → descarga). Trae
  fila de cabecera, 40 columnas, el CAR SUNAT lleno y las siete columnas que completa la
  Administración (tipo de nota, estado, FOB, gratuitas, tipo de operación, DAM, CLU).

Entran los **dos registros**: ventas (Anexo 3, 33 campos informados) y compras (Anexo 11,
37, con el número del comprobante en el 10 porque el 9 es el año de la DUA y las tres
parejas de base/IGV según el destino). Cuál es se deduce del **nombre** del archivo, que
lleva el código del libro que pone SUNAT (`1404` ventas, `0804` compras); contar campos no
sirve, porque un RVIE exportado (40) y un RCE de reemplazo (41) se parecen demasiado.

Se comparan solo los **campos informados**, saltando el 4 (CAR) porque
en el reemplazo va vacío a propósito. Los importes se normalizan (`0` y `0.00` son lo
mismo) y el tipo de cambio también (SUNAT exporta `1.000` en soles; en el reemplazo va
vacío porque el anexo lo pide solo si la moneda no es PEN).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path

from .lectores import sire_txt

# Nombres del Anexo 3 (RVIE), para que el informe diga "IGV" y no "campo 17".
CAMPOS_RVIE = [
    "RUC", "ID / razón social", "periodo", "CAR SUNAT", "fecha de emisión", "vencimiento",
    "tipo de CP", "serie", "número", "número final", "tipo de documento", "nro de documento",
    "nombre del cliente", "exportación", "base gravada", "descuento de la base", "IGV",
    "descuento del IGV", "exonerado", "inafecto", "ISC", "base del IVAP", "IVAP", "ICBPER",
    "otros tributos", "total", "moneda", "tipo de cambio", "fecha del doc. modificado",
    "tipo del doc. modificado", "serie del doc. modificado", "número del doc. modificado",
    "ID de proyecto",
]
# Nombres del Anexo 11 (RCE). Ojo con los desplazamientos frente a ventas: el 9 es el
# año de la DUA, así que el número del comprobante es el 10; y las tres parejas de
# base/IGV (15-20) dicen el destino de la adquisición.
CAMPOS_RCE = [
    "RUC", "ID / razón social", "periodo", "CAR SUNAT", "fecha de emisión", "vencimiento",
    "tipo de CP", "serie", "año de la DUA", "número", "número final", "tipo de documento",
    "nro de documento", "nombre del proveedor", "base gravada DG", "IGV DG", "base gravada DGNG",
    "IGV DGNG", "base gravada DNG", "IGV DNG", "adquisiciones no gravadas", "ISC", "ICBPER",
    "otros tributos", "total", "moneda", "tipo de cambio", "fecha del doc. modificado",
    "tipo del doc. modificado", "serie del doc. modificado", "dependencia aduanera",
    "número del doc. modificado", "clasificación de bienes", "ID de proyecto",
    "% de participación", "IMB", "CAR original",
]
IGNORAR = {4}          # CAR SUNAT: lleno en la exportación, vacío en el reemplazo


class Registro:
    """Dónde está cada cosa en un registro. Ventas y compras NO comparten posiciones."""

    def __init__(self, tipo, campos, i_numero, importes, i_tc, i_contraparte=None):
        self.tipo, self.campos = tipo, campos
        self.i_numero, self.importes, self.i_tc = i_numero, importes, i_tc
        self.i_contraparte = i_contraparte


# `i_contraparte` solo en COMPRAS: ahí el proveedor forma parte de la identidad del
# comprobante —dos proveedores emiten la misma serie-número (8 casos en el registro real
# de julio de un contribuyente real)—. En ventas se deja fuera A PROPÓSITO: el emisor eres tú y tu
# serie-número es única, así que un RUC de cliente mal escrito conviene que salga como
# *diferencia del campo 12* y no como un "falta uno / sobra otro", que cuesta más de leer.
VENTAS = Registro("venta", CAMPOS_RVIE, 9, set(range(14, 27)), 28)
COMPRAS = Registro("compra", CAMPOS_RCE, 10, set(range(15, 26)), 27, i_contraparte=13)


def leer_bytes(datos: bytes) -> list[list[str]]:
    """Filas (lista de campos) de un TXT o del TXT dentro de un ZIP. El parseo es el
    de `sire_txt.leer_lineas` — era el mismo algoritmo copiado dos veces (30-ago-2026)."""
    return sire_txt.leer_lineas(datos)


def registro_de(rutas: list[str | Path], forzado: str = "") -> Registro:
    """¿Es el registro de ventas o el de compras? Por el NOMBRE del archivo.

    Los dos formatos (la exportación y el reemplazo) llevan el código del libro en el
    nombre que pone SUNAT — `1404` ventas, `0804` compras (Tabla 6) —, que es más fiable
    que contar campos: un RVIE exportado (40) y un RCE de reemplazo (41) se parecen
    demasiado. Si el nombre no lo dice, hay que pasar `--registro`.
    """
    if forzado:
        return VENTAS if forzado == "venta" else COMPRAS
    marcas = {("1404" in Path(ruta).name) and "venta" or ("0804" in Path(ruta).name) and "compra"
              for ruta in rutas}
    marcas.discard(False)
    if marcas == {"venta"}:
        return VENTAS
    if marcas == {"compra"}:
        return COMPRAS
    raise ValueError("No se sabe si son ventas o compras por el nombre de los archivos "
                     "(se busca 1404 o 0804). Indícalo con --registro venta|compra.")


def clave(fila: list[str], reg: Registro = VENTAS) -> tuple:
    """Identidad del comprobante: tipo + serie + número, y en COMPRAS también el proveedor."""
    campo = lambda posicion: fila[posicion - 1].strip() if len(fila) >= posicion else ""  # noqa: E731
    identidad = (fila[6].strip(), fila[7].strip().upper(), campo(reg.i_numero).lstrip("0"))
    return identidad + (campo(reg.i_contraparte),) if reg.i_contraparte else identidad


def _norm(posicion: int, valor: str, reg: Registro = VENTAS) -> str:
    valor = (valor or "").strip()
    if posicion in reg.importes or posicion == reg.i_tc:   # importes y tipo de cambio
        if valor in ("", "0", "0.00", "1.000"):  # el TC en soles va vacío en el reemplazo
            return ""
        try:
            return str(Decimal(valor).normalize())
        except InvalidOperation:
            return valor
    if posicion == reg.i_numero:                    # número: 0000256 y 256 son el mismo
        return valor.lstrip("0")
    return valor


def comparar(nuestras: list[list[str]], suyas: list[list[str]], reg: Registro = VENTAS) -> dict:
    """Alinea por comprobante y devuelve qué falta, qué sobra y qué no coincide."""
    nuestras_por_clave = {clave(fila, reg): fila for fila in nuestras}
    suyas_por_clave = {clave(fila, reg): fila for fila in suyas}
    comunes = sorted(set(nuestras_por_clave) & set(suyas_por_clave))
    diferencias = []
    for identidad in comunes:
        de_sunat, nuestra = suyas_por_clave[identidad], nuestras_por_clave[identidad]
        for posicion in range(1, min(len(reg.campos), len(de_sunat), len(nuestra)) + 1):
            if posicion in IGNORAR:
                continue
            valor_sunat = _norm(posicion, de_sunat[posicion - 1], reg)
            valor_nuestro = _norm(posicion, nuestra[posicion - 1], reg)
            if valor_sunat != valor_nuestro:
                diferencias.append({"comprobante": "-".join(identidad), "campo": posicion,
                                    "nombre": reg.campos[posicion - 1],
                                    "sunat": de_sunat[posicion - 1], "nuestro": nuestra[posicion - 1]})
    return {
        "registro": reg.tipo,
        "comunes": comunes,
        "solo_en_sunat": sorted(set(suyas_por_clave) - set(nuestras_por_clave)),
        "solo_nuestros": sorted(set(nuestras_por_clave) - set(suyas_por_clave)),
        "diferencias": diferencias,
    }


def informe(comparacion: dict) -> str:
    lineas = [f"Registro de {comparacion.get('registro', 'venta')}s: {len(comparacion['comunes'])} comprobantes "
              f"en los dos - {len(comparacion['solo_en_sunat'])} solo en SUNAT · "
              f"{len(comparacion['solo_nuestros'])} solo nuestros"]
    # Con el proveedor en la clave (compras), un RUC mal escrito deja de ser una
    # diferencia de campo y aparece como uno que falta + otro que sobra. Se dice, para
    # que no parezcan dos problemas cuando es uno.
    sospechosos = ({identidad[:3] for identidad in comparacion["solo_en_sunat"]}
                   & {identidad[:3] for identidad in comparacion["solo_nuestros"]})
    for identidad in comparacion["solo_en_sunat"]:
        lineas.append(f"  FALTA en lo nuestro: {'-'.join(identidad)}")
    for identidad in comparacion["solo_nuestros"]:
        lineas.append(f"  SOBRA (SUNAT no lo tiene): {'-'.join(identidad)}")
    for identidad in sorted(sospechosos):
        lineas.append(f"  ^ {'-'.join(identidad)} está en los dos con distinto proveedor: revisa el RUC")
    if not comparacion["diferencias"]:
        lineas.append("  Sin diferencias en los campos informados." if comparacion["comunes"]
                      else "  Nada que comparar.")
    for diferencia in comparacion["diferencias"]:
        lineas.append(f"  {diferencia['comprobante']} - campo {diferencia['campo']} ({diferencia['nombre']}): "
                      f"SUNAT [{diferencia['sunat']}] != nuestro [{diferencia['nuestro']}]")
    return "\n".join(lineas)
