"""Armar: el asiento de un mes y la forma en que cada driver lo recibe.

La contabilidad se escribe una vez para todos los sistemas: el núcleo arma las líneas del asiento, las numera y exige que
cuadren; un driver de asientos solo las traduce, y uno de registro recibe los comprobantes después de que el núcleo
exigió lo que ese destino pide.
"""
from __future__ import annotations

from typing import Any

from .. import asiento as asi
from .. import configuracion as _declaracion
from .. import drivers
from ..contable import partida_doble
from ..errores import DocumentoInvalido
from .._version import __version__
from ..asiento.huella import huella
from ..asiento.resolucion import exigir_requisitos, fundir_config
from ..configuracion import (CONFIG_POR_DEFECTO, CONFIGURACION_GENERAL, NO_SON_CONFIGURACION,
                             ConfiguracionInvalida)
from ..drivers import contrato
from ..modelo import ORIGEN_YA_ARMADO, ORIGENES_DE_LIBRO, Comprobante, Libro, identidad_de
from .preparacion import documento, libro_de, lineas_de, preparar, preparar_tesoreria
from .seleccion import fuera_de, seleccionar


def config_para(modulo, config: dict) -> dict:
    """La configuración con la que se llama a un driver que lleva cuentas: la ya aplicada para él
    (`preparacion.config_aplicada(configuracion, driver)`), comprobada contra lo que se configura para él —lo general y
    su sección— y completada con sus valores por defecto. Quien llama aquí directamente recibe los mismos errores que
    por la API, en vez de exportar con el valor de fábrica una clave que nadie leyó."""
    secciones = [clave for clave in config if clave in drivers.DRIVERS]
    if secciones:
        raise ConfiguracionInvalida([f"`{clave}` es la sección de un sistema: aquí llega la configuración ya aplicada "
                                     "(`operaciones.config_aplicada(configuracion, driver)`)" for clave in secciones])
    errores = _declaracion.validar({k: v for k, v in config.items() if k not in NO_SON_CONFIGURACION},
                                   (*CONFIGURACION_GENERAL, *contrato.configuracion(modulo)),
                                   contrato.columnas_elegibles(modulo))
    if errores:
        raise ConfiguracionInvalida(errores)
    return fundir_config({**CONFIG_POR_DEFECTO, **contrato.seccion_por_defecto(modulo)}, config)


def identidades(libro: Libro, comprobantes: list[Comprobante]) -> list[dict]:
    """Lo que la respuesta dice de cada comprobante de un registro, que no arma asiento: su identidad."""
    return [{"identidad": identidad_de(libro, c)} for c in comprobantes]


def por_comprobante(libro: Libro, lineas: list, indice: tuple) -> list[dict]:
    """Lo que la respuesta dice de cada comprobante de un asiento (hito 0.4): su identidad, el tramo de líneas que le
    toca (`[desde, hasta)`) y la huella de ese tramo. Los tramos son una partición exacta de las líneas.

    Lo arma `asiento.exportacion_de`, que es quien lo sabe hacer, porque desde la 3.1 lo necesitan dos: esta
    respuesta y el driver que escribe el documento del estándar, que puede llevarlo dentro del archivo. Ya no
    hace falta pasarle los comprobantes: la identidad sale de la cabecera del índice, que sabe decir su clave."""
    return asi.exportacion_de(libro, lineas, indice)["comprobantes"]


