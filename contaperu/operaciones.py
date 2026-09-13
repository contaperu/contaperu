"""Operaciones de alto nivel: documento `open-accounting` entra, documento `open-accounting` sale.

Es la capa que consume el servidor MCP, y sirve igual a cualquier aplicación que prefiera
hablar con diccionarios en vez de con los objetos del modelo. Todas las funciones de aquí son
**puras**: no leen disco, no salen a la red, no guardan nada. La misma entrada da siempre la
misma salida.

El contrato es sencillo: los documentos son los del estándar (ver `estandar/LEEME.md`), la
configuración contable del contribuyente y la imputación de cada documento entran por parámetro, y los
archivos binarios salen en base64 porque un JSON no sabe llevar bytes.
"""
from __future__ import annotations

import base64
from datetime import date
from decimal import Decimal
from typing import Any

from . import asiento as asi
from . import configuracion as _declaracion
from . import detracciones, drivers, generar as gen, pcge, partida_doble, validar
from .asiento.faltas import CONTADOR, FALTAS, PROVEEDOR, SISTEMA  # noqa: F401  (PROVEEDOR: reservado)
from .configuracion import CLAVES_RETIRADAS, CONFIG_POR_DEFECTO, CONFIGURACION_GENERAL, ConfiguracionInvalida
from .lectores import archivos as lectura_archivos, sire_txt
from .modelo import Comprobante, Libro, serie_y_numero

# Ojo: NO se redefine aquí. Era la segunda copia del mismo número.
from ._version import OPEN_ACCOUNTING  # noqa: E402  (constante, no un módulo)

# Tope de seguridad. Un mes de una PYME son decenas o cientos de comprobantes; muchos miles en
# una sola llamada es casi siempre un error de quien llama, y conviene decirlo en vez de
# quedarse pensando.
MAXIMO_COMPROBANTES = 5000


class DocumentoInvalido(ValueError):
    """El documento no cumple el estándar lo bastante como para poder trabajar con él."""


# --- a quién se le pide lo que falta ------------------------------------------------

# Quién resuelve cada cosa que `diagnosticar` puede encontrar. No es una regla contable: las reglas
# ya existen (`validar.py`, `asiento.faltantes_para`); esto solo dice a quién preguntar, para que un
# agente no adivine (la idea viene del *Accounting agent* de Intuit, ver `REFERENCIAS.md`). El criterio:
# **contador** = se decide mirando el documento o el plan de cuentas; **sistema** = configuración del
# destino o un dato público que no está en el papel (el T.C. lo publica SUNAT). **`proveedor` queda
# reservado**: el motor ve un documento y no puede afirmar que lo que falta esté en el papel del
# proveedor; entrará con un caso real (la constancia de detracción conciliada, por ejemplo).
# `tests/test_diagnosticar.py` recorre `validar.py` y comprueba que ningún código se quede fuera.
PEDIR_A: dict[str, str] = {
    # lo que falta para el destino (claves de `faltantes`): lo dice su tabla, `asiento.FALTAS`
    **{falta.clave: falta.pedir_a for falta in FALTAS},
    # una configuración que no cumple lo declarado se arregla donde se configura
    "configuracion_invalida": SISTEMA,
    # errores de la validación
    "ANIO_DUA_FALTA": CONTADOR, "CONTRAPARTE_FALTA": CONTADOR, "DNI_INVALIDO": CONTADOR,
    "DSCTO_MAYOR_QUE_BASE": CONTADOR, "DUPLICADO": CONTADOR, "DUPLICADO_PERIODO_ANTERIOR": CONTADOR,
    "FECHA_FALTA": CONTADOR, "FECHA_POSTERIOR": CONTADOR, "IGV_NO_CUADRA": CONTADOR,
    "MONEDA_INVALIDA": CONTADOR, "NOTA_SIN_FECHA_REF": CONTADOR, "NOTA_SIN_REFERENCIA": CONTADOR,
    "NUMERO_FALTA": CONTADOR, "RETENCION_MAYOR": CONTADOR, "RUC_INVALIDO": CONTADOR, "SERIE_FALTA": CONTADOR,
    "TC_FALTA": SISTEMA, "TOTAL_NO_CUADRA": CONTADOR, "VENCIMIENTO_FALTA": CONTADOR,
    "XML_DE_OTRO_RUC": CONTADOR, "XML_PARA_OTRO_RUC": CONTADOR,
    # avisos (no bloquean; están para que la tabla sea completa)
    "ADQUIRENTE_NO_COINCIDE": CONTADOR, "ANTICIPO": CONTADOR, "BOLETA_SIN_DOC": CONTADOR,
    "COMPRA_BOLETA": CONTADOR, "CREDITO_FISCAL_FUERA_DE_PLAZO": CONTADOR, "DETRACCION_TASA_DISTINTA": CONTADOR,
    "EMISOR_NO_COINCIDE": CONTADOR, "GRATUITAS": CONTADOR, "IGV_TASA_REDUCIDA": CONTADOR, "NOMBRE_FALTA": CONTADOR,
    "PERIODO_ANTERIOR": CONTADOR, "RETENCION_NO_APLICA": CONTADOR, "RETENCION_TASA": CONTADOR,
    "SIRE_SIN_DETALLE": CONTADOR, "TIPO_CP_DESCONOCIDO": CONTADOR, "TOTAL_CERO": CONTADOR,
}


