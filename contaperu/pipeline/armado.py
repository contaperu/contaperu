"""Armar: el asiento de un mes y la forma en que cada driver lo recibe.

La contabilidad se escribe una vez para todos los sistemas: el núcleo arma las líneas neutrales, las numera y exige que
cuadren; un driver de asientos solo las traduce, y uno de registro recibe los comprobantes después de que el núcleo
exigió lo que ese destino pide.
"""
from __future__ import annotations

from typing import Any

from .. import asiento as asi
from .. import configuracion as _declaracion
from .. import drivers, partida_doble
from ..asiento.huella import huella
from ..asiento.resolucion import exigir_requisitos, fundir_config
from ..configuracion import CONFIG_POR_DEFECTO, CONFIGURACION_GENERAL, ConfiguracionInvalida
from ..drivers import contrato
from ..modelo import Comprobante, Libro
from .preparacion import documento, preparar


def config_para(modulo, config: dict) -> dict:
    """La configuración con la que se llama a un driver que lleva cuentas: la ya aplicada para él
    (`preparacion.config_aplicada(configuracion, driver)`), comprobada contra lo que se configura para él —lo general y
    su sección— y completada con sus valores por defecto. Quien llama aquí directamente recibe los mismos errores que
    por la API, en vez de exportar con el valor de fábrica una clave que nadie leyó."""
    secciones = [clave for clave in config if clave in drivers.DRIVERS]
    if secciones:
        raise ConfiguracionInvalida([f"`{clave}` es la sección de un sistema: aquí llega la configuración ya aplicada "
                                     "(`operaciones.config_aplicada(configuracion, driver)`)" for clave in secciones])
    errores = _declaracion.validar({k: v for k, v in config.items() if k != "imputaciones"},
                                   (*CONFIGURACION_GENERAL, *contrato.configuracion(modulo)),
                                   contrato.columnas_elegibles(modulo))
    if errores:
        raise ConfiguracionInvalida(errores)
    return fundir_config({**CONFIG_POR_DEFECTO, **contrato.seccion_por_defecto(modulo)}, config)


def desde_lineas(modulo, libro: Libro, comprobantes: list[Comprobante], opciones: Any,
                 config: dict | None = None, correlativos: dict[str, int] | None = None) -> tuple[bytes, dict]:
    """Un driver de asientos de la forma `desde_lineas`: el núcleo arma las líneas neutrales, las
    numera y exige que cuadren; el driver solo las traduce. Así la contabilidad se escribe una vez
    para todos los ERP, y un driver nuevo no puede equivocarse en una cuenta ni en un sentido."""
    if config is None or correlativos is None:
        raise ValueError(f"El driver {modulo.NOMBRE!r} arma asientos: necesita `config` y `correlativos`")
    # Lo que ese destino exige (`contrato.exige`: lo del núcleo más su EXIGE) se comprueba ANTES de
    # armar nada: un driver `desde_lineas` nunca ve los comprobantes, así que solo el núcleo puede.
    exigir_requisitos(comprobantes, config, libro.es_venta, contrato.exige(modulo))
    # Lo que su formato no puede llevar detiene también a un driver de asientos, antes de armar nada.
    fuera = contrato.no_caben(modulo, libro, comprobantes, config)
    if fuera:
        raise contrato.NoCabe(fuera)
    lineas, rangos, indice = asi.lineas_e_indice_del_libro(libro, comprobantes, config, correlativos, opciones,
                                                           contrato.centro_en_anexo(modulo, config))
    cuadre = partida_doble.exigir(lineas)
    if contrato.acepta_indice(modulo):
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones, indice=indice)
    else:
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones)
    return contenido, {"filas": len(lineas), "sub_diarios": dict(rangos),
                       "debe": str(cuadre.debe), "haber": str(cuadre.haber), "huella": huella(lineas), **extra}


def desde_comprobantes(modulo, libro: Libro, comprobantes: list[Comprobante], opciones: Any,
                       config: dict | None = None) -> tuple[bytes, dict]:
    """Un driver de registro de la forma `desde_comprobantes`: el sistema contable que importa su registro y arma
    el asiento él mismo. No hay asiento que armar ni que numerar, pero sí cuentas que llevar: el núcleo exige lo
    que ese destino pide (`contrato.exige`) y lo que su formato no lleva (`no_caben`) ANTES de llamarlo, y el
    driver lee cada cuenta de `asiento.partes_de` y `asiento.cuenta_tercero`, la misma resolución que usa el asiento.
    Sin asiento no hay cuadre ni huella."""
    if config is None:
        raise ValueError(f"El driver {modulo.NOMBRE!r} lleva cuentas: necesita `config`")
    exigir_requisitos(comprobantes, config, libro.es_venta, contrato.exige(modulo))
    fuera = contrato.no_caben(modulo, libro, comprobantes, config)
    if fuera:
        raise contrato.NoCabe(fuera)
    return modulo.desde_comprobantes(libro, comprobantes, config, opciones)


def generar_asiento(doc: dict, *, driver: str, configuracion: dict | None = None, correlativos: dict | None = None,
                    incluir_observados: bool = False, imputacion: dict | None = None) -> dict:
    """Comprobantes -> líneas de diario del estándar, sin formato de ningún ERP.

    Con la configuración del sistema de `driver`, que tiene que armar asientos: sus siglas, sus sub-diarios y las
    columnas en que pone el centro de costo deciden lo que llevan las líneas, que son las mismas de su archivo."""
    modulo = drivers.obtener(driver)
    if not contrato.arma_asientos(modulo):
        con_asientos = [nombre for nombre, m in drivers.DRIVERS.items() if contrato.arma_asientos(m)]
        raise ValueError(f"El driver {driver!r} no arma asientos: las líneas salen con la configuración de uno que "
                         f"sí ({', '.join(con_asientos)})")
    libro, comprobantes, config = preparar(doc, configuracion, incluir_observados, imputacion, driver)
    corr = asi.correlativos_de_partida(comprobantes, config, libro.es_venta, correlativos)
    # Directo a las líneas neutrales: sin pasar por las columnas de ningún ERP.
    neutrales, rangos = asi.lineas_del_libro(libro, comprobantes, config, corr,
                                             centro_en_anexo=contrato.centro_en_anexo(modulo, config))
    lineas = [ln.a_dict() for ln in neutrales]
    cuadre = partida_doble.cuadra(lineas)
    salida = documento(libro, lineas=lineas)
    salida["_asiento"] = {"lineas": len(lineas), "sub_diarios": dict(rangos), "cuadre": cuadre.a_dict(),
                          "huella": huella(neutrales)}
    return salida
