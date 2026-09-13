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
from . import detracciones, drivers, generar as gen, pcge, partida_doble, validar
from .lectores import archivos as lectura_archivos, sire_txt
from .modelo import Comprobante, Libro

# Ojo: NO se redefine aquí. Era la segunda copia del mismo número.
from ._version import OPEN_ACCOUNTING  # noqa: E402  (constante, no un módulo)

# Tope de seguridad. Un mes de una PYME son decenas o cientos de comprobantes; muchos miles en
# una sola llamada es casi siempre un error de quien llama, y conviene decirlo en vez de
# quedarse pensando.
MAXIMO_COMPROBANTES = 5000


class DocumentoInvalido(ValueError):
    """El documento no cumple el estándar lo bastante como para poder trabajar con él."""


# --- a quién se le pide lo que falta ------------------------------------------------

CONTADOR, SISTEMA, PROVEEDOR = "contador", "sistema", "proveedor"

# Quién resuelve cada cosa que `diagnosticar` puede encontrar. No es una regla contable: las reglas
# ya existen (`validar.py`, `asiento.faltantes_para`); esto solo dice a quién preguntar, para que un
# agente no adivine (la idea viene del *Accounting agent* de Intuit, ver `REFERENCIAS.md`). El criterio:
# **contador** = se decide mirando el documento o el plan de cuentas; **sistema** = configuración del
# destino o un dato público que no está en el papel (el T.C. lo publica SUNAT). **`proveedor` queda
# reservado**: el motor ve un documento y no puede afirmar que lo que falta esté en el papel del
# proveedor; entrará con un caso real (la constancia de detracción conciliada, por ejemplo).
# `tests/test_diagnosticar.py` recorre `validar.py` y comprueba que ningún código se quede fuera.
PEDIR_A: dict[str, str] = {
    # lo que falta para el destino (claves de `faltantes`)
    "sin_cuenta": CONTADOR, "reparto_no_cuadra": CONTADOR, "reparto_no_admitido": CONTADOR,
    "sin_centro_de_costo": CONTADOR, "no_caben": CONTADOR,
    "tipos_sin_equivalencia": SISTEMA, "monedas_sin_codigo": SISTEMA, "sub_diarios_sin_correlativo": SISTEMA,
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

TEXTO_FALTANTE = {
    "sin_cuenta": "sin cuenta contable",
    "reparto_no_cuadra": "con un reparto entre cuentas que no suma la base del asiento",
    "reparto_no_admitido": "con la base repartida entre varias cuentas, que el sistema de destino no admite",
    "sin_centro_de_costo": "sin centro de costo en una cuenta que lo lleva",
    "tipos_sin_equivalencia": "de un tipo sin equivalencia en el sistema de destino",
    "monedas_sin_codigo": "en una moneda que el sistema de destino no admite",
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


def configuracion(contab: dict | None = None) -> dict:
    """La configuración contable efectiva: los valores por defecto con lo del contribuyente
    encima, fundidos en profundidad. Sin argumentos devuelve los de serie.

    Acepta las dos formas, y esto importa: lo que devuelve esta función **se puede volver a
    pasar tal cual**, que es lo que hace cualquiera —persona o agente— al pedir la
    configuración de partida, cambiarle una cuenta y devolverla. La forma anidada
    (`{"concar": {...}}`) existe porque así la guardan las aplicaciones que separan la
    configuración del estudio de la de cada RUC; para eso está `asiento.config_de`, con sus
    tres capas.
    """
    if not contab:
        return asi.config_de(None)
    encima = contab.get("concar") if "concar" in contab else contab
    return asi.merge_config(asi.config_de(None), encima or {})


def con_imputacion(conf: dict, imputacion: dict | None, comprobantes: list[Comprobante]) -> dict:
    """La imputación de cada documento llega APARTE del documento, por `id_externo` (John, 12-sep-2026: las
    cuentas viven en la aplicación, no en el riel). Se lee aquí, en la puerta, para que un error de forma se diga
    con su motivo, y se le entrega al núcleo dentro de la configuración, que es lo que ya recibe todo el asiento.

    Una imputación cuyo `id_externo` no es de ningún documento se rechaza: una llave mal escrita haría salir ese
    documento con la cuenta por defecto, sin error y sin aviso.

    Es pública porque la CLI la usa: escribe los bytes del archivo y por eso llama al núcleo sin pasar por
    `exportar` (ver `cli.py`)."""
    if not imputacion:
        return conf
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
    return {**conf, "imputaciones": leida}


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

def revisar(doc: dict, contab: dict | None = None) -> dict:
    """Aplica las reglas deterministas y devuelve el documento con `estado` y
    `observaciones` puestos, más un resumen de lo que hay que mirar."""
    libro = libro_de(doc)
    comprobantes = comprobantes_de(doc)
    conf = configuracion(contab)
    limpiadas = detracciones.normalizar(comprobantes, conf)
    validar.revisar(comprobantes, libro)
    errores = [c for c in comprobantes if c.tiene_errores]
    avisos = [c for c in comprobantes if c.observaciones and not c.tiene_errores]
    salida = documento(libro, comprobantes)
    salida["_revision"] = {
        "total": len(comprobantes),
        "con_error": len(errores),
        "con_aviso": len(avisos),
        "detracciones_descartadas": len(limpiadas),
        "bloquean_la_exportacion": [
            {"serie_numero": f"{c.serie}-{c.numero}".strip("-"),
             "observaciones": [o.a_dict() for o in c.observaciones if o.nivel == "error"]}
            for c in errores
        ],
    }
    return salida


def cuadrar(lineas: list[dict]) -> dict:
    """¿La suma del Debe es igual a la del Haber?"""
    return partida_doble.cuadra(lineas).a_dict()


# --- asiento y exportación ---------------------------------------------------------

def _preparar(doc: dict, contab: dict | None, incluir_observados: bool, imputacion: dict | None = None):
    libro = libro_de(doc)
    todos = comprobantes_de(doc)
    comprobantes = [c for c in todos if not c.excluida]
    if not comprobantes:
        raise DocumentoInvalido("No hay comprobantes que procesar.")
    conf = con_imputacion(configuracion(contab), imputacion, todos)
    validar.revisar(comprobantes, libro)
    if not incluir_observados:
        con_error = [c for c in comprobantes if c.tiene_errores]
        if con_error:
            raise DocumentoInvalido(
                f"{len(con_error)} comprobantes tienen observaciones que bloquean. "
                "Corrígelos, o pide `incluir_observados` si sabes lo que haces.")
    return libro, comprobantes, conf


def generar_asiento(doc: dict, contab: dict | None = None, correlativos: dict | None = None,
                    incluir_observados: bool = False, imputacion: dict | None = None) -> dict:
    """Comprobantes -> líneas de diario del estándar, sin formato de ningún ERP."""
    libro, comprobantes, conf = _preparar(doc, contab, incluir_observados, imputacion)
    venta = libro.es_venta
    corr = {s: 1 for s in asi.sub_diarios_presentes(comprobantes, conf, venta)}
    corr.update(correlativos or {})
    # Directo a las líneas neutrales: sin pasar por las columnas de ningún ERP.
    neutrales, rangos = asi.lineas_del_libro(libro, comprobantes, conf, corr)
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


def exportar(doc: dict, driver: str = "concar", contab: dict | None = None,
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
    libro, comprobantes, conf = _preparar(doc, contab, incluir_observados, imputacion)
    mod = drivers.obtener(driver)
    # Lo que pide la forma del driver: la configuración, todo el que lleva cuentas (también el registro de un
    # sistema contable); los correlativos, además, el que arma asientos.
    params: dict[str, Any] = {}
    if drivers.contrato.necesita_config(mod):
        params["contab"] = conf
    if drivers.contrato.necesita_asiento(mod):
        corr = {s: 1 for s in asi.sub_diarios_presentes(comprobantes, conf, libro.es_venta)}
        corr.update(correlativos or {})
        params["correlativos"] = corr
    exp = gen.generar(libro, comprobantes, driver, incluir_errores=incluir_observados, **params)

    salida: dict[str, Any] = {
        "driver": driver, "formato": exp.formato, "archivo": exp.nombre,
        "filas": exp.n_filas, "resumen": exp.resumen,
        "_exportacion": {"driver": driver, "archivo": exp.nombre,
                         **({"huella": exp.resumen["huella"]} if exp.resumen.get("huella") else {}),
                         **({"fecha": cuando} if cuando else {})},
    }
    if exp.txt:
        salida["texto"] = exp.txt.decode("utf-8", errors="replace")
        salida["zip_base64"] = base64.b64encode(exp.zip).decode()
        salida["archivo_zip"] = exp.nombre_zip
    else:
        contenido = exp.contenido
        salida["content_type"] = exp.content_type
        if (exp.content_type or "").startswith("text/"):
            salida["texto"] = contenido.decode("utf-8-sig", errors="replace")
        salida["contenido_base64"] = base64.b64encode(contenido).decode()
    return salida


def _serie_numero(c: Comprobante) -> str:
    return f"{c.serie}-{c.numero}".strip("-")


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
    for clave, requisito in asi.REQUISITO_DE.items():
        if requisito not in exige or not faltantes.get(clave):
            continue
        if clave == "tipos_sin_equivalencia":
            cuales = [_serie_numero(c) for c in candidatos if c.tipo_cp in faltantes[clave]]
            texto = f"{TEXTO_FALTANTE[clave]}: {', '.join(faltantes[clave])}"
        elif clave == "monedas_sin_codigo":
            cuales = [_serie_numero(c) for c in candidatos if c.moneda in faltantes[clave]]
            texto = f"{TEXTO_FALTANTE[clave]}: {', '.join(faltantes[clave])}"
        else:
            cuales, texto = list(faltantes[clave]), TEXTO_FALTANTE[clave]
        salida.append({"motivo": clave, "texto": texto, "comprobantes": cuales, "pedir_a": PEDIR_A[clave]})
    for motivo, cuales in (faltantes.get("no_caben") or {}).items():
        salida.append({"motivo": "no_caben", "texto": motivo, "comprobantes": cuales, "pedir_a": PEDIR_A["no_caben"]})
    return salida


def diagnosticar(doc: dict, contab: dict | None = None, correlativos: dict | None = None,
                 driver: str = "concar", imputacion: dict | None = None) -> dict:
    """Todo lo que hay que mirar de un mes ANTES de exportarlo, en una sola respuesta.

    Es la operación pensada para un agente —o para una persona con prisa—: en vez de lanzar la
    exportación y ver qué excepción salta a mitad de camino, responde de una vez qué bloquea, qué
    falta y qué saldría. No añade ninguna regla contable: reúne comprobaciones que ya existen
    (`validar.revisar`, `filas_sin_cuenta`, `filas_sin_centro`, `tipos_sin_mapa`,
    `monedas_sin_codigo`, la numeración por sub-diario) y las cuenta por su serie-número.

    Pura y sin estado. **No lanza** por lo que le falte al mes: lo describe. Solo rechaza un
    documento que no es un documento (sin `libro`, o comprobantes ilegibles).
    """
    libro = libro_de(doc)
    todos = comprobantes_de(doc)
    conf = con_imputacion(configuracion(contab), imputacion, todos)
    detracciones.normalizar(todos, conf)
    validar.revisar(todos, libro)
    mod = drivers.obtener(driver)
    venta = libro.es_venta
    # Lo que ESE destino exige (`contrato.exige`): decide qué faltante deja el mes «no listo». El CSV
    # no exige centro ni moneda con código; CONCAR, los dos; el SIRE, nada de esto.
    exige = drivers.contrato.exige(mod)

    excluidos = [c for c in todos if c.excluida]
    fuera = gen.fuera_de([c for c in todos if not c.excluida], getattr(mod, "EXCLUYE_TIPOS", None))
    candidatos = [c for c in todos if not c.excluida and c not in fuera]
    con_error = [c for c in candidatos if c.tiene_errores]
    con_aviso = [c for c in candidatos if c.observaciones and not c.tiene_errores]

    # Lo que pide todo driver que lleva cuentas —los de asientos y el registro de un sistema contable— y el
    # registro tributario (el SIRE) no: la cuenta, el reparto y el centro de cada documento. Y lo que pide solo el
    # que arma asientos: la equivalencia del tipo, el código de la moneda y el correlativo de cada sub-diario.
    faltantes: dict[str, Any] = {}
    sub_diarios: dict[str, Any] = {}
    if drivers.contrato.necesita_config(mod):
        faltantes = {
            "sin_cuenta": [_serie_numero(c) for c in asi.filas_sin_cuenta(candidatos, conf, venta)],
            "reparto_no_cuadra": [_serie_numero(c) for c in asi.repartos_que_no_cuadran(candidatos, conf, venta)],
            "sin_centro_de_costo": [_serie_numero(c) for c in asi.filas_sin_centro(candidatos, conf, venta)],
        }
        # Lo que solo cuenta para el destino que lo pide: el reparto, si lleva una cuenta por documento, y lo que su
        # formato no puede llevar (`no_caben`). A quien no lo declara no le aparece la clave.
        if "cuenta_unica" in exige:
            faltantes["reparto_no_admitido"] = [_serie_numero(c) for c in asi.con_reparto(candidatos, conf)]
        if callable(getattr(mod, "no_caben", None)):
            faltantes["no_caben"] = {motivo: [_serie_numero(c) for c in lista] for motivo, lista
                                     in drivers.contrato.no_caben(mod, libro, candidatos, conf).items()}
    if drivers.contrato.necesita_asiento(mod):
        sin_mapa = asi.tipos_sin_mapa(candidatos, conf)
        con_mapa = [c for c in candidatos if c.tipo_cp not in sin_mapa]
        presentes = asi.sub_diarios_presentes(con_mapa, conf, venta)
        corr = {s: 1 for s in presentes}
        corr.update(correlativos or {})
        faltantes.update({
            "tipos_sin_equivalencia": sin_mapa,
            "monedas_sin_codigo": asi.monedas_sin_codigo(candidatos, conf),
            "sub_diarios_sin_correlativo": [s for s in presentes if s not in (correlativos or {})],
        })
        etiquetas = asi.etiquetas_sub_diario(conf)
        sub_diarios = {s: {"etiqueta": etiquetas.get(s, s), "comprobantes": n, "empieza_en": corr[s]}
                       for s, n in presentes.items()}

    por_que_no: list[str] = []
    if not candidatos:
        por_que_no.append("no hay comprobantes que exportar")
    if con_error:
        por_que_no.append(f"{len(con_error)} comprobantes con observaciones que bloquean")
    for clave in ("reparto_no_admitido", "sin_cuenta", "reparto_no_cuadra", "sin_centro_de_costo",
                  "tipos_sin_equivalencia", "monedas_sin_codigo"):
        # Solo lo que el destino exige deja el mes «no listo»; lo demás sigue en `faltantes`, informando.
        if faltantes.get(clave) and asi.REQUISITO_DE[clave] in exige:
            por_que_no.append(f"{len(faltantes[clave])} {TEXTO_FALTANTE[clave]}")
    # Lo que no cabe en el formato del destino lo declara el propio driver: siempre bloquea.
    for motivo, cuales in (faltantes.get("no_caben") or {}).items():
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
        "totales": {"comprobantes": len(todos), "saldrian": len(candidatos), "excluidos": len(excluidos),
                    "fuera_del_registro": len(fuera), "con_error": len(con_error), "con_aviso": len(con_aviso)},
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