# --- conversión entre el estándar y el modelo --------------------------------------

def libro_de(doc: dict) -> Libro:
    datos = doc.get("libro")
    if not isinstance(datos, dict):
        raise DocumentoInvalido("Falta el bloque `libro`: sin RUC, periodo y tipo no hay contabilidad.")
    try:
        return Libro(ruc=datos.get("ruc", ""), razon_social=datos.get("razon_social", ""),
                     periodo=datos.get("periodo", ""), tipo=datos.get("tipo", ""))
    except ValueError as e:
        raise DocumentoInvalido(str(e)) from None


def comprobantes_de(doc: dict) -> list[Comprobante]:
    crudos = doc.get("comprobantes") or []
    if not isinstance(crudos, list):
        raise DocumentoInvalido("`comprobantes` tiene que ser una lista.")
    if len(crudos) > MAXIMO_COMPROBANTES:
        raise DocumentoInvalido(
            f"{len(crudos)} comprobantes en una sola llamada; el tope es {MAXIMO_COMPROBANTES}. "
            "Divídelo por periodo o por lote.")
    try:
        return [Comprobante.de_dict(c) for c in crudos]
    except (ValueError, TypeError) as e:
        raise DocumentoInvalido(f"Un comprobante no se pudo leer: {e}") from None


def documento(libro: Libro, comprobantes: list[Comprobante] | None = None,
              lineas: list[dict] | None = None, **extra) -> dict:
    """Arma un documento `open-accounting` con lo que se le dé."""
    doc: dict[str, Any] = {
        "open_accounting": OPEN_ACCOUNTING,
        "libro": {"ruc": libro.ruc, "razon_social": libro.razon_social,
                  "periodo": libro.periodo, "tipo": libro.tipo},
    }
    if comprobantes is not None:
        doc["comprobantes"] = [c.a_dict() for c in comprobantes]
    if lineas is not None:
        doc["asiento"] = lineas
    doc.update(extra)
    return doc


