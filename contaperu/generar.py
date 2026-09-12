"""Generar el archivo de salida de un libro: el TXT del registro (y el ZIP con el
que se sube a SUNAT) o el archivo de un driver que lleva cuentas: el Excel de asientos
de CONCAR, el CSV, el registro de un sistema contable.

- Respeta el orden de entrada: el que ordena es quien llama (la API por fecha
  y serie-número; los golden, tal cual vienen).
- Excluye lo que el usuario excluyó y los duplicados; si queda algún comprobante
  con observaciones de nivel `error`, no genera (`ErroresBloqueantes`) salvo que
  se pida explícitamente `incluir_errores=True`.
- El ZIP es reproducible (fecha fija en la entrada) para que dos exportaciones
  iguales den los mismos bytes.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from decimal import Decimal

from . import drivers, partida_doble
from .asiento.construir import exigir_requisitos
from .asiento.huella import huella
from .asiento.motor import lineas_del_libro
from .drivers import contrato
from .modelo import Comprobante, Libro
from .formato import Opciones


class ErroresBloqueantes(Exception):
    def __init__(self, errores: list[dict]):
        super().__init__(f"{len(errores)} comprobante(s) con errores que bloquean la exportación")
        self.errores = errores


@dataclass
class Exportado:
    nombre: str          # nombre oficial del TXT (o del Excel)
    nombre_zip: str      # '' en las drivers binarias
    formato: str         # 'ple_141' | 'ple_081' | 'sire_rvie' | 'sire_rce' | 'concar_xlsx'
    driver: str
    txt: bytes           # b'' en las drivers binarias
    zip: bytes           # b'' en las drivers binarias
    n_filas: int
    resumen: dict
    # Lo que se guarda en Storage y se descarga: el ZIP del TXT, o el Excel tal cual.
    archivo: str = ""
    contenido: bytes = b""
    content_type: str = "application/zip"

    def __post_init__(self) -> None:
        if not self.archivo:
            self.archivo = self.nombre_zip or self.nombre
        if not self.contenido:
            self.contenido = self.zip


def etiqueta(c: Comprobante) -> str:
    return f"{c.tipo_cp} {c.serie}-{c.numero}".strip()


def errores_de(comprobantes: list[Comprobante]) -> list[dict]:
    return [
        {
            "indice": i,
            "comprobante": etiqueta(c),
            "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "error"],
        }
        for i, c in enumerate(comprobantes)
        if c.tiene_errores
    ]


def seleccionar(comprobantes: list[Comprobante]) -> list[Comprobante]:
    return [c for c in comprobantes if not c.excluida and c.estado != "duplicada"]


def fuera_de(comprobantes: list[Comprobante], tipos) -> list[Comprobante]:
    """Los que esta driver no puede llevar (hoy: el recibo por honorarios no se
    anota en el registro que se declara a SUNAT, pero sí en el asiento contable)."""
    return [c for c in comprobantes if c.tipo_cp in (tipos or frozenset())]


def lineas(libro: Libro, comprobantes: list[Comprobante], driver: str = drivers.DRIVER_DEFAULT,
           opciones: Opciones | None = None) -> list[str]:
    mod = drivers.obtener(driver)
    op = opciones or mod.OPCIONES
    return [mod.linea(c, libro, i, op) for i, c in enumerate(comprobantes, start=1)]


def _resumen(comprobantes: list[Comprobante], incluidos: list[Comprobante], errores: list, op: Opciones,
             fuera: list[Comprobante] | None = None) -> dict:
    def signo(c: Comprobante) -> Decimal:
        return Decimal(-1) if (op.signo_nc and c.es_nota_credito) else Decimal(1)

    return {
        "comprobantes": len(incluidos),
        "excluidos": sum(1 for c in comprobantes if c.excluida),
        "duplicados": sum(1 for c in comprobantes if c.estado == "duplicada" and not c.excluida),
        "con_avisos": sum(1 for c in incluidos if c.observaciones and not c.tiene_errores),
        "con_errores": len(errores),
        # Comprobantes que esta driver no puede llevar (recibos por honorarios en
        # el SIRE): se anota para que el histórico no parezca que se perdieron.
        "fuera_del_registro": len(fuera or []),
        "total": str(sum((c.total * signo(c) for c in incluidos), Decimal("0.00"))),
        "igv": str(sum((c.igv * signo(c) for c in incluidos), Decimal("0.00"))),
    }


def _desde_lineas(mod, libro: Libro, comprobantes: list[Comprobante], op: Opciones,
                  contab: dict | None = None, correlativos: dict[str, int] | None = None) -> tuple[bytes, dict]:
    """Un driver de asientos de la forma `desde_lineas`: el núcleo arma las líneas neutrales, las
    numera y exige que cuadren; el driver solo las traduce. Así la contabilidad se escribe una vez
    para todos los ERP, y un driver nuevo no puede equivocarse en una cuenta ni en un sentido."""
    if contab is None or correlativos is None:
        raise ValueError(f"El driver {mod.NOMBRE!r} arma asientos: necesita `contab` y `correlativos`")
    # Lo que ese destino exige (`contrato.exige`: lo del núcleo más su EXIGE) se comprueba ANTES de
    # armar nada: un driver `desde_lineas` nunca ve los comprobantes, así que solo el núcleo puede.
    exigir_requisitos(comprobantes, contab, libro.es_venta, contrato.exige(mod))
    lineas, rangos = lineas_del_libro(libro, comprobantes, contab, correlativos, op)
    cuadre = partida_doble.exigir(lineas)
    contenido, extra = mod.desde_lineas(libro, lineas, contab, op)
    return contenido, {"filas": len(lineas), "sub_diarios": dict(rangos),
                       "debe": str(cuadre.debe), "haber": str(cuadre.haber), "huella": huella(lineas), **extra}


def _desde_comprobantes(mod, libro: Libro, comprobantes: list[Comprobante], op: Opciones,
                        contab: dict | None = None) -> tuple[bytes, dict]:
    """Un driver de registro de la forma `desde_comprobantes`: el sistema contable que importa su registro y arma
    el asiento él mismo. No hay asiento que armar ni que numerar, pero sí cuentas que llevar: el núcleo exige lo
    que ese destino pide (`contrato.exige`) ANTES de llamarlo, y el driver lee cada cuenta de `asiento.partes_de`
    y `asiento.cuenta_tercero`, la misma resolución que usa el asiento. Sin asiento no hay cuadre ni huella."""
    if contab is None:
        raise ValueError(f"El driver {mod.NOMBRE!r} lleva cuentas: necesita `contab`")
    exigir_requisitos(comprobantes, contab, libro.es_venta, contrato.exige(mod))
    return mod.desde_comprobantes(libro, comprobantes, contab, op)


def generar(libro: Libro, comprobantes: list[Comprobante], driver: str = drivers.DRIVER_DEFAULT,
            opciones: Opciones | None = None, incluir_errores: bool = False, **params) -> Exportado:
    """`params` son los que pide la forma del driver: `contab`, todo el que lleva cuentas
    (`contrato.necesita_config`), y además `correlativos`, el que arma asientos (`contrato.necesita_asiento`)."""
    mod = drivers.obtener(driver)
    op = opciones or mod.OPCIONES
    formato = drivers.formato(driver, libro.tipo)
    incluidos = seleccionar(comprobantes)
    # Cada driver se lleva lo que le toca: el TXT del SIRE/PLE deja fuera los
    # recibos por honorarios; el Excel de CONCAR los lleva a su sub-diario.
    fuera = fuera_de(incluidos, getattr(mod, "EXCLUYE_TIPOS", None))
    if fuera:
        incluidos = [c for c in incluidos if c not in fuera]
    errores = errores_de(incluidos)
    if errores and not incluir_errores:
        raise ErroresBloqueantes(errores)

    forma = contrato.forma(mod)
    if forma in ("desde_lineas", "desde_comprobantes", "construir"):
        if forma == "desde_lineas":
            contenido, extra = _desde_lineas(mod, libro, incluidos, op, **params)
        elif forma == "desde_comprobantes":
            contenido, extra = _desde_comprobantes(mod, libro, incluidos, op, **params)
        else:
            contenido, extra = mod.construir(libro, incluidos, op=op, **params)
        nombre = mod.nombre(libro, op)
        return Exportado(
            nombre=nombre, nombre_zip="", formato=formato, driver=driver, txt=b"", zip=b"",
            n_filas=len(incluidos), resumen={**_resumen(comprobantes, incluidos, errores, op, fuera), **extra},
            archivo=nombre, contenido=contenido, content_type=getattr(mod, "CONTENT_TYPE", "application/octet-stream"),
        )

    cuerpo = op.nueva_linea.join(lineas(libro, incluidos, driver, op))
    if cuerpo:
        cuerpo += op.nueva_linea
    if op.sanear:
        txt = cuerpo.encode(op.codificacion)            # tras sanear() es ASCII: no puede fallar
    else:
        txt = cuerpo.encode("cp1252", errors="replace")  # lo que históricamente exigían los libros electrónicos

    nombre = mod.nombre(libro, op)
    nombre_zip = nombre.rsplit(".", 1)[0] + ".zip"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        info = zipfile.ZipInfo(nombre, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, txt)

    return Exportado(
        nombre=nombre, nombre_zip=nombre_zip, formato=formato, driver=driver, txt=txt, zip=buf.getvalue(),
        n_filas=len(incluidos), resumen=_resumen(comprobantes, incluidos, errores, op, fuera),
    )