# De qué bloque puede salir el asiento de un libro, dicho por la tabla y no a mano: hoy `comprobantes` y
# `movimientos`. La respuesta trae **las dos claves siempre**, la del libro con sus entradas y la otra vacía, que es
# literalmente cierto —un libro de tesorería no tiene comprobantes— y le ahorra a quien la lee tener dos formas.
# Al ser derivado, el día que la tabla gane una fila con otro origen la respuesta gana su clave sola, y el esquema
# se pone rojo por quedarse atrás, que es lo que se quiere.
#
# Desde la 13.1 se deriva una sola vez, en `modelo`, porque la leen tres capas; aquí se conserva el nombre corto.
# **Sin el bloque del asiento** (B13): un libro que llega ya armado no tiene entradas aparte que listar —son sus
# propias líneas, que ya van en la respuesta—, así que abrirle una clave sería meter el asiento dentro de sí
# mismo. Por eso esto no es `ORIGENES_DE_LIBRO` a secas y la respuesta de una compra no gana una clave vacía.
ORIGENES = tuple(o for o in ORIGENES_DE_LIBRO if o != ORIGEN_YA_ARMADO)


def por_entrada(libro: Libro, lineas: list, indice: tuple) -> dict:
    """Lo que la respuesta dice de cada entrada del asiento, bajo la clave de su origen (`comprobantes` o
    `movimientos`), y la de los demás orígenes vacía."""
    detalle = asi.exportacion_de(libro, lineas, indice)
    return {clave: detalle.get(clave) or [] for clave in ORIGENES}


def desde_lineas(modulo, libro: Libro, comprobantes: list[Comprobante], opciones: Any,
                 config: dict | None = None, correlativos: dict[str, int] | None = None) -> tuple[bytes, dict]:
    """Un driver de asientos de la forma `desde_lineas`: el núcleo arma las líneas del asiento, las
    numera y exige que cuadren; el driver solo las traduce. Así la contabilidad se escribe una vez
    para todos los ERP, y un driver nuevo no puede equivocarse en una cuenta ni en un sentido."""
    contenido, resumen, _, _ = desde_lineas_con_indice(modulo, libro, comprobantes, opciones, config, correlativos)
    return contenido, resumen


def desde_lineas_con_indice(modulo, libro: Libro, comprobantes: list[Comprobante], opciones: Any,
                            config: dict | None = None, correlativos: dict[str, int] | None = None,
                            ) -> tuple[bytes, dict, list, tuple]:
    """`desde_lineas`, devolviendo además las líneas y el índice de cada comprobante."""
    if config is None or correlativos is None:
        raise ValueError(f"El driver {modulo.NOMBRE!r} arma asientos: necesita `config` y `correlativos`")
    # Lo que ese destino exige (`contrato.exige`: lo del núcleo más su EXIGE) se comprueba ANTES de
    # armar nada: un driver `desde_lineas` nunca ve los comprobantes, así que solo el núcleo puede.
    exigir_requisitos(comprobantes, config, libro.rasgos, contrato.exige(modulo))
    # Lo que su formato no puede llevar detiene también a un driver de asientos, antes de armar nada.
    fuera = contrato.no_caben(modulo, libro, comprobantes, config)
    if fuera:
        raise contrato.NoCabe(fuera)
    lineas, rangos, indice = asi.lineas_e_indice_del_libro(libro, comprobantes, config, correlativos, opciones,
                                                           contrato.centro_en_anexo(modulo, config),
                                                           vocabulario=contrato.vocabulario(modulo))
    cuadre = partida_doble.exigir(lineas)
    if contrato.acepta_indice(modulo):
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones, indice=indice)
    else:
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones)
    resumen = {"filas": len(lineas), "sub_diarios": dict(rangos),
               "debe": str(cuadre.debe), "haber": str(cuadre.haber), "huella": huella(lineas), **extra}
    return contenido, resumen, lineas, indice