def errores_de_configuracion(configuracion: dict | None) -> list[str]:
    """Lo que la configuración no cumple, un error por línea con su ruta; lista vacía = se puede aplicar.

    Se valida entera: lo general contra lo que declara el motor y cada sección contra lo que declara su driver, también
    la de un sistema al que hoy no se exporta, porque una clave mal escrita ahí se descubriría el día que se use. Una
    clave de un sistema puesta en la raíz —la forma plana de antes del 13-sep-2026— dice a qué sección va, y una
    retirada, qué la reemplaza."""
    if configuracion is None:
        return []
    if not isinstance(configuracion, dict):
        return _declaracion.validar(configuracion, CONFIGURACION_GENERAL)
    generales = [c.clave for c in CONFIGURACION_GENERAL]
    sistemas = {nombre: modulo for nombre, modulo in drivers.DRIVERS.items() if drivers.contrato.lleva_cuentas(modulo)}
    va_en: dict[str, list[str]] = {}
    for nombre, modulo in sistemas.items():
        for campo in drivers.contrato.configuracion(modulo):
            va_en.setdefault(campo.clave, []).append(nombre)
        if drivers.contrato.columnas_elegibles(modulo):
            va_en.setdefault("columnas", []).append(nombre)
    errores: list[str] = []
    for clave, valor in configuracion.items():
        if clave in generales:
            errores += _declaracion.validar({clave: valor}, CONFIGURACION_GENERAL)
        elif clave in sistemas:
            errores += _declaracion.validar(valor, drivers.contrato.configuracion(sistemas[clave]),
                                            drivers.contrato.columnas_elegibles(sistemas[clave]), donde=clave)
        elif clave in CLAVES_RETIRADAS:
            errores.append(f"`{clave}` ya no existe: es {CLAVES_RETIRADAS[clave]}")
        elif clave in va_en:
            errores.append(f"`{clave}` va dentro de la sección de su sistema ({' o '.join(va_en[clave])}), "
                           "no en la raíz")
        elif clave == "imputaciones":
            errores.append("`imputaciones` no va en la configuración: la imputación de cada documento llega aparte "
                           "(`imputacion`)")
        elif clave in drivers.DRIVERS:
            errores.append(f"`{clave}` no tiene sección: ese sistema no lleva cuentas y no se configura")
        else:
            errores.append(f"`{clave}`: clave desconocida; en la raíz va lo general ({', '.join(generales)}) y una "
                           f"sección por sistema ({', '.join(sistemas)})")
    return errores


def config_aplicada(configuracion: dict | None = None, driver: str = "") -> dict:
    """La configuración con la que se genera hacia `driver`: lo general con sus valores por defecto debajo, y encima la
    sección de ese sistema con los suyos, todo plano, como lo lee el núcleo. Sin `driver` —o con uno que no lleva
    cuentas, como el SIRE—, solo lo general.

    Se guarda con lo general en la raíz y una sección por sistema (John, 13-sep-2026): `{"cuentas": {...},
    "concar": {"tipos": {...}, "columnas": {...}}, "contasis": {"medio_pago": "003"}}`, fundida en profundidad sobre
    los valores por defecto (una empresa puede cambiar solo `cuentas.cxp.USD` y hereda el resto). Se valida entera
    (`errores_de_configuracion`) y un error la detiene con `ConfiguracionInvalida`: una clave que nadie lee exportaría
    con el valor de fábrica sin avisar. Lo que devuelve es para generar; la forma que se guarda, con sus valores por
    defecto, la da `configuracion_por_defecto`."""
    errores = errores_de_configuracion(configuracion)
    if errores:
        raise ConfiguracionInvalida(errores)
    guardada = configuracion or {}
    aplicada = asi.fundir_config(CONFIG_POR_DEFECTO, {k: v for k, v in guardada.items() if k not in drivers.DRIVERS})
    if not driver:
        return aplicada
    modulo = drivers.obtener(driver)
    return {**aplicada, **asi.fundir_config(drivers.contrato.seccion_por_defecto(modulo), guardada.get(driver) or {})}


def configuracion_por_defecto() -> dict:
    """La configuración de partida en la forma en que se guarda: lo general y la sección de cada sistema que se
    configura, con sus valores por defecto. Se puede cambiar y volver a pasar tal cual."""
    salida = asi.fundir_config(CONFIG_POR_DEFECTO, {})
    for nombre, modulo in drivers.DRIVERS.items():
        seccion = drivers.contrato.seccion_por_defecto(modulo)
        if seccion:
            salida[nombre] = seccion
    return salida


