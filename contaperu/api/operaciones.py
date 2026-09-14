"""Las operaciones de la API: documento `open-accounting` entra, diccionario sale.

Todas son **puras**: no leen disco, no salen a la red, no guardan nada, y la misma entrada da siempre la misma salida.
El documento va primero y todo lo demás por su nombre; las que van hacia un sistema piden `driver`, sin valor por
defecto, porque no hay un destino que se pueda suponer. Los archivos binarios salen en base64 porque un JSON no sabe
llevar bytes; quien los quiera en bytes tiene `exportar_archivo`.
"""
from __future__ import annotations

from typing import Sequence

from .. import _datos, catalogos, comparar_sire as _comparar, drivers, partida_doble, pcge
from ..drivers import contrato
from ..errores import DocumentoInvalido
from ..pipeline import armado, diagnostico, lectura, preparacion, salida
from ..pipeline.salida import Exportado


# --- leer ---------------------------------------------------------------------------

def leer_xml(contenido: str, libro: dict, *, es_base64: bool = False) -> dict:
    """Lee el XML UBL 2.1 de la factura electrónica de SUNAT —uno suelto, o un ZIP con varios— y devuelve un documento
    `open-accounting` revisado. Descarta lo que no es un comprobante (las constancias de recepción y las hojas de
    estilo) y dice en `_lectura` lo que no pudo leer. `libro` es la cabecera: RUC, periodo y si son ventas o compras."""
    return lectura.leer_xml(contenido, libro, es_base64)


def leer_propuesta_sire(contenido: str, libro: dict, *, es_base64: bool = False) -> dict:
    """Lee el TXT de la propuesta que SUNAT entrega en el SIRE —o el ZIP tal cual lo entrega— y devuelve un documento
    `open-accounting` revisado."""
    return lectura.leer_propuesta_sire(contenido, libro, es_base64)


def leer_archivos(archivos: Sequence[tuple[str, bytes | None]], libro: dict) -> dict:
    """Lee varios archivos con su nombre —XML, ZIP, y lo que se ignora: CDR, PDF, fotos— y devuelve un documento
    `open-accounting` revisado. Un archivo que no se pudo abrir llega con `None` y se anota como error. `_lectura`
    dice cuántos se leyeron, cuántos se ignoraron, cuáles fallaron y cuántos PDF o imágenes quedan pendientes."""
    return lectura.leer_archivos(archivos, libro)


# --- revisar ------------------------------------------------------------------------

def revisar(documento: dict, *, configuracion: dict | None = None, imputacion: dict | None = None,
            claves_previas: list | None = None) -> dict:
    """Revisa los comprobantes y devuelve el mismo documento con `estado` y `observaciones` puestos en cada uno, y en
    `_revision` lo que hay que mirar. Descarta las detracciones que la tabla del contribuyente no reconoce. Con
    `imputacion`, comprueba también que cada una hable de un documento que está. `claves_previas` es lo ya anotado en
    otros periodos del mismo RUC, cada una como `[tipo_cp, serie, numero, contraparte_doc]`: lo que coincide sale con
    `DUPLICADO_PERIODO_ANTERIOR` (hasta `MAXIMO_CLAVES_PREVIAS`)."""
    return preparacion.revisar(documento, configuracion, imputacion, claves_previas)


def normalizar_detracciones(documento: dict, *, configuracion: dict | None = None) -> dict:
    """Contrasta la detracción de cada comprobante con la tabla del contribuyente y deja en blanco la que no
    reconozca; `_detracciones` dice cuántas revisó y cuántas descartó. La confusión más común al leer con un modelo de
    lenguaje es tomar la retención del IGV por una detracción."""
    return preparacion.normalizar_detracciones(documento, configuracion)


def diagnosticar(documento: dict, *, driver: str, configuracion: dict | None = None, imputacion: dict | None = None,
                 correlativos: dict | None = None, claves_previas: list | None = None) -> dict:
    """Todo lo que hay que mirar de un mes antes de exportarlo hacia `driver`, en una sola respuesta: si está listo y
    por qué no, qué bloquea, qué falta y a quién pedírselo, qué saldría y desde qué correlativo. No lanza por lo que
    le falte al mes ni por una configuración que no se puede aplicar: lo describe."""
    return diagnostico.diagnosticar(documento, driver=driver, configuracion=configuracion, correlativos=correlativos,
                                    imputacion=imputacion, claves_previas=claves_previas)


# --- asentar y exportar -------------------------------------------------------------

def generar_asiento(documento: dict, *, driver: str, configuracion: dict | None = None,
                    imputacion: dict | None = None, correlativos: dict | None = None,
                    incluir_observados: bool = False, claves_previas: list | None = None) -> dict:
    """Convierte los comprobantes en líneas de diario del estándar, con la configuración del sistema de asientos
    `driver` (sus siglas, sus sub-diarios, las columnas del centro de costo) y sin su formato. `_asiento` trae el
    número de líneas, los rangos por sub-diario, el cuadre y la huella."""
    return armado.generar_asiento(documento, driver=driver, configuracion=configuracion, correlativos=correlativos,
                                  incluir_observados=incluir_observados, imputacion=imputacion,
                                  claves_previas=claves_previas)


def exportar(documento: dict, *, driver: str, configuracion: dict | None = None, imputacion: dict | None = None,
             correlativos: dict | None = None, incluir_observados: bool = False, fecha: str | None = None,
             claves_previas: list | None = None) -> dict:
    """Genera el archivo que importa el sistema `driver` y lo devuelve en JSON: `texto` cuando es legible, el archivo en
    base64 y `_exportacion` con el driver, el archivo, la huella del asiento y la `fecha` que ponga quien llama."""
    return salida.exportar(documento, driver=driver, configuracion=configuracion, correlativos=correlativos,
                           incluir_observados=incluir_observados, fecha=fecha, imputacion=imputacion,
                           claves_previas=claves_previas)


