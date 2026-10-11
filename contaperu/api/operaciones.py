"""Las operaciones de la API: documento `open-accounting` entra, diccionario sale.

Todas son **puras**: no leen disco, no salen a la red, no guardan nada, y la misma entrada da siempre la misma salida.
El documento va primero y todo lo demás por su nombre; las que van hacia un sistema piden `driver`, sin valor por
defecto, porque no hay un destino que se pueda suponer. Los archivos binarios salen en base64 porque un JSON no sabe
llevar bytes; quien los quiera en bytes tiene `exportar_archivo`.
"""
from __future__ import annotations

import importlib
from typing import Any, Sequence

from .. import (_datos, catalogos, drivers, modelo, pcge, tesoreria,
                vocabulario)
from ..drivers import contrato
from ..contable import partida_doble
from ..contable import resumen as _resumen
from ..drivers.kit import rol
from ..modelo.libro import rasgos_de
from ..tributos import comparar_sire as _comparar
from ..tributos import detracciones
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
    `driver` (sus siglas, sus sub-diarios, las columnas del centro de costo) y sin su formato. Es `exportar` sin
    escribir el archivo: exige lo que exige ese destino y lo que no cabe en su formato. `_asiento` trae el número de
    líneas, los rangos por sub-diario, el cuadre y la huella."""
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


def revisar_tesoreria(documento: dict, cuentas: list[dict] | None = None) -> dict:
    """El dinero de un periodo, revisado antes de conciliarlo: los movimientos de las cuentas del contribuyente.

    **Una sola entrada** (3.0 del estándar), como `comprobantes[]` lo es de una compra o de una venta: venga de una
    línea de extracto o de una constancia de pago, al motor llega un `movimiento`, y lo que los distingue no es una
    etiqueta sino el `saldo`, que solo un extracto trae. Lo que el banco declara en la cabecera de la hoja va en
    `extractos[]`, y la contrapartida que decide el ERP en `imputaciones_de_movimientos`.

    **No asienta nada.** El asiento de tesorería es el hito D6 y espera tres datos que no tenemos: la norma para
    asentar el ITF —que además no tiene código en el Catálogo 05, así que su línea no se puede nombrar—, las
    cuentas del PCGE con su cita, y un archivo del sub-diario de bancos que CONCAR haya aceptado. Lo que esto hace
    es lo que sí se puede terminar hoy: validar la forma, deduplicar, resumir y reportar lo que no cierra.

    **Y no juzga cómo se leyó nada** (12.0), que es la regla que ordena lo que hay aquí dentro. Hasta la 11.x esto
    recorría la cadena de saldos corridos línea a línea y devolvía un `cuadre`; el problema, que señaló John el
    11-oct-2026 —*«el cuadre de saldos no garantiza nada, y además no todos tienen eso»*—, es que **sin líneas con
    `saldo` devolvía `cuadra: true` sin haber mirado nada**, y con una línea inventada también. Un verde que no
    significa nada es peor que ningún control, y para un ERP que manda operaciones estructuradas —que es lo que
    este motor recibe— ése era siempre el caso.

    La cadena no desaparece: vive en **`tesoreria.cuadra`, publicada**, porque sigue siendo lo que convierte «leí
    un PDF» en «lo leí bien». Lo que cambia es dónde se llama — **donde se hace el parseo**, que no es aquí.

    **Lo que sí se comprueba es lo que el banco DECLARÓ contra lo que mandaste.** Los dos totales de la cabecera
    (`extractos[]`) contra la suma de las líneas, y su saldo final contra la aritmética de esos mismos números.
    Es la diferencia que lo hace valer: **no puede pasar en vacío**, porque solo corre si la cabecera dice algo, y
    entonces compara dos números que existen los dos. Y caza lo que la cadena no caza —una línea entera perdida,
    porque las demás encadenan igual—.

    **El `cuadre` contable de verdad es la partida doble**, y tesorería no lo tiene todavía porque no arma asiento.
    Llegará con D6, sobre las líneas, como el de cualquier libro.

    Lo que un movimiento dice cancelar tiene su propio cuadre, que es aritmético y distinto: lo que sus
    `referencias` reclaman no puede pasar del importe —eso para al construirlo—, y **lo que ninguna reclama se
    reporta y no se cierra**, porque qué es ese resto lo decide el contador por la imputación. Un cargo lleva el
    ITF dentro.

    Y lo que apunta a una cuenta que nadie declaró se nombra: el `id` es la llave con la que el dinero se enlaza
    con su 104, y si no está en el maestro no hay nada que deducir.

    **Y dice qué movimientos no tienen todavía su contrapartida** (3.0 del estándar), que es el `sin_cuenta` del
    dinero: la 104 sale del maestro y la otra cara la pone el ERP en `imputaciones_de_movimientos`, igual que la
    cuenta de un gasto llega en la imputación de su comprobante. Un reparto que no suma el importe **no se
    reporta: para** — ese informe existe porque «qué es ese resto lo decide el contador por la imputación», y una
    imputación a medias no es un dato que falte sino una decisión mal hecha."""
    doc = documento or {}
    libro = preparacion.libro_de(doc)
    movimientos = preparacion.movimientos_de(doc)
    cabeceras = preparacion.extractos_de(doc)
    imputadas = preparacion.imputaciones_de_movimientos_de(doc, movimientos)
    declaradas = {c.id: c for c in tesoreria.leer(cuentas)}

    nuevos, repetidos = tesoreria.sin_duplicados(movimientos)

    # Un RESUMEN, y el nombre lo dice: cuántos movimientos tiene cada cuenta y cuánto suman sus dos sentidos. No
    # afirma que nada cuadre. El ITF va aparte porque no es un cargo del titular hacia un tercero, es lo que el
    # banco descuenta además — y las dos sumas se contrastan abajo contra lo que declaró la cabecera, si la hay.
    totales = []
    for cuenta in dict.fromkeys(m.cuenta for m in nuevos):
        suyos = [m for m in nuevos if m.cuenta == cuenta]
        totales.append({
            "cuenta": cuenta,
            "movimientos": len(suyos),
            "cargos": str(sum((m.importe for m in suyos if m.es_cargo), modelo.CERO)),
            "abonos": str(sum((m.importe for m in suyos if not m.es_cargo), modelo.CERO)),
            "itf": str(sum((m.itf for m in suyos if m.itf is not None), modelo.CERO)),
            "cuenta_contable": (declaradas[cuenta].cuenta_contable if cuenta in declaradas else ""),
        })

    # Los dos informes que antes salían de `constancias[]` y ahora salen del movimiento, que es la única entrada
    # (3.0 del estándar). `cual` en vez de `numero`: un movimiento se nombra por el número del papel que lo prueba
    # si lo tiene, y si no por el del banco — los dos existen y pueden ser distintos.
    sin_atribuir = [{"cual": _nombre_de(m), "importe": str(m.importe), "repartido": str(m.repartido),
                     "sin_atribuir": str(m.sin_atribuir)}
                    for m in nuevos if m.sin_atribuir > modelo.CERO]
    de_ia = [{"cual": _nombre_de(m), "origen": m.origen, "confianza": str(m.confianza)}
             for m in nuevos if m.de_lectura_asistida]

    avisos = []
    if not declaradas:
        avisos.append({"codigo": "SIN_CUENTAS_DECLARADAS", "pedir_a": "quien integra",
                       "texto": "No se declaró el maestro de cuentas, así que no hay contra qué contrastar a qué "
                                "cuenta apunta cada movimiento ni de qué 104 sale cada pago"})
    # Lo que el banco DECLARÓ en la cabecera contra la suma de lo que llegó. Es la única comprobación de saldos
    # que se queda aquí, y lo que la distingue de la que se fue es que **no puede pasar en vacío**: solo corre si
    # la cabecera dice algo, y entonces compara dos números que existen. La cadena de saldos corridos, en cambio,
    # devolvía «cuadra» cuando ninguna línea traía `saldo`, que es un verde que no significaba nada (John,
    # 11-oct-2026: «el cuadre de saldos no garantiza nada, y además no todos tienen eso»). Vive ahora en
    # `tesoreria.cuadra`, publicada para quien parsea un extracto, que es donde se comprueba una lectura.
    for c in totales:
        cabecera = cabeceras.get(c["cuenta"])
        if cabecera is None:
            continue
        for clave, suma in (("total_cargos", "cargos"), ("total_abonos", "abonos")):
            dicho = getattr(cabecera, clave)
            if dicho is not None and str(dicho) != c[suma]:
                avisos.append({"codigo": "TOTAL_DECLARADO_NO_COINCIDE", "pedir_a": "quien lee el archivo",
                               "texto": f"La cabecera de {c['cuenta']!r} dice {clave.replace('total_', '')} por "
                                        f"{dicho} y las líneas suman {c[suma]}. Falta o sobra una línea: el saldo "
                                        f"final no siempre lo delata, porque un cargo y un abono perdidos por el "
                                        f"mismo importe lo dejan igual"})
        # Y el saldo final, que es aritmética sobre los mismos números: lo de antes, más lo que entró, menos lo
        # que salió y menos lo que el banco descontó por ITF. No necesita que ninguna línea traiga su saldo.
        if cabecera.saldo_inicial is not None and cabecera.saldo_final is not None:
            sale = (cabecera.saldo_inicial + modelo.monto(c["abonos"])
                    - modelo.monto(c["cargos"]) - modelo.monto(c["itf"]))
            if sale != cabecera.saldo_final:
                avisos.append({"codigo": "SALDO_FINAL_DECLARADO_NO_COINCIDE", "pedir_a": "quien lee el archivo",
                               "texto": f"La cabecera de {c['cuenta']!r} dice que se acaba en "
                                        f"{cabecera.saldo_final} y de sus propios números sale {sale} "
                                        f"({cabecera.saldo_inicial} + {c['abonos']} − {c['cargos']} − "
                                        f"{c['itf']} de ITF). Falta o sobra un movimiento"})
    # La contrapartida que falta, y la cuenta de un traspaso que nadie declaró. Las dos son del mismo tipo que
    # `sin_cuenta` en un comprobante: el motor no la adivina y dice a quién pedirla.
    for m in nuevos:
        if (m.id_externo or "") not in imputadas:
            avisos.append({"codigo": "MOVIMIENTO_SIN_IMPUTAR", "pedir_a": "contador",
                           "texto": f"El movimiento {_nombre_de(m) or m.id_externo or 'sin referencia'} de la "
                                    f"cuenta {m.cuenta!r} no tiene contrapartida. La 104 sale del maestro; la otra "
                                    f"cara se imputa, igual que la cuenta de un gasto"})
            continue
        suya = imputadas[m.id_externo]
        if suya.es_traspaso and declaradas and suya.cuenta_propia not in declaradas:
            avisos.append({"codigo": "CUENTA_PROPIA_NO_DECLARADA", "pedir_a": "quien integra",
                           "texto": f"El movimiento {_nombre_de(m) or m.id_externo} declara un traspaso a la "
                                    f"cuenta {suya.cuenta_propia!r}, que no está en el maestro declarado: un "
                                    f"traspaso es entre dos cuentas propias, y la otra tiene que existir"})
    for h in tesoreria.sin_cuenta_declarada(nuevos, list(declaradas.values())):
        avisos.append({"codigo": "CUENTA_NO_DECLARADA", "pedir_a": "quien integra",
                       "texto": f"Un {h['que']} ({h['cual'] or 'sin referencia'}) apunta a la cuenta "
                                f"{h['cuenta']!r}, que no está en el maestro declarado"})
    # La moneda de un movimiento contra la de su cuenta. Hasta la 3.0 no se contrastaba con nada, así que una
    # cuenta en dólares aceptaba movimientos marcados en soles y nada fallaba — el tipo de error que no se ve
    # hasta el cierre, igual que un `id` mal escrito.
    for m in nuevos:
        suya = declaradas.get(m.cuenta)
        if m.moneda and suya and suya.moneda and m.moneda != suya.moneda:
            avisos.append({"codigo": "MONEDA_DISTINTA_DE_LA_CUENTA", "pedir_a": "quien lee el archivo",
                           "texto": f"El movimiento {_nombre_de(m) or 'sin referencia'} de la cuenta "
                                    f"{m.cuenta!r} dice {m.moneda} y esa cuenta se declaró en {suya.moneda}. "
                                    f"Casi siempre es una línea de otro extracto o un `id` equivocado"})

    sin_imputar = [_nombre_de(m) or m.id_externo
                   for m in nuevos if (m.id_externo or "") not in imputadas]
    traspasos = [{"cual": _nombre_de(m) or m.id_externo, "cuenta": m.cuenta,
                  "cuenta_propia": imputadas[m.id_externo].cuenta_propia}
                 for m in nuevos
                 if m.id_externo in imputadas and imputadas[m.id_externo].es_traspaso]

    return {"libro": libro.a_dict(), "movimientos": len(nuevos), "repetidos": len(repetidos),
            "imputados": len(nuevos) - len(sin_imputar), "sin_imputar": sin_imputar,
            "transferencias_declaradas": traspasos, "totales_por_cuenta": totales,
            "sin_atribuir": sin_atribuir, "de_lectura_asistida": de_ia, "avisos": avisos}


def _nombre_de(m) -> str:
    """Cómo se nombra un movimiento en un informe: por el papel que lo prueba si lo tiene, y si no por el número
    que le dio el banco. Los dos existen y pueden ser distintos — una detracción pagada desde BBVA tiene su vóucher
    del Banco de la Nación y su `N° OPER`—, y para que una persona lo encuentre vale más el del papel."""
    return m.constancia or m.referencia


def validar_cuentas_bancarias(cuentas: list[dict]) -> dict:
    """El maestro de cuentas bancarias del contribuyente, comprobado antes de usarlo.

    **Es un argumento y no una tabla**: el motor lo recibe, lo valida y no lo guarda. El estado —qué cuentas tiene
    hoy la empresa— es del ERP, y lo que puede vivir aquí es su contrato. Sin cuentas declaradas no cambia nada.

    Lo que comprueba: que el CCI tenga sus 20 dígitos (se admite con espacios o guiones, que es como lo imprime
    cada banco), que la moneda sea una de las dos que un extracto peruano trae, y que ningún `id` se repita —es la
    llave con la que un movimiento apunta a su cuenta, y la que enlaza un traspaso con la otra—. Un fallo de esos **para**, porque seguir
    con una cuenta que no se puede reconocer no lleva a ningún sitio.

    Lo que **avisa y no para**: una cuenta sin cuenta contable. La 104 del PCGE es un dato de la empresa y el motor
    no la deriva ni cuando conoce el banco, así que lo que hace es decir cuál falta y a quién pedírsela."""
    leidas = tesoreria.leer(cuentas)
    avisos = [{"id": c.id, "codigo": "CUENTA_BANCARIA_SIN_CUENTA_CONTABLE", "pedir_a": "contador",
               "texto": f"La cuenta {c.id!r} no declara con qué cuenta contable se asienta. El motor no la supone: "
                        f"es una divisionaria de la 104 y la elige el contribuyente, cuenta por cuenta"}
              for c in leidas if not c.cuenta_contable]
    return {"cuentas": [{**c.a_dict(), "codigo_de_banco": c.codigo_de_banco} for c in leidas],
            "avisos": avisos, "cuantas": len(leidas)}


def resumen(documento: dict, *, agrupar_por: str = "") -> dict:
    """Cuánto es este libro: base gravada, IGV y total, **cada moneda por su lado**.

    Lo que un contador pregunta antes de dar un mes por bueno, y lo que hasta la 3.4 había que sacar
    generando un archivo. **No recibe `driver` ni configuración**: es del libro, no de un destino — y esa
    es la diferencia con el `resumen_por_contraparte` de `diagnosticar`, que es lo que iría a ESE archivo
    (filtra lo que el destino no lleva y cuenta las duplicadas).

    `recuento` trae cuatro números que no se solapan y suman `recibidos`: lo excluido no es del mes y lo
    duplicado no va a ningún archivo, así que ninguno suma, pero son dos cosas distintas y se dicen
    aparte. **La nota de crédito resta** —la 07 y la 87—, y no hay ninguna clave que sume dos monedas.

    Con `agrupar_por="contraparte"`, además por proveedor o cliente, de más a menos y por su documento.
    Quien quiera que las duplicadas del lote se marquen solas, llama antes a `revisar`: esto no valida.
    """
    libro = preparacion.libro_de(documento)
    salida_ = _resumen.del_libro(preparacion.comprobantes_de(documento), agrupar_por=agrupar_por)
    # El libro va en la respuesta porque un total sin decir de qué RUC y de qué mes es una trampa —y es
    # además lo que hace que nadie pueda coser doce de estos y presentarlos como un resumen anual sin que
    # se vea, que es un descarte declarado (`ARQUITECTURA.md`, «Lo que no se hace, y por qué»).
    return {"libro": {"ruc": libro.ruc, "periodo": libro.periodo, "tipo": libro.tipo}, **salida_}


def campos_del_comprobante() -> dict:
    """Qué campos de un comprobante los pone el DOCUMENTO, cuáles el SISTEMA que lo produce y cuáles la
    REVISIÓN.

    Es lo que necesita cualquier puerta de entrada para saber qué acepta de quien escribe: una API de
    registro, un formulario, o un agente al que alguien le dicta una factura. Los tres tramos no se
    solapan y cubren el comprobante entero, y `obligatorios` son los del `required` del estándar.

    Existe por un caso concreto: quien lo escribía a mano se dejaba campos —los descuentos, el ICBPER, el
    valor no gravado— que su propia base ya guardaba, y se perdían sin error y sin aviso.
    """
    return {
        "documento": list(modelo.CAMPOS_DEL_DOCUMENTO),
        "sistema": list(modelo.CAMPOS_DEL_SISTEMA),
        "revision": list(modelo.CAMPOS_DE_LA_REVISION),
        "obligatorios": list(esquema_open_accounting()["$defs"]["comprobante"]["required"]),
    }


def _como_dict(linea: Any) -> dict:
    """Una línea como diccionario, venga ya como tal o como `LineaDiario`. Lo de siempre: las dos formas circulan,
    y por esta puerta entran diccionarios."""
    return dict(linea) if isinstance(linea, dict) else linea.a_dict()


def por_cuenta(lineas: list[dict], libro: dict | None = None) -> dict:
    """El pre-mayor: en qué cuentas cayó el asiento, con su debe y su haber por moneda, y el cuadre.

    La misma entrada que `cuadrar`, y hermana suya: aquí no se contabiliza nada, se agrupa lo que el motor
    ya contabilizó. Delata una imputación mal puesta sin abrir ningún archivo —una cuenta con un importe
    que no le toca salta a la vista en diez cuentas y no en seiscientas filas—.

    Trae el cuadre global y **también por moneda**, que dice algo que el global no puede: dos monedas cuyos
    descuadres se compensan salen cuadradas en el total y descuadradas cada una. Los suma la misma función
    que `cuadrar`, así que el pre-mayor y el cuadre no pueden discrepar.

    `roles` va en plural: con una detracción, la cuenta por pagar hace dos papeles en el mismo asiento. Y **pide el
    `libro`**, porque desde la 10.0 el papel de una línea no viaja en ella: se **deriva** de lo que trae, y el lado
    al que va la contraparte lo dice el libro (`drivers.kit.rol`). Sin él la columna viene vacía y
    `roles_derivados` lo dice — nadie puede afirmar que una línea es el tercero sin saber si es una compra o una
    venta, y una columna vacía sin avisar es peor que no tenerla.

    Un libro que **no declara roles** —tesorería, mientras el motor no sepa armar su asiento— también devuelve la
    columna vacía con `roles_derivados: false`: no es un error, es una pregunta sin respuesta todavía. Un `tipo`
    que el motor no conoce **sí** es un error, y lo dice: un libro mal escrito dejaría la columna vacía en silencio.
    """
    tipo = str(((libro or {}).get("tipo") or "")).strip()
    if not tipo:
        return {**_resumen.por_cuenta(lineas), "roles_derivados": False}
    rasgos = rasgos_de(tipo)                      # un tipo desconocido para aquí, con la lista de los que conoce
    if not rasgos.roles:
        return {**_resumen.por_cuenta(lineas), "roles_derivados": False}
    return {**_resumen.por_cuenta([{**d, "rol": rol.rol_de(d, rasgos)} for d in map(_como_dict, lineas)]),
            "roles_derivados": True}


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

def configuracion_por_defecto(driver: str | None = None) -> dict:
    """La configuración contable de partida, en la forma en que se guarda: lo general en la raíz y una sección por
    sistema que se configura. Es un punto de partida, no la verdad de ningún contribuyente.

    **Con `driver`, la de quien lleva ese sistema**: lo general con las cuentas de ese sistema —las suyas si las
    declara, las del PCGE si no— y solo su sección. Es lo que una aplicación siembra cuando alguien da de alta una
    empresa y ya dijo con qué sistema trabaja, en vez de sembrar la de todos."""
    return preparacion.configuracion_por_defecto(driver or "")


def describir_configuracion(driver: str | None = None) -> dict:
    """Qué se configura: lo general y, por cada sistema, sus campos con tipo, valor por defecto, patrón y textos, y en
    qué columnas de su archivo puede ir cada dato. Con `driver`, lo general y solo su sección."""
    return preparacion.describir_configuracion(driver or "")


def config_aplicada(configuracion: dict | None = None, *, driver: str = "",
                    documento: dict | None = None, imputacion: dict | None = None) -> dict:
    """La configuración **tal como la preparan las operaciones** antes de tocar nada: lo general con sus valores de
    fábrica debajo, encima la sección del sistema de `driver`, todo plano, y la imputación de cada comprobante dentro.

    **Exportar no la necesita**: ahí se entrega la configuración como se guarda y el motor la aplica por dentro. Esto
    es para quien hace su propio **pre-vuelo** —decirle a alguien qué le falta ANTES de generar el archivo, o pintar
    una pantalla con lo que está configurado—, porque las funciones que responden eso (`asiento.faltantes_para`,
    `asiento.sub_diario`, `asiento.cuenta_tercero`, `asiento.lleva_centro`…) reciben la configuración **ya aplicada**
    y buscan sus claves en la raíz. Con la forma en que se guarda no fallan: devuelven vacío, que es peor.

    La imputación llega como en cualquier operación: en el bloque `imputaciones` del `documento` o por `imputacion`,
    nunca las dos, y con las mismas comprobaciones —ninguna llave huérfana, ninguna repetida—. **Por eso una
    imputación exige el documento**: sin los comprobantes no hay contra qué casar las llaves, y una mal escrita
    volvería a hacer lo que esas comprobaciones existen para impedir, que es generar con la cuenta por defecto sin
    decir nada. Sin imputación, el documento sobra.

    Una configuración inválida se detiene aquí con `ConfiguracionInvalida`, igual que al exportar: una clave que nadie
    lee generaría el archivo con el valor de fábrica sin avisar.
    """
    trae_imputacion = bool(imputacion) or bool((documento or {}).get("imputaciones"))
    if trae_imputacion and not documento:
        raise DocumentoInvalido(
            "Para aplicar una imputación hace falta el `documento`: sus comprobantes son contra lo que se comprueba "
            "que cada `id_externo` existe y no está repetido. Sin configuración de imputación, el documento sobra.")
    comprobantes = preparacion.comprobantes_de(documento) if documento else []
    elegida = preparacion.imputacion_del_documento(documento, imputacion, comprobantes) if documento else None
    return preparacion.con_imputacion(preparacion.config_aplicada(configuracion, driver), elegida, comprobantes)


def errores_de_configuracion(configuracion: dict | None) -> list[str]:
    """Lo que la configuración no cumple, un error por línea con su ruta. Lista vacía: se puede aplicar."""
    return preparacion.errores_de_configuracion(configuracion)


# --- lo que el motor sabe -----------------------------------------------------------

def drivers_disponibles() -> dict:
    """Los sistemas a los que se exporta, por nombre: qué libros genera cada uno, su forma, su familia, su canal
    —a quién entrega: `legacy`, `sunat` o `erp`—, el vocabulario con que recibe sus líneas (`legacy` o `neutral`), lo
    que exige, si se configura y su descripción.

    Hasta la 7.x había además un `grupo` que traducía el canal a «SIRE», «Legacy» o «ERP». La 8.0 lo retiró: eran dos
    palabras para lo mismo, y la de fuera mentía — el PLE salía como grupo `sire` y no es el SIRE."""
    return {
        nombre: {"formatos": modulo.FORMATOS,
                 "tipo": "texto" if contrato.forma(modulo) == "linea" else "archivo",
                 "forma": contrato.forma(modulo),
                 "familia": contrato.familia(modulo),
                 "canal": contrato.canal(modulo),
                 "vocabulario": contrato.vocabulario(modulo),
                 "exige": sorted(contrato.exige(modulo)),
                 "configurable": bool(contrato.seccion_por_defecto(modulo)),
                 "descripcion": ((modulo.__doc__ or "").strip().splitlines() or [""])[0]}
        for nombre, modulo in drivers.DRIVERS.items()
    }


def verificar_documento(documento: dict) -> dict:
    """Comprueba un documento contra el ESTÁNDAR, sin armar ni exportar nada: su esquema y sus catálogos.

    Es el espejo de `verificar_driver`. Aquel comprueba lo que alguien ESCRIBE contra el contrato del motor; este
    comprueba lo que alguien PRODUCE contra el contrato del estándar, y existe porque hasta la 3.1 no había
    ninguno: quien construía sobre `open-accounting` tenía el esquema publicado y ninguna forma de correrlo que no
    fuera clonar el repositorio y lanzar pytest.

    Devuelve `{conforme, errores, avisos, open_accounting}`. La diferencia entre las dos listas es la del propio
    estándar: un **error** es que el documento no cumple el esquema, y ahí no hay nada que interpretar. Un
    **aviso** es lo que el esquema no puede decir porque está en los catálogos y no en él —un `tipo` de libro que
    no conocemos rompe, porque de él dependen las columnas de cada registro—, y quien lee decide.

    **Hasta la 10.0 había un segundo aviso, el del `rol` fuera del catálogo**, y se fue con el campo: una línea con
    `rol` ya no se degrada, falla el esquema, porque `linea` no admite claves que no son suyas. Mantener el aviso
    sería prometer una degradación que no ocurre.

    Solo para Python y la línea de comandos, por lo mismo que `verificar_driver` y por una razón más: valida con
    `jsonschema`, que es el extra `schema` y no una dependencia del núcleo. Lanza `ImportError` si no está."""
    try:
        import jsonschema
    except ImportError as error:
        raise ImportError("Validar contra el esquema necesita `jsonschema`: pip install 'contaperu[schema]'") from error

    validador = jsonschema.Draft202012Validator(esquema_open_accounting())
    errores = [f"{'/'.join(str(p) for p in e.absolute_path) or '(raíz)'}: {e.message}"
               for e in sorted(validador.iter_errors(documento), key=lambda e: list(e.absolute_path))]

    tipos = set(catalogos_del_estandar()["tipos_de_libro"]["codigos"])
    avisos = []
    tipo = ((documento or {}).get("libro") or {}).get("tipo")
    if tipo is not None and tipo not in tipos:
        avisos.append(f"`libro.tipo` {tipo!r} no está en el catálogo ({', '.join(sorted(tipos))}): esto SÍ rompe, "
                      "porque de él dependen las columnas de cada registro")
    return {"conforme": not errores, "errores": errores, "avisos": avisos,
            "open_accounting": (documento or {}).get("open_accounting", "")}


def verificar_driver(modulo: str) -> dict:
    """Comprueba un driver contra el contrato antes de registrarlo: importa el módulo por su nombre (`paquete.driver`) y
    dice su forma, su canal, si cumple y qué le falta (`drivers.contrato.incumplimientos`), más los avisos con
    que el registro lo aceptaría igual durante la 1.x.

    Solo para Python y la línea de comandos: importar código por su nombre nunca se expone por HTTP ni por MCP, y por
    eso no está en la tabla de operaciones. Lanza `ImportError` si el módulo no se puede importar."""
    try:
        cargado = importlib.import_module(modulo)
    except Exception as error:  # noqa: BLE001 — cualquier fallo al importar se dice igual: no hay driver que mirar
        raise ImportError(f"No se puede importar el driver {modulo!r}: {error}") from error
    faltas = contrato.incumplimientos(cargado)
    # Los dos avisos que hubo aquí hasta la 3.10 —no declarar CANAL y usar la forma `construir`— prometían la 2.0
    # con el paquete en la 3.10. La 4.0 los cobró: las dos cosas son ya incumplimientos, no avisos.
    avisos: list[str] = []
    return {"modulo": modulo, "nombre": str(getattr(cargado, "NOMBRE", "") or ""), "forma": contrato.forma(cargado),
            "canal": contrato.canal(cargado), "cumple": not faltas,
            "incumplimientos": faltas, "avisos": avisos}


def catalogos_sunat() -> dict:
    """Los catálogos de SUNAT que entiende el motor: tipos de comprobante, tipos de documento de identidad, monedas,
    medios de pago, los motivos de una nota de crédito y de una de débito, los códigos de tributo, las clases de IGV
    y la tabla de detracciones, con su fuente.
    La de detracciones es la única que el ERP puede sobreescribir en su configuración; las demás se copian de la norma
    y no se gobiernan.

    Ojo con dos claves que se parecen y no son lo mismo: `notas` son los TIPOS DE COMPROBANTE que son notas (07, 08,
    87 y 88), y los dos `motivos_nota_*` dicen POR QUÉ se emitió una (los Catálogos 09 y 10 del Anexo N.° 8)."""
    return {
        "tipos_comprobante": catalogos.TIPOS_CP,
        "tipos_documento_identidad": catalogos.TIPOS_DOC_IDENTIDAD,
        "monedas": sorted(catalogos.MONEDAS),
        "medios_pago": catalogos.MEDIOS_PAGO,
        "motivos_nota_credito": catalogos.MOTIVOS_NOTA_CREDITO,
        "motivos_nota_debito": catalogos.MOTIVOS_NOTA_DEBITO,
        "tributos": catalogos.TRIBUTOS,
        "notas": sorted(catalogos.NOTAS),
        "clases_igv_compra": catalogos.CLASES_IGV_COMPRA,
        "clases_igv_venta": catalogos.CLASES_IGV_VENTA,
        "fuera_del_registro_sunat": sorted(catalogos.FUERA_DEL_REGISTRO_SUNAT),
        "detracciones": detracciones.tabla_del_motor(),
        "fuentes": dict(catalogos.FUENTES),
    }


def catalogos_api_sire() -> dict:
    """El CANAL del SIRE, descrito: a qué rutas se sube un registro, qué parámetros son
    obligatorios, qué significa cada estado de ticket y qué códigos de retorno devuelve SUNAT.

    Por qué está en el motor: el conocimiento del FORMATO ya estaba resuelto una vez para todos
    —la estructura del TXT, el nombre que SUNAT exige, los catálogos—, pero el del CANAL no, y cada
    casa de software lo vuelve a reunir a mano desde dos manuales que se contradicen entre sí. Aquí
    se describe; ejecutarlo es de quien integra. El motor no se conecta a SUNAT.

    Ojo a lo que esto NO habilita: «Generar el registro» no existe por API (RS 000040-2022 art. 8.3).
    El techo de cualquier integración es dejar el mes en preliminar."""
    return catalogos.api_sire()


def campos_del_sire() -> dict:
    """El FORMATO del SIRE columna a columna: de cada campo del anexo del RVIE y del RCE, su número, el nombre que le
    da SUNAT, el campo del documento donde cae —o el motivo por el que no cae— y si el TXT de reemplazo lo devuelve.

    Para qué sirve: responde «¿dónde acabó esta columna?» y «¿qué del registro no se está usando?» sin leer el código
    del lector. Quien monta una pantalla de revisión puede decir de dónde salió cada dato, y quien escribe su propio
    conector sabe qué le llega y qué no.

    **Una columna que el motor no lee no se pierde**: la fila entera del TXT viaja en `datos_originales["sire"]` del
    comprobante. Lo que no está tipado es lo que ninguna regla usa todavía, y cada hueco lleva escrito su motivo —dos
    de ellos, la marca de detracción del RCE y las operaciones gratuitas del RVIE, dicen además que son candidatos a
    entrar el día que haya un caso real detrás.

    Es el hermano de `catalogos_api_sire`: aquel describe el CANAL —a qué ruta se sube un registro— y este el FORMATO.
    Los dos describen sin ejecutar."""
    return catalogos.campos_del_sire()


def campos_del_ple() -> dict:
    """El FORMATO del **Libro Diario 5.1 del PLE** columna a columna: de cada uno de sus 21 campos, su número, el
    nombre que le da SUNAT, de dónde lo saca el driver al escribirlo —o el motivo por el que va vacío— y qué hizo con
    esa columna un libro real que SUNAT aceptó.

    Trae además los **códigos de libro** del PLE (`050100` el Diario, `080100` el Registro de Compras, `140100` el de
    Ventas) y la nomenclatura del fichero `LE…`. Ojo con no confundirlos con los del SIRE, que son otros: `140400` y
    `080400`.

    **El motor no LEE un 5.1**, así que a diferencia del mapa del SIRE este no habla de lectura: describe cómo se
    escribe. Lo que el motor no sabe poner lo dice su `motivo` — el campo 20, la referencia al registro de origen,
    espera que el motor numere el CUO de ese registro.

    Es el hermano de `campos_del_sire`: el mismo papel para el otro formato de SUNAT que el motor escribe."""
    return catalogos.campos_del_ple()


def regimenes_tributarios() -> dict:
    """Los **regímenes tributarios** del Perú y lo que cada uno obliga, con la cita de su artículo: la tasa y la base
    de su pago a cuenta, los libros que obliga a llevar —por su código del PLE— y los topes que sacan de él.

    Para qué sirve, y por qué es un catálogo y no un campo del documento: responde dos preguntas, y una de ellas no
    tiene un documento delante. «¿Qué libros estoy obligado a llevar?» se pregunta al dar de alta una empresa, antes
    de cargar un comprobante — haría falta un libro para preguntar por los libros. La otra, «¿cómo tributo este
    mes?», se contesta con los dos registros del mes delante, y la tasa sale de aquí.

    Tabla parcial a propósito: hoy solo el **Régimen Especial**, el único con su norma leída (arts. 118, 120 y 124 de
    la Ley del Impuesto a la Renta). Los otros tres se declaran `pendiente_de_fuente` y dicen qué hay que leer para
    que entren, en vez de traer una tasa de memoria.

    Lo que esto NO hace: **calcular la cuota**. Eso es una regla que emite un número y entra con su norma y con su
    caso real, un formulario presentado. El motor publica la tasa; la aplica quien integra. Y el régimen de cada
    periodo lo dice quien llama: superar un tope cambia de régimen a mitad de ejercicio (art. 122) y el motor no lo
    deduce de los importes."""
    return catalogos.regimenes_tributarios()


def cronogramas_de_vencimiento() -> dict:
    """Cuándo vence un mes: la fecha de la **declaración y el pago** (anexo I) y la **fecha máxima de atraso del
    registro electrónico** de ventas y de compras (anexo II), por año, por periodo y por cada uno de los diez
    dígitos de RUC, más la columna de los buenos contribuyentes y las UESP. Las fechas son texto `AAAA-MM-DD`.

    Los dos salen de la misma resolución, la RS 000281-2022/SUNAT, que los fija en días hábiles «para el año 2023 y
    siguientes». El del registro **vence antes** que el de la declaración: el registro se cierra para poder
    declarar.

    Por qué esto puede vivir en un motor sin reloj: **no es un reloj**. Dado un periodo y un dígito devuelve una
    fecha, y la respuesta no cambia según cuándo se pregunte. Lo que necesita la fecha de hoy —si queda tiempo, si
    hay mora, cuántos días faltan— no está aquí y no va a estar: eso lo calcula quien llama, que es quien tiene el
    hoy.

    Solo los años que SUNAT ya publicó resueltos, y es la única tabla del motor que envejece: derivar un año nuevo
    pediría el calendario de feriados y de días no laborables, que cambia por decreto. Un periodo de un año que no
    está no devuelve una fecha calculada — la librería se niega diciendo qué años conoce."""
    return catalogos.cronogramas_de_vencimiento()


def catalogos_del_estandar() -> dict:
    """Los catálogos que este estándar inventa —`roles`, `clases` y `tipos_de_libro`—, cada uno con su fuente y su
    versión. Son lo que un ERP de fuera necesita para leer una línea del asiento sin conocer el PCGE, y viven
    publicados junto al esquema para poder citarse por la URL del tag del estándar.

    No están en `catalogos_sunat` a propósito: esos se copian de la norma y estos se gobiernan (`estandar/LEEME.md`,
    «Quién gobierna los catálogos»)."""
    return vocabulario.catalogos()


def catalogo_pcge() -> dict:
    """El catálogo oficial de cuentas del PCGE 2026: cada cuenta con su nombre y la página de la norma que lo dice."""
    return pcge.catalogo.cargar_catalogo()


def esquema_open_accounting() -> dict:
    """El esquema JSON del documento `open-accounting`, con cada campo documentado."""
    return _datos.esquema_open_accounting()


def esquema_diagnostico() -> dict:
    """El JSON Schema de la respuesta de `diagnosticar`, también cuando la configuración no se puede aplicar."""
    return _datos.leer_esquema("diagnostico")


def contrato_openconta() -> dict:
    """El contrato OpenConta de la puerta HTTP, en formato OpenAPI 3.1: el que viaja con esta versión del motor."""
    return _datos.openconta()


def comparar_sire(nuestro: bytes, sunat: bytes, *, registro: str = "", nombres: Sequence[str] = ()) -> dict:
    """Compara el TXT del SIRE que generó el motor con la exportación del detalle que da SUNAT, por comprobante: qué
    falta, qué sobra y qué no coincide, y en `informe` lo mismo en texto. El registro —`venta` o `compra`— se deduce de
    los `nombres` de los archivos (1404 ventas, 0804 compras) o se fuerza con `registro`."""
    elegido = _comparar.registro_de(list(nombres), registro)
    comparacion = _comparar.comparar(_comparar.leer_bytes(nuestro), _comparar.leer_bytes(sunat), elegido)
    return {**comparacion, "informe": _comparar.informe(comparacion)}