def con_imputacion(config: dict, imputacion: dict | None, comprobantes: list[Comprobante]) -> dict:
    """La imputación de cada documento llega APARTE del documento, por `id_externo` (John, 12-sep-2026: las
    cuentas viven en la aplicación, no en el riel). Se lee aquí, en la puerta, para que un error de forma se diga
    con su motivo, y se le entrega al núcleo dentro de la configuración, que es lo que ya recibe todo el asiento.

    Una imputación cuyo `id_externo` no es de ningún documento se rechaza: una llave mal escrita haría salir ese
    documento con la cuenta por defecto, sin error y sin aviso.

    Es pública porque la CLI la usa: escribe los bytes del archivo y por eso llama al núcleo sin pasar por
    `exportar` (ver `cli.py`)."""
    if not imputacion:
        return config
    if not isinstance(imputacion, dict):
        raise DocumentoInvalido("`imputacion` es un objeto: {id_externo: {cuenta_contable, centro_costo, "
                                "cuenta_tercero, reparto}}.")
    try:
        leida = {str(k): asi.Imputacion.de(v) for k, v in imputacion.items()}
    except ValueError as e:
        raise DocumentoInvalido(f"Una imputación no se pudo leer: {e}") from None
    huerfanas = sorted(set(leida) - {(c.id_externo or "").strip() for c in comprobantes})
    if huerfanas:
        raise DocumentoInvalido("La imputación habla de documentos que no están (id_externo): "
                                + ", ".join(huerfanas) + ".")
    return {**config, "imputaciones": leida}


# --- lectura -----------------------------------------------------------------------

def _bytes_de(contenido: str, es_base64: bool) -> bytes:
    if es_base64:
        try:
            return base64.b64decode(contenido, validate=True)
        except Exception as e:
            raise DocumentoInvalido(f"El contenido no es base64 válido: {e}") from None
    return contenido.encode("utf-8")


def _nombre_de(datos: bytes) -> str:
    """Un nombre coherente con lo que los bytes dicen que es. Lo que llega por el protocolo no
    tiene nombre de archivo, y el lector clasifica por extension o por bytes magicos."""
    return "entrada.zip" if datos[:4] == b"PK" else "comprobante.xml"