def exportar_archivo(documento: dict, *, driver: str, configuracion: dict | None = None,
                     imputacion: dict | None = None, correlativos: dict | None = None,
                     incluir_observados: bool = False, claves_previas: list | None = None) -> Exportado:
    """Lo mismo que `exportar`, con el archivo en bytes (`Exportado`): para quien lo escribe a disco o lo sirve tal
    cual."""
    return salida.exportar_archivo(documento, driver=driver, configuracion=configuracion, correlativos=correlativos,
                                   incluir_observados=incluir_observados, imputacion=imputacion,
                                   claves_previas=claves_previas)


def cuadrar(lineas: list[dict]) -> dict:
    """¿La suma del Debe es exactamente igual a la del Haber? Devuelve las dos sumas, la diferencia y cuántas líneas no
    dicen si son Debe o Haber."""
    return partida_doble.cuadra(lineas).a_dict()


# --- plan de cuentas ----------------------------------------------------------------

def buscar_cuenta_pcge(*, texto: str = "", codigo: str = "") -> dict:
    """Busca una cuenta del Plan Contable General Empresarial 2026 por nombre (`texto`) o por `codigo`. Un código que no
    está en la norma resuelve a la cuenta madre que lo gobierna: las divisionarias las abre cada empresa."""
    if not codigo and not texto:
        raise DocumentoInvalido("Dime qué buscar: un `texto` del nombre o un `codigo` de cuenta.")
    norma = pcge.catalogo.cargar_catalogo()
    resultado: dict = {"version": norma.get("version", ""), "fuente": norma.get("fuente", "")}
    if codigo:
        resultado["cuenta"] = pcge.resolver(codigo)
    if texto:
        resultado["encontradas"] = pcge.buscar(texto)
    return resultado


def adaptar_pcge(lineas: list[dict]) -> dict:
    """Aplica las equivalencias del PCGE 2026. Sin la tabla oficial cargada no toca nada
    y lo dice: en este proyecto ninguna regla contable se escribe de memoria."""
    adaptadas, informe = pcge.adaptar(lineas)
    return {"asiento": adaptadas, "informe": informe.a_dict()}


# --- configuración ------------------------------------------------------------------

def configuracion_por_defecto() -> dict:
    """La configuración contable de partida, en la forma en que se guarda: lo general en la raíz y una sección por
    sistema que se configura. Es un punto de partida, no la verdad de ningún contribuyente."""
    return preparacion.configuracion_por_defecto()


def describir_configuracion(driver: str | None = None) -> dict:
    """Qué se configura: lo general y, por cada sistema, sus campos con tipo, valor por defecto, patrón y textos, y en
    qué columnas de su archivo puede ir cada dato. Con `driver`, lo general y solo su sección."""
    return preparacion.describir_configuracion(driver or "")


def errores_de_configuracion(configuracion: dict | None) -> list[str]:
    """Lo que la configuración no cumple, un error por línea con su ruta. Lista vacía: se puede aplicar."""
    return preparacion.errores_de_configuracion(configuracion)


# --- lo que el motor sabe -----------------------------------------------------------

def drivers_disponibles() -> dict:
    """Los sistemas a los que se exporta, por nombre: qué libros genera cada uno, su forma, su familia, su canal
    (`legacy`, `tributario` o `intercambio`), lo que exige, si se configura y su descripción."""
    return {
        nombre: {"formatos": modulo.FORMATOS,
                 "tipo": "texto" if contrato.forma(modulo) == "linea" else "archivo",
                 "forma": contrato.forma(modulo),
                 "familia": contrato.familia(modulo),
                 "canal": contrato.canal(modulo),
                 "exige": sorted(contrato.exige(modulo)),
                 "configurable": bool(contrato.seccion_por_defecto(modulo)),
                 "descripcion": ((modulo.__doc__ or "").strip().splitlines() or [""])[0]}
        for nombre, modulo in drivers.DRIVERS.items()
    }


def catalogos_sunat() -> dict:
    """Los catálogos de SUNAT que entiende el motor: tipos de comprobante, tipos de documento de identidad y monedas."""
    return {
        "tipos_comprobante": catalogos.TIPOS_CP,
        "tipos_documento_identidad": catalogos.TIPOS_DOC_IDENTIDAD,
        "monedas": sorted(catalogos.MONEDAS),
        "notas": sorted(catalogos.NOTAS),
        "fuera_del_registro_sunat": sorted(catalogos.FUERA_DEL_REGISTRO_SUNAT),
    }


def catalogo_pcge() -> dict:
    """El catálogo oficial de cuentas del PCGE 2026: cada cuenta con su nombre y la página de la norma que lo dice."""
    return pcge.catalogo.cargar_catalogo()


def esquema_open_accounting() -> dict:
    """El esquema JSON del documento `open-accounting`, con cada campo documentado."""
    return _datos.esquema_open_accounting()


def comparar_sire(nuestro: bytes, sunat: bytes, *, registro: str = "", nombres: Sequence[str] = ()) -> dict:
    """Compara el TXT del SIRE que generó el motor con la exportación del detalle que da SUNAT, por comprobante: qué
    falta, qué sobra y qué no coincide, y en `informe` lo mismo en texto. El registro —`venta` o `compra`— se deduce de
    los `nombres` de los archivos (1404 ventas, 0804 compras) o se fuerza con `registro`."""
    elegido = _comparar.registro_de(list(nombres), registro)
    comparacion = _comparar.comparar(_comparar.leer_bytes(nuestro), _comparar.leer_bytes(sunat), elegido)
    return {**comparacion, "informe": _comparar.informe(comparacion)}