def desde_lineas_dadas(modulo, libro: Libro, comprobantes: list[Comprobante], lineas: list,
                       opciones: Any, config: dict | None = None) -> tuple[bytes, dict, list, tuple]:
    """Como `desde_lineas_con_indice`, pero con las líneas que YA trae el documento: **no las rearma** (5.2).

    Hasta aquí el motor solo sabía exportar lo que él mismo derivaba de los comprobantes, así que no podía releer su
    propio documento: `generar_asiento` devuelve un bloque `asiento` que `exportar` no sabía leer. Esta rama cierra
    ese círculo, y abre la puerta a que un ERP entregue el asiento que lleva él.

    Lo que **sigue igual**, y es la mitad del valor de esta función: el destino exige lo que exige antes de escribir
    nada (`contrato.exige`, de donde sale que el 5.3 pida la denominación), lo que su formato no lleva lo para
    (`no_caben`), y el asiento **tiene que cuadrar** (`partida_doble.exigir`). Entrar por esta puerta no relaja
    ninguna regla: solo evita rederivar lo que ya está hecho.

    Lo que cambia es de dónde sale el índice: de reconocer las líneas en vez de generarlas
    (`asiento.indice_de_lineas_dadas`), por su `documento.id_externo`. Y los correlativos no se piden, porque cada
    línea trae el suyo."""
    exigir_requisitos(comprobantes, config, libro.rasgos, contrato.exige(modulo))
    fuera = contrato.no_caben(modulo, libro, comprobantes, config)
    if fuera:
        raise contrato.NoCabe(fuera)
    indice = asi.indice_de_lineas_dadas(comprobantes, lineas)
    cuadre = partida_doble.exigir(lineas)
    if contrato.acepta_indice(modulo):
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones, indice=indice)
    else:
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones)
    resumen = {"filas": len(lineas), "sub_diarios": asi.rangos_de_lineas_dadas(indice),
               "debe": str(cuadre.debe), "haber": str(cuadre.haber), "huella": huella(lineas), **extra}
    return contenido, resumen, lineas, indice


def desde_lineas_ya_armadas(modulo, libro: Libro, lineas: list, opciones: Any,
                            config: dict | None = None) -> tuple:
    """Las líneas de un libro que llega armado, hacia su destino. Sin índice y sin numerar (B13).

    Hermana de `desde_lineas_dadas` y más corta por lo que NO hace: no exige requisitos —están escritos sobre
    comprobantes y este libro no los tiene—, no construye índice —no hay entradas aparte que indexar— y no
    numera, porque el CUO viene de quien mandó las líneas. Lo que sí hace es lo que no se negocia: **cuadrar**.
    """
    cuadre = partida_doble.exigir(lineas)
    if contrato.acepta_indice(modulo):
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones, indice=())
    else:
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones)
    resumen = {"filas": len(lineas), "sub_diarios": {}, "debe": str(cuadre.debe), "haber": str(cuadre.haber),
               "huella": huella(lineas), **extra}
    return contenido, resumen, lineas, ()


def desde_movimientos(modulo, libro: Libro, movimientos: list, opciones: Any, config: dict | None = None,
                      lineas: list | None = None) -> tuple[bytes, dict, list, tuple]:
    """Un driver de asientos que recibe un libro de movimientos (12.10): el núcleo arma las líneas, exige que
    cuadren, y el driver solo las traduce. La misma promesa que `desde_lineas_con_indice` en el otro camino.

    **Las dos entradas en una función y no en dos**, al contrario que en el camino del comprobante
    (`desde_lineas_con_indice` y `desde_lineas_dadas`): allí son dos porque la rama de las líneas dadas pide
    requisitos y no pide correlativos, y aquí no hay ni una cosa ni la otra —un movimiento no tiene tipo ni moneda
    que exigir y su libro todavía no se numera—, así que lo único que cambia entre las dos es de dónde salen las
    líneas y de dónde sale el índice: de generarlas, o de reconocerlas por su `documento.id_externo`.

    Lo que **no** cambia: el asiento tiene que cuadrar, y lo que el formato del destino no lleva lo para antes de
    escribir nada."""
    if config is None:
        raise ValueError(f"El driver {modulo.NOMBRE!r} arma asientos: necesita `config`")
    fuera = contrato.no_caben(modulo, libro, [], config)
    if fuera:
        raise contrato.NoCabe(fuera)
    if lineas is None:
        lineas, rangos, indice = asi.lineas_e_indice_de_movimientos(libro, movimientos, config,
                                                                    vocabulario=contrato.vocabulario(modulo))
    else:
        indice = asi.indice_de_movimientos_dados(movimientos, lineas, config)
        rangos = asi.rangos_de_lineas_dadas(indice)
    cuadre = partida_doble.exigir(lineas)
    if contrato.acepta_indice(modulo):
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones, indice=indice)
    else:
        contenido, extra = modulo.desde_lineas(libro, lineas, config, opciones)
    resumen = {"filas": len(lineas), "sub_diarios": dict(rangos),
               "debe": str(cuadre.debe), "haber": str(cuadre.haber), "huella": huella(lineas), **extra}
    return contenido, resumen, lineas, indice