def leer_xml(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """XML UBL 2.1 de SUNAT (uno, o un ZIP con varios) -> documento `open-accounting`."""
    lib = libro_de({"libro": libro})
    datos = _bytes_de(contenido, es_base64)
    lote = lectura_archivos.Lote()
    # El nombre NO decide si es un ZIP: lo deciden los bytes. Llamarlo ".zip" hacia que un
    # XML suelto en base64 —lo natural desde un agente— se rechazara como "ZIP danado".
    lectura_archivos.expandir(_nombre_de(datos), datos, lote=lote)
    res = lectura_archivos.convertir_xml(lote, lib)
    comprobantes = lectura_archivos.ordenar(res.comprobantes)
    validar.revisar(comprobantes, lib)
    return documento(lib, comprobantes,
                     _lectura={"ignorados": len(res.ignorados), "errores": res.errores,
                               "pendientes_de_leer": len(res.pendientes_ia)})


def leer_propuesta_sire(contenido: str, libro: dict, es_base64: bool = False) -> dict:
    """El TXT (o el ZIP) de la propuesta que entrega SUNAT -> documento `open-accounting`."""
    lib = libro_de({"libro": libro})
    comprobantes = sire_txt.parsear(_bytes_de(contenido, es_base64), lib)
    comprobantes = lectura_archivos.ordenar(comprobantes)
    validar.revisar(comprobantes, lib)
    return documento(lib, comprobantes)


# --- validación --------------------------------------------------------------------

def revisar(doc: dict, configuracion: dict | None = None) -> dict:
    """Aplica las reglas deterministas y devuelve el documento con `estado` y
    `observaciones` puestos, más un resumen de lo que hay que mirar."""
    libro = libro_de(doc)
    comprobantes = comprobantes_de(doc)
    config = config_aplicada(configuracion)
    limpiadas = detracciones.normalizar(comprobantes, config)
    validar.revisar(comprobantes, libro)
    errores = [c for c in comprobantes if c.tiene_errores]
    avisos = [c for c in comprobantes if c.observaciones and not c.tiene_errores]
    salida = documento(libro, comprobantes)
    salida["_revision"] = {
        "comprobantes": len(comprobantes),
        "con_error": len(errores),
        "con_aviso": len(avisos),
        "detracciones_descartadas": len(limpiadas),
        "bloqueantes": [
            {"serie_numero": _serie_numero(c),
             "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "error"]}
            for c in errores
        ],
    }
    return salida


def cuadrar(lineas: list[dict]) -> dict:
    """¿La suma del Debe es igual a la del Haber?"""
    return partida_doble.cuadra(lineas).a_dict()


# --- asiento y exportación ---------------------------------------------------------

def _preparar(doc: dict, configuracion: dict | None, incluir_observados: bool, imputacion: dict | None = None,
              driver: str = ""):
    libro = libro_de(doc)
    todos = comprobantes_de(doc)
    comprobantes = [c for c in todos if not c.excluida]
    if not comprobantes:
        raise DocumentoInvalido("No hay comprobantes que procesar.")
    config = con_imputacion(config_aplicada(configuracion, driver), imputacion, todos)
    validar.revisar(comprobantes, libro)
    if not incluir_observados:
        con_error = [c for c in comprobantes if c.tiene_errores]
        if con_error:
            raise DocumentoInvalido(
                f"{len(con_error)} comprobantes tienen observaciones que bloquean. "
                "Corrígelos, o pide `incluir_observados` si sabes lo que haces.")
    return libro, comprobantes, config


def generar_asiento(doc: dict, configuracion: dict | None = None, correlativos: dict | None = None,
                    incluir_observados: bool = False, imputacion: dict | None = None, driver: str = "concar") -> dict:
    """Comprobantes -> líneas de diario del estándar, sin formato de ningún ERP.

    Con la configuración del sistema de `driver`, que tiene que armar asientos: sus siglas, sus sub-diarios y las
    columnas en que pone el centro de costo deciden lo que llevan las líneas, que son las mismas de su archivo."""
    modulo = drivers.obtener(driver)
    if not drivers.contrato.arma_asientos(modulo):
        con_asientos = [nombre for nombre, m in drivers.DRIVERS.items() if drivers.contrato.arma_asientos(m)]
        raise ValueError(f"El driver {driver!r} no arma asientos: las líneas salen con la configuración de uno que "
                         f"sí ({', '.join(con_asientos)})")
    libro, comprobantes, config = _preparar(doc, configuracion, incluir_observados, imputacion, driver)
    es_venta = libro.es_venta
    corr = asi.correlativos_de_partida(comprobantes, config, es_venta, correlativos)
    # Directo a las líneas neutrales: sin pasar por las columnas de ningún ERP.
    neutrales, rangos = asi.lineas_del_libro(libro, comprobantes, config, corr,
                                             centro_en_anexo=drivers.contrato.centro_en_anexo(modulo, config))
    lineas = [ln.a_dict() for ln in neutrales]
    cuadre = partida_doble.cuadra(lineas)
    salida = documento(libro, lineas=lineas)
    salida["_asiento"] = {"lineas": len(lineas), "sub_diarios": dict(rangos), "cuadre": cuadre.a_dict(),
                          "huella": asi.huella(neutrales)}
    return salida


def _fecha_de(fecha: str | None) -> str | None:
    """La fecha de una exportación la pone quien llama —el núcleo no mira el reloj— y solo se
    comprueba que sea una fecha (`AAAA-MM-DD`): es una anotación, no un dato contable."""
    if fecha in (None, ""):
        return None
    try:
        return date.fromisoformat(str(fecha)).isoformat()
    except ValueError:
        raise DocumentoInvalido(f"`fecha` tiene que ser AAAA-MM-DD, no {fecha!r}.") from None


def exportar(doc: dict, driver: str = "concar", configuracion: dict | None = None,
             correlativos: dict | None = None, incluir_observados: bool = False,
             fecha: str | None = None, imputacion: dict | None = None) -> dict:
    """Genera el archivo que pide un sistema contable.

    El resultado trae `texto` cuando la salida es legible (el TXT del SIRE, el CSV) y
    `contenido_base64` cuando son bytes (el Excel de CONCAR). Siempre trae el nombre de archivo
    que el destino espera, y `_exportacion`: el driver, el archivo, la **huella** del asiento que
    salió (solo en los drivers de asientos; `asiento/huella.py`) y la `fecha` si quien llama la dio.
    Es la anotación con la que un productor reconoce una tanda que ya exportó (`REFERENCIAS.md`).
    """
    cuando = _fecha_de(fecha)
    libro, comprobantes, config = _preparar(doc, configuracion, incluir_observados, imputacion, driver)
    modulo = drivers.obtener(driver)
    # Lo que pide la forma del driver: la configuración, todo el que lleva cuentas (también el registro de un
    # sistema contable); los correlativos, además, el que arma asientos.
    corr = None
    if drivers.contrato.arma_asientos(modulo):
        corr = asi.correlativos_de_partida(comprobantes, config, libro.es_venta, correlativos)
    exp = gen.generar(libro, comprobantes, driver, incluir_errores=incluir_observados,
                      config=config if drivers.contrato.lleva_cuentas(modulo) else None, correlativos=corr)

    salida: dict[str, Any] = {
        "driver": driver, "formato": exp.formato, "archivo": exp.nombre,
        "comprobantes": exp.comprobantes, "resumen": exp.resumen,
        "_exportacion": {"driver": driver, "archivo": exp.nombre,
                         **({"huella": exp.resumen["huella"]} if exp.resumen.get("huella") else {}),
                         **({"fecha": cuando} if cuando else {})},
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


def _serie_numero(c: Comprobante) -> str:
    return serie_y_numero(c.serie, c.numero)


def _detraccion_pendiente(c: Comprobante) -> bool:
    """¿La detracción de este comprobante espera todavía su constancia del Banco de la Nación?

    El estándar define `detraccion.estado` (PROVISIONADO | PAGADO) y `nro_constancia`, pero hoy
    ningún lector los escribe —la conciliación de constancias está pendiente de un archivo real—,
    así que «pendiente» se lee de la forma más honesta: no está PAGADO y no hay constancia. Un
    productor que sí los rellene obtiene la respuesta correcta sin cambiar nada aquí.
    """
    d = c.detraccion if isinstance(c.detraccion, dict) else None
    if not d or not asi.tiene_detraccion(c):
        return False
    return str(d.get("estado") or "").upper() != "PAGADO" and not str(d.get("nro_constancia") or "").strip()


def _que_falta(con_error: list[Comprobante], candidatos: list[Comprobante], faltantes: dict,
               exige: frozenset[str]) -> list[dict]:
    """Lo que bloquea la exportación a ESE destino, agrupado por motivo y con a quién pedírselo.

    Un agente redacta «faltan cuentas contables en E001-871 y E001-872», no dos preguntas: por eso va
    por motivo. Solo lo que bloquea: los errores de la validación y los faltantes que el driver exige.
    """
    salida: list[dict] = []
    por_codigo: dict[str, list[str]] = {}
    textos: dict[str, str] = {}
    for c in con_error:
        for o in c.observaciones:
            if o.nivel == "error":
                por_codigo.setdefault(o.codigo, []).append(_serie_numero(c))
                textos.setdefault(o.codigo, o.texto)
    for codigo in sorted(por_codigo):
        salida.append({"motivo": codigo, "texto": textos[codigo], "comprobantes": por_codigo[codigo],
                       "pedir_a": PEDIR_A.get(codigo, CONTADOR)})
    for falta in FALTAS:
        clave = falta.clave
        if not falta.requisito or falta.requisito not in exige or not faltantes.get(clave):
            continue
        if clave == "sin_sigla":
            cuales = [_serie_numero(c) for c in candidatos if c.tipo_cp in faltantes[clave]]
            texto = f"{falta.texto}: {', '.join(faltantes[clave])}"
        elif clave == "sin_codigo_de_moneda":
            cuales = [_serie_numero(c) for c in candidatos if c.moneda in faltantes[clave]]
            texto = f"{falta.texto}: {', '.join(faltantes[clave])}"
        else:
            cuales, texto = list(faltantes[clave]), falta.texto
        salida.append({"motivo": clave, "texto": texto, "comprobantes": cuales, "pedir_a": falta.pedir_a})
    for motivo, cuales in (faltantes.get("no_cabe") or {}).items():
        salida.append({"motivo": "no_cabe", "texto": motivo, "comprobantes": cuales, "pedir_a": PEDIR_A["no_cabe"]})
    return salida


def _sin_configuracion(libro: Libro, driver: str, exige: frozenset[str], todos: list[Comprobante],
                       errores: list[str]) -> dict:
    """El diagnóstico de un mes cuya configuración no se puede aplicar: sin ella no hay nada que medir, así que dice eso
    —cada error con su ruta— y a quién pedírselo, con la forma de siempre."""
    return {
        "libro": {"ruc": libro.ruc, "periodo": libro.periodo, "tipo": libro.tipo},
        "driver": driver,
        "exige": sorted(exige),
        "listo_para_exportar": False,
        "por_que_no": [f"la configuración tiene {len(errores)} {'error' if len(errores) == 1 else 'errores'}"],
        "que_falta": [{"motivo": "configuracion_invalida", "comprobantes": [],
                       "texto": "la configuración no cumple lo que declaran el motor y su sistema",
                       "pedir_a": PEDIR_A["configuracion_invalida"]}],
        "errores_de_configuracion": errores,
        "totales": {"comprobantes": len(todos), "saldrian": 0, "excluidos": sum(1 for c in todos if c.excluida),
                    "fuera_del_destino": 0, "con_error": 0, "con_aviso": 0},
        "bloqueantes": [], "avisos": [], "faltantes": {}, "detracciones_pendientes": [],
        "resumen_por_contraparte": {}, "sub_diarios": {}, "saldrian": [],
    }


def diagnosticar(doc: dict, configuracion: dict | None = None, correlativos: dict | None = None,
                 driver: str = "concar", imputacion: dict | None = None) -> dict:
    """Todo lo que hay que mirar de un mes ANTES de exportarlo, en una sola respuesta.

    Es la operación pensada para un agente —o para una persona con prisa—: en vez de lanzar la
    exportación y ver qué excepción salta a mitad de camino, responde de una vez qué bloquea, qué
    falta y qué saldría. No añade ninguna regla contable: reúne comprobaciones que ya existen
    (`validar.revisar`, `comprobantes_sin_cuenta`, `comprobantes_sin_centro`, `tipos_sin_sigla`,
    `monedas_sin_codigo`, la numeración por sub-diario) y las cuenta por su serie-número.

    Pura y sin estado. **No lanza** por lo que le falte al mes: lo describe. Tampoco por una
    configuración que no se puede aplicar: la dice en `errores_de_configuracion`. Solo rechaza un
    documento que no es un documento (sin `libro`, o comprobantes ilegibles).
    """
    libro = libro_de(doc)
    todos = comprobantes_de(doc)
    modulo = drivers.obtener(driver)
    # Lo que ESE destino exige (`contrato.exige`): decide qué faltante deja el mes «no listo». El CSV
    # no exige centro ni moneda con código; CONCAR, los dos; el SIRE, nada de esto.
    exige = drivers.contrato.exige(modulo)
    errores = errores_de_configuracion(configuracion)
    if errores:
        return _sin_configuracion(libro, driver, exige, todos, errores)
    config = con_imputacion(config_aplicada(configuracion, driver), imputacion, todos)
    detracciones.normalizar(todos, config)
    validar.revisar(todos, libro)
    es_venta = libro.es_venta

    excluidos = [c for c in todos if c.excluida]
    fuera = gen.fuera_de([c for c in todos if not c.excluida], getattr(modulo, "EXCLUYE_TIPOS", None))
    candidatos = [c for c in todos if not c.excluida and c not in fuera]
    con_error = [c for c in candidatos if c.tiene_errores]
    con_aviso = [c for c in candidatos if c.observaciones and not c.tiene_errores]

    # Lo que se mira: lo que ese destino exige y, además, lo que solo informa —la cuenta y el centro a todo el que lleva
    # cuentas, el tipo y la moneda al que arma asientos—, con la misma regla que hace cumplir el núcleo
    # (`asiento.faltantes_para`). El reparto que un destino no admite aparece solo si lo exige, y lo que su formato no
    # puede llevar, si el driver lo declara (`no_caben`).
    mirar = set(exige)
    if drivers.contrato.lleva_cuentas(modulo):
        mirar |= {"cuenta_contable", "centro_costo"}
    if drivers.contrato.arma_asientos(modulo):
        mirar |= {"tipo_cp", "moneda"}
    codigos = ("sin_sigla", "sin_codigo_de_moneda")      # se dicen por su código, no por comprobante
    faltantes: dict[str, Any] = {clave: cuales if clave in codigos else [_serie_numero(c) for c in cuales]
                                 for clave, cuales in asi.faltantes_para(candidatos, config, es_venta, mirar).items()}
    if drivers.contrato.lleva_cuentas(modulo) and callable(getattr(modulo, "no_caben", None)):
        faltantes["no_cabe"] = {motivo: [_serie_numero(c) for c in lista] for motivo, lista
                                 in drivers.contrato.no_caben(modulo, libro, candidatos, config).items()}
    sub_diarios: dict[str, Any] = {}
    if drivers.contrato.arma_asientos(modulo):
        con_equivalencia = [c for c in candidatos if c.tipo_cp not in faltantes["sin_sigla"]]
        presentes = asi.sub_diarios_presentes(con_equivalencia, config, es_venta)
        corr = asi.correlativos_de_partida(con_equivalencia, config, es_venta, correlativos)
        faltantes["sin_correlativo"] = [s for s in presentes if s not in (correlativos or {})]
        etiquetas = asi.etiquetas_sub_diario(config)
        sub_diarios = {s: {"etiqueta": etiquetas.get(s, s), "comprobantes": n, "empieza_en": corr[s]}
                       for s, n in presentes.items()}

    por_que_no: list[str] = []
    if not candidatos:
        por_que_no.append("no hay comprobantes que exportar")
    if con_error:
        por_que_no.append(f"{len(con_error)} comprobantes con observaciones que bloquean")
    for falta in FALTAS:
        # Solo lo que el destino exige deja el mes «no listo»; lo demás sigue en `faltantes`, informando.
        if falta.requisito in exige and faltantes.get(falta.clave):
            por_que_no.append(f"{len(faltantes[falta.clave])} {falta.texto}")
    # Lo que no cabe en el formato del destino lo declara el propio driver: siempre bloquea.
    for motivo, cuales in (faltantes.get("no_cabe") or {}).items():
        por_que_no.append(f"{len(cuales)} {motivo}")

    por_contraparte: dict[str, dict] = {}
    for c in candidatos:
        clave = c.contraparte_doc or "(sin documento)"
        r = por_contraparte.setdefault(clave, {"nombre": c.contraparte_nombre, "comprobantes": 0,
                                               "total": Decimal("0.00"), "moneda": c.moneda})
        r["comprobantes"] += 1
        r["total"] += c.total if not c.es_nota_credito else -c.total
    for r in por_contraparte.values():
        r["total"] = str(r["total"])

    return {
        "libro": {"ruc": libro.ruc, "periodo": libro.periodo, "tipo": libro.tipo},
        "driver": driver,
        "exige": sorted(exige),
        "listo_para_exportar": not por_que_no,
        "por_que_no": por_que_no,
        "que_falta": _que_falta(con_error, candidatos, faltantes, exige),
        "errores_de_configuracion": [],
        "totales": {"comprobantes": len(todos), "saldrian": len(candidatos), "excluidos": len(excluidos),
                    "fuera_del_destino": len(fuera), "con_error": len(con_error), "con_aviso": len(con_aviso)},
        "bloqueantes": [{"serie_numero": _serie_numero(c),
                         "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "error"]}
                        for c in con_error],
        "avisos": [{"serie_numero": _serie_numero(c),
                    "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "aviso"]}
                   for c in con_aviso],
        "faltantes": faltantes,
        "detracciones_pendientes": [
            {"serie_numero": _serie_numero(c), "codigo": str((c.detraccion or {}).get("codigo") or ""),
             "monto": str((c.detraccion or {}).get("monto") or "")}
            for c in candidatos if _detraccion_pendiente(c)],
        "resumen_por_contraparte": por_contraparte,
        "sub_diarios": sub_diarios,
        "saldrian": [_serie_numero(c) for c in candidatos if not c.tiene_errores],
    }


def adaptar_pcge(lineas: list[dict]) -> dict:
    """Aplica las equivalencias del PCGE 2026. Sin la tabla oficial cargada no toca nada
    y lo dice: en este proyecto ninguna regla contable se escribe de memoria."""
    salida, informe = pcge.adaptar(lineas)
    return {"asiento": salida, "informe": informe.a_dict()}
