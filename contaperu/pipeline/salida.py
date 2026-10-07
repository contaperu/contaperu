"""La salida: el archivo de un libro hacia un destino, y lo que se responde de él.

El TXT del registro (y el ZIP con el que se sube a SUNAT) o el archivo de un driver que lleva cuentas: el Excel de
asientos de CONCAR, el CSV, el registro de un sistema contable.

- Si queda algún comprobante con observaciones de nivel `error`, no genera (`ErroresBloqueantes`) salvo que se pida
  explícitamente `incluir_errores=True`.
- El ZIP es reproducible (fecha fija en la entrada) para que dos exportaciones iguales den los mismos bytes.
"""
from __future__ import annotations

import base64
import io
import zipfile
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .. import asiento as asi
from .. import drivers
from .._version import __version__
from ..drivers import contrato
from ..drivers.kit import texto as kit_texto
from ..errores import ErroresBloqueantes
from ..modelo import Comprobante, Libro
from . import armado
from .preparacion import fecha_de, lineas_de, preparar
from .seleccion import errores_de, fuera_de, seleccionar


@dataclass
class Exportado:
    nombre: str          # nombre oficial del TXT (o del Excel)
    nombre_comprimido: str   # '' en los drivers de archivo
    formato: str         # 'sire_rvie', 'sire_rce', 'concar_xlsx', 'contasis_xlsx', 'csv_asiento' o el de un tercero
    driver: str
    texto: bytes             # el TXT; b'' en los drivers de archivo
    comprimido: bytes        # el ZIP del TXT; b'' en los drivers de archivo
    comprobantes: int        # cuántos comprobantes salieron
    resumen: dict
    # Lo que se guarda y se descarga: el ZIP del TXT, o el Excel tal cual.
    archivo: str = ""
    contenido: bytes = b""
    content_type: str = "application/zip"
    # Lo que la respuesta dice de cada comprobante que salió (hito 0.4): su identidad y, en un asiento, su tramo de
    # líneas y su huella.
    por_comprobante: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.archivo:
            self.archivo = self.nombre_comprimido or self.nombre
        if not self.contenido:
            self.contenido = self.comprimido