def por_movimiento(libro: Libro, lineas: list, indice: tuple) -> list[dict]:
    """Lo que la respuesta dice de cada movimiento de un asiento: su identidad, su tramo de líneas y su huella.
    Hermano de `por_comprobante`, y los dos salen de `asiento.exportacion_de`."""
    return asi.exportacion_de(libro, lineas, indice)["movimientos"]


def desde_comprobantes(modulo, libro: Libro, comprobantes: list[Comprobante], opciones: Any,
                       config: dict | None = None) -> tuple[bytes, dict]:
    """Un driver de registro de la forma `desde_comprobantes`: el sistema contable que importa su registro y arma
    el asiento él mismo. No hay asiento que armar ni que numerar, pero sí cuentas que llevar: el núcleo exige lo
    que ese destino pide (`contrato.exige`) y lo que su formato no lleva (`no_caben`) ANTES de llamarlo, y el
    driver lee cada cuenta de `asiento.partes_de` y `asiento.cuenta_tercero`, la misma resolución que usa el asiento.
    Sin asiento no hay cuadre ni huella."""
    if config is None:
        raise ValueError(f"El driver {modulo.NOMBRE!r} lleva cuentas: necesita `config`")
    exigir_requisitos(comprobantes, config, libro.rasgos, contrato.exige(modulo))
    fuera = contrato.no_caben(modulo, libro, comprobantes, config)
    if fuera:
        raise contrato.NoCabe(fuera)
    return modulo.desde_comprobantes(libro, comprobantes, config, opciones)


def generar_asiento(doc: dict, *, driver: str, configuracion: dict | None = None, correlativos: dict | None = None,
                    incluir_observados: bool = False, imputacion: dict | None = None, claves_previas: Any = None) -> dict:
    """Un libro -> líneas de diario del estándar, sin formato de ningún ERP.

    Con la configuración del sistema de `driver`, que tiene que armar asientos: sus siglas, sus sub-diarios y las
    columnas en que pone el centro de costo deciden lo que llevan las líneas, que son las mismas de su archivo. Es
    `exportar` sin escribir el archivo, y exige lo mismo; mirar sin exigir es `diagnosticar`.

    **De qué bloque del documento salen las líneas lo dice la tabla** (`libro.rasgos.origen`), y el dispatch ocurre
    aquí y en `salida.exportar_archivo`, una sola vez en cada uno: ni un `if es_tesoreria` más adentro. Un libro de
    compras o de ventas sale de sus `comprobantes` y uno de tesorería de sus `movimientos` (12.9)."""
    modulo = drivers.obtener(driver)
    if not contrato.arma_asientos(modulo):
        con_asientos = [nombre for nombre, m in drivers.DRIVERS.items() if contrato.arma_asientos(m)]
        raise ValueError(f"El driver {driver!r} no arma asientos: las líneas salen con la configuración de uno que "
                         f"sí ({', '.join(con_asientos)})")
    # **El tipo de libro se comprueba ANTES de preparar nada**, igual que en `salida.exportar_archivo` y por el mismo
    # motivo: si no, lo que recibe quien pide el asiento de un libro que ese destino no lleva es «No hay comprobantes
    # que procesar» —porque un libro de tesorería no los trae— y eso es engañoso. La razón verdadera es que ese
    # destino no lleva ese libro, y `drivers.formato_de` ya sabe decirlo nombrando los que sí.
    #
    # `exportar` lo corrigió en la 9.1 y esta puerta se quedó atrás: nadie lo notó porque hasta el 10-oct-2026 no
    # existía ningún libro del catálogo fuera de los dos que todos los drivers llevan.
    libro = libro_de(doc)
    drivers.formato_de(driver, libro.tipo)
    return CAMINOS_DEL_ASIENTO[libro.rasgos.origen](
        doc, modulo, driver, configuracion=configuracion, correlativos=correlativos,
        incluir_observados=incluir_observados, imputacion=imputacion, claves_previas=claves_previas)


def _asiento_de_comprobantes(doc: dict, modulo, driver: str, *, configuracion: dict | None,
                             correlativos: dict | None, incluir_observados: bool, imputacion: dict | None,
                             claves_previas: Any) -> dict:
    """El asiento de un libro que sale de sus comprobantes: una compra, una venta."""
    libro, comprobantes, config = preparar(doc, configuracion, incluir_observados, imputacion, driver, claves_previas)
    # Lo mismo que saldría en su archivo: sin excluidos ni duplicados, sin lo que ese destino no lleva, y exigiendo lo que
    # exige y lo que no cabe en su formato. El desborde de un sub-diario no se lanza aquí: se lee en `sub_diarios`.
    incluidos = seleccionar(comprobantes)
    fuera = fuera_de(incluidos, getattr(modulo, "EXCLUYE_TIPOS", None))
    incluidos = [c for c in incluidos if c not in fuera]
    exigir_requisitos(incluidos, config, libro.rasgos, contrato.exige(modulo))
    no_caben = contrato.no_caben(modulo, libro, incluidos, config)
    if no_caben:
        raise contrato.NoCabe(no_caben)
    corr = asi.correlativos_de_partida(incluidos, config, libro.rasgos, correlativos)
    # Directo a las líneas del asiento: sin pasar por las columnas de ningún ERP.
    neutrales, rangos, indice = asi.lineas_e_indice_del_libro(libro, incluidos, config, corr,
                                                              centro_en_anexo=contrato.centro_en_anexo(modulo, config),
                                                              vocabulario=contrato.vocabulario(modulo))
    return _respuesta(libro, neutrales, rangos, indice)


def _asiento_de_movimientos(doc: dict, modulo, driver: str, *, configuracion: dict | None, **_del_registro) -> dict:
    """El asiento de un libro que sale de sus movimientos: el dinero (12.9).

    `**_del_registro` se traga los cuatro argumentos que solo tienen sentido en el otro camino —los correlativos,
    los observados, la imputación y las claves previas—: las dos funciones de la tabla se llaman igual, y lo que
    una no usa lo dice su firma en vez de obligar a la puerta a saber cuál es cuál.

    **No pasa por `exigir_requisitos` ni por `no_caben`, y no es un olvido.** Las dos están escritas sobre un
    comprobante —`faltantes_para` recorre comprobantes y les pregunta por su tipo, su moneda, su detracción— así
    que llamarlas con una lista vacía devolvería «nada falta» sin haber comprobado nada, que es peor que no
    llamarlas. Lo que le falta a un movimiento para asentarse lo exige el propio asiento, con sus cuatro faltas y
    el mismo trato que `revisar_tesoreria` daba a sus avisos: `MovimientoSinImputar`, `SinCuentaDeEfectivo`,
    `TraspasoEnDosPatas` y `CuentaSinClase`.

    El hueco queda **declarado**: el día que un destino exija algo que valga para una línea de tesorería —el
    candidato es `denominacion`, que mira cuentas y no comprobantes— ese requisito necesita su hermano que recorra
    movimientos. Hoy ninguno de los que exige un driver de serie lo es.

    `correlativos` no llega aquí: con vocabulario neutral el motor no numera, y con uno legacy el libro se para en
    `LibroQueTodaviaNoSeNumera` porque su sub-diario espera el archivo real que lo pida."""
    libro, movimientos, config = preparar_tesoreria(doc, configuracion, driver)
    neutrales, rangos, indice = asi.lineas_e_indice_de_movimientos(libro, movimientos, config,
                                                                  vocabulario=contrato.vocabulario(modulo))
    return _respuesta(libro, neutrales, rangos, indice)