def _en_zip(nombre: str, datos: bytes) -> tuple[str, bytes]:
    """El archivo dentro de un ZIP de un solo miembro, con su mismo nombre base.

    **Reproducible**: la fecha de la entrada es fija, así que el mismo contenido da el mismo ZIP byte a byte, y
    quien guarde su huella la reconoce. El nombre se corta por el último punto, que es la razón por la que
    `kit.nombre_de_archivo` no omite nunca la extensión.
    """
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as archivo_zip:
        info = zipfile.ZipInfo(nombre, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archivo_zip.writestr(info, datos)
    return nombre.rsplit(".", 1)[0] + ".zip", memoria.getvalue()


def lineas_de_texto(libro: Libro, comprobantes: list[Comprobante], driver: str, opciones: Any = None) -> list[str]:
    modulo = drivers.obtener(driver)
    opciones = opciones or modulo.OPCIONES
    return [modulo.linea(c, libro, i, opciones) for i, c in enumerate(comprobantes, start=1)]


def _resumen(comprobantes: list[Comprobante], incluidos: list[Comprobante], errores: list, opciones: Any,
             fuera: list[Comprobante] | None = None, config: dict | None = None) -> dict:
    def signo(c: Comprobante) -> Decimal:
        return Decimal(-1) if (opciones.signo_nc and c.es_nota_credito) else Decimal(1)

    return {
        "comprobantes": len(incluidos),
        "excluidos": sum(1 for c in comprobantes if c.excluida),
        "duplicados": sum(1 for c in comprobantes if c.estado == "duplicada" and not c.excluida),
        "con_aviso": sum(1 for c in incluidos if c.observaciones and not c.tiene_errores),
        "con_error": len(errores),
        # Comprobantes que este driver no puede llevar (recibos por honorarios en
        # el SIRE): se anota para que el histórico no parezca que se perdieron.
        "fuera_del_destino": len(fuera or []),
        # Las facturas que el contador marcó como anuladas por una nota de crédito (5.3.1). Se cuentan
        # por el mismo motivo que la línea de arriba: la marca hace desaparecer dos líneas del asiento
        # —el recorte y la provisión del depósito— y hasta ahora no quedaba rastro de ello en ninguna
        # parte. **`anuladas_por_nota` y no `anuladas`**: «anulado» ya significa otra cosa en este
        # dominio, la comunicación de baja de SUNAT, y son dos hechos distintos.
        #
        # **Sale 0 en un registro tributario**, y no por descuido: a un driver que no lleva cuentas se le
        # entrega `config=None` a propósito (`exportar_archivo`), así que aquí no hay imputación que
        # mirar. Encaja con lo que la marca significa — «el asiento es una cosa y el registro es otra»:
        # en el TXT del SIRE el comprobante va entero y la marca no cambia ni un byte, así que no hay
        # nada que contar.
        "anuladas_por_nota": sum(1 for c in incluidos if asi.anulada_por_nota(c, config or {})),
        "total": str(sum((c.total * signo(c) for c in incluidos), Decimal("0.00"))),
        "igv": str(sum((c.igv * signo(c) for c in incluidos), Decimal("0.00"))),
    }


def generar(libro: Libro, comprobantes: list[Comprobante], driver: str, opciones: Any = None,
            incluir_errores: bool = False, config: dict | None = None,
            correlativos: dict[str, int] | None = None, lineas: list | None = None) -> Exportado:
    """`config`, la configuración contable, la pide todo driver que lleva cuentas (`contrato.lleva_cuentas`), y
    `correlativos`, además, el que arma asientos (`contrato.arma_asientos`).

    `lineas` son las del bloque `asiento` del documento, cuando lo trae: entonces el asiento **no se rearma**, se
    usa, y los correlativos no hacen falta porque cada línea trae el suyo (5.2)."""
    modulo = drivers.obtener(driver)
    opciones = opciones or modulo.OPCIONES
    formato = drivers.formato_de(driver, libro.tipo)
    incluidos = seleccionar(comprobantes)
    # Cada driver se lleva lo que le toca: el TXT del SIRE deja fuera los
    # recibos por honorarios; el Excel de CONCAR los lleva a su sub-diario.
    fuera = fuera_de(incluidos, getattr(modulo, "EXCLUYE_TIPOS", None))
    if fuera:
        incluidos = [c for c in incluidos if c not in fuera]
    errores = errores_de(incluidos)
    if errores and not incluir_errores:
        raise ErroresBloqueantes(errores)

    forma = contrato.forma(modulo)
    if forma in ("desde_lineas", "desde_comprobantes"):
        if config is not None:
            config = armado.config_para(modulo, config)
        detalle = armado.identidades(libro, incluidos)
        if forma == "desde_lineas":
            if lineas is None:
                contenido, extra, lineas, indice = armado.desde_lineas_con_indice(modulo, libro, incluidos, opciones,
                                                                                  config, correlativos)
            else:
                contenido, extra, lineas, indice = armado.desde_lineas_dadas(modulo, libro, incluidos, lineas,
                                                                             opciones, config)
            detalle = armado.por_comprobante(libro, lineas, indice)
        else:
            contenido, extra = armado.desde_comprobantes(modulo, libro, incluidos, opciones, config)
        nombre = modulo.nombre(libro, opciones)
        resumen = {**_resumen(comprobantes, incluidos, errores, opciones, fuera, config), **extra}
        tipo = getattr(modulo, "CONTENT_TYPE", "application/octet-stream")
        # Comprimir es del FORMATO, no de la forma del driver: lo pide un sistema que importa un archivo
        # envuelto, y hasta la 2.3 solo sabía hacerlo la rama de texto, que es la del SIRE. Se pobla `texto`
        # además del ZIP porque es por donde bifurcan `respuesta()`, la CLI y el MCP. **Ningún driver de serie
        # entra hoy por aquí**: lo hacía STARSOFT y en la 6.0 dejó de hacerlo, porque su pantalla de importación
        # quiere el TXT suelto. Queda para un driver de tercero cuyo destino sí pida el envoltorio.
        if getattr(opciones, "comprimir", False):
            nombre_comprimido, comprimido = _en_zip(nombre, contenido)
            return Exportado(
                nombre=nombre, nombre_comprimido=nombre_comprimido, formato=formato, driver=driver,
                texto=contenido, comprimido=comprimido, comprobantes=len(incluidos), resumen=resumen,
                archivo=nombre_comprimido, contenido=comprimido, content_type=tipo, por_comprobante=detalle,
            )
        return Exportado(
            nombre=nombre, nombre_comprimido="", formato=formato, driver=driver, texto=b"", comprimido=b"",
            comprobantes=len(incluidos), resumen=resumen,
            archivo=nombre, contenido=contenido, content_type=tipo, por_comprobante=detalle,
        )

    # Unir y codificar vive en el kit desde la 4.2: lo comparte con el driver del Libro Diario del PLE, que por la
    # forma de su fila es `desde_lineas` y no pasa por aquí. La política de codificación es una sola.
    texto = kit_texto.armar_archivo(lineas_de_texto(libro, incluidos, driver, opciones), opciones)

    nombre = modulo.nombre(libro, opciones)
    nombre_comprimido, comprimido = _en_zip(nombre, texto)

    return Exportado(
        nombre=nombre, nombre_comprimido=nombre_comprimido, formato=formato, driver=driver,
        texto=texto, comprimido=comprimido, comprobantes=len(incluidos),
        resumen=_resumen(comprobantes, incluidos, errores, opciones, fuera, config),
        por_comprobante=armado.identidades(libro, incluidos),
    )


def exportar_archivo(doc: dict, *, driver: str, configuracion: dict | None = None, correlativos: dict | None = None,
                     incluir_observados: bool = False, imputacion: dict | None = None,
                     claves_previas: Any = None) -> Exportado:
    """El archivo de un documento hacia `driver`, en bytes: preparar, numerar desde los correlativos dados (o desde 1) y
    generar."""
    libro, comprobantes, config = preparar(doc, configuracion, incluir_observados, imputacion, driver, claves_previas)
    modulo = drivers.obtener(driver)
    # El asiento que el documento TRAIGA manda sobre el que el motor derivaría (5.2): quien lo produjo ya numeró, y
    # rearmarlo le cambiaría el correlativo a un asiento que puede haber salido ya.
    dadas = lineas_de(doc) if contrato.forma(modulo) == "desde_lineas" else None
    # Lo que pide la forma del driver: la configuración, todo el que lleva cuentas (también el registro de un
    # sistema contable); los correlativos, además, el que arma asientos — y solo si hay que numerar.
    corr = None
    if contrato.arma_asientos(modulo) and dadas is None:
        corr = asi.correlativos_de_partida(comprobantes, config, libro.es_venta, correlativos)
    return generar(libro, comprobantes, driver, incluir_errores=incluir_observados,
                   config=config if contrato.lleva_cuentas(modulo) else None, correlativos=corr, lineas=dadas)


def respuesta(exp: Exportado, cuando: str | None = None) -> dict:
    """Lo que se responde de una exportación, en JSON: el archivo en base64 (y en texto si es legible) y `_exportacion`,
    la anotación con que un productor reconoce lo que ya exportó."""
    salida: dict[str, Any] = {
        "driver": exp.driver, "formato": exp.formato, "archivo": exp.nombre,
        "comprobantes": exp.comprobantes, "resumen": exp.resumen,
        "_exportacion": {"driver": exp.driver, "archivo": exp.nombre,
                         **({"huella": exp.resumen["huella"]} if exp.resumen.get("huella") else {}),
                         **({"fecha": cuando} if cuando else {}),
                         "comprobantes": exp.por_comprobante, "motor": __version__},
    }
    if exp.texto:
        salida["texto"] = exp.texto.decode("utf-8", errors="replace")
        salida["zip_base64"] = base64.b64encode(exp.comprimido).decode()
        salida["archivo_zip"] = exp.nombre_comprimido
    else:
        contenido = exp.contenido
        salida["content_type"] = exp.content_type
        if (exp.content_type or "").startswith("text/"):
            salida["texto"] = contenido.decode("utf-8-sig", errors="replace")
        salida["contenido_base64"] = base64.b64encode(contenido).decode()
    return salida


def exportar(doc: dict, *, driver: str, configuracion: dict | None = None, correlativos: dict | None = None,
             incluir_observados: bool = False, fecha: str | None = None, imputacion: dict | None = None,
             claves_previas: Any = None) -> dict:
    """Genera el archivo que pide un sistema contable y lo responde en JSON (`respuesta`). La fecha, si se da, se
    comprueba antes que nada."""
    cuando = fecha_de(fecha)
    exp = exportar_archivo(doc, driver=driver, configuracion=configuracion, correlativos=correlativos,
                           incluir_observados=incluir_observados, imputacion=imputacion, claves_previas=claves_previas)
    return respuesta(exp, cuando)