def _asiento_del_diario(doc: dict, modulo, driver: str, *, configuracion: dict | None, **_del_registro) -> dict:
    """El asiento de un libro que **llega ya armado**: el Libro Diario (B13).

    Es el tercer camino y el único que no arma nada. Sus líneas vienen en el bloque `asiento` del documento, que
    el estándar admite de entrada desde la 1.0 y `lineas_de` lee desde la 5.2, y tienen que venir así porque
    armarlas pediría reglas que este motor no tiene: una planilla pide las de la planilla y una depreciación el
    activo y su vida útil. Lo que el motor aporta aquí no es el asiento, es **lo mismo que aporta a los otros
    dos cuando ya existen**: leer cada línea con su contrato —`LineaDiario.de_dict` exige la clase y la verifica
    contra el PCGE—, cuadrarlo, darle su huella y dejarlo listo para cualquier destino.

    **Ni índice ni rangos**, y las dos ausencias son afirmaciones. No hay índice porque no hay entradas aparte
    que indexar: las entradas de este libro son sus propias líneas. Y no hay rangos porque **ya viene numerado**
    —el CUO es de quien lo mandó— y renumerar le cambiaría el número a un asiento que puede estar presentado.
    """
    libro = libro_de(doc)
    dadas = lineas_de(doc)
    if not dadas:
        raise DocumentoInvalido(
            f"Un libro {libro.tipo!r} llega con su asiento ya armado y este documento no trae el bloque "
            "`asiento`. No es que esté vacío: es que de este libro el motor no sabe armar líneas, solo "
            "recibirlas — las de una planilla o una depreciación las produce quien tiene esas reglas.")
    return _respuesta(libro, dadas, {}, ())


def _respuesta(libro: Libro, neutrales: list, rangos: dict, indice: tuple) -> dict:
    """El documento con su bloque `asiento` y `_asiento`, igual venga de comprobantes o de movimientos: lo que sigue
    —cuadrar, hashear, responder— no sabe de cuál de los dos salió, y ésa es la mitad del valor del dispatch."""
    lineas = [ln.a_dict() for ln in neutrales]
    cuadre = partida_doble.cuadra(lineas)
    salida = documento(libro, lineas=lineas)
    salida["_asiento"] = {"lineas": len(lineas), "sub_diarios": dict(rangos), "cuadre": cuadre.a_dict(),
                          "huella": huella(neutrales),
                          **por_entrada(libro, neutrales, indice),
                          "motor": __version__}
    return salida


# **De qué bloque sale el asiento, dicho por la tabla y no por un `if`** (13.1). La clave es el `origen` de la fila
# del libro, no su nombre: por eso hay dos entradas y tres libros, y un libro nuevo que entre por un bloque que ya
# está aquí no añade ninguna. Uno que estrene bloque da `KeyError` en la puerta, que es lo que se quiere — antes
# caía en el `else` y salía tratado como una compra.
#
# Va al final del módulo porque las dos funciones tienen que existir ya; es el único motivo.
CAMINOS_DEL_ASIENTO = {"comprobantes": _asiento_de_comprobantes, "movimientos": _asiento_de_movimientos,
                       "asiento": _asiento_del_diario}
