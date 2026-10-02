"""El asiento en líneas del asiento: la contabilidad, sin el vocabulario de ningún ERP.

Aquí vive la LÓGICA del asiento —qué cuentas, qué sentido, cuántas líneas, en qué fecha— y sale ya
en el bloque `asiento` del estándar `open-accounting`. Las reglas, con su fuente al lado, están en el
docstring del paquete (`__init__.py`); este módulo las aplica.

Hasta el 11-sep-2026 esta lógica escribía directamente las columnas del Excel de CONCAR ('A'..'AO')
y la línea del comprobante se sacaba después, releyendo esas columnas. Era al revés de lo que el proyecto
quiere ser: la línea «neutral» heredaba los cortes de glosa y las siglas de un ERP concreto, y un
segundo driver de asientos habría tenido que reinterpretar columnas de CONCAR. Ahora la línea del comprobante
es la fuente y CONCAR es una proyección más (`drivers/concar/proyeccion.py`), con prohibido cambiar
una sola celda del Excel validado: lo vigila `tests/test_snapshot_concar.py`.

Lo que la línea sigue llevando de «sistema contable» es contabilidad peruana, no formato de un ERP:
el sub-diario y su correlativo, la cuenta, el centro de costo y en qué línea va. La sigla del
documento se conservaba por compatibilidad —la leían los consumidores de la 0.6— al lado de `tipo_cp`, el
código SUNAT; desde la 4.0 solo viaja el código, y la sigla la escribe cada driver con `resolucion.sigla_de_tipo`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from ..catalogos import (CATEGORIA_RENTA_4TA, TIPO_HONORARIOS, TIPOS_INVIERTEN, TIPOS_NOTA, TRIBUTO_IGV,
                         TRIBUTO_RENTA)
from ..configuracion import CONFIG_POR_DEFECTO
from ..detracciones import es_comodin, monto_detraccion, numero_pendiente, tasa_detraccion
from .. import pcge, vocabulario
from ..igv import base_imputable, igv_del_asiento, tasa_calculada
from ..modelo import CENTIMO, Comprobante, Libro, numero_sin_ceros, serie_y_numero, texto_tasa
from .faltas import RepartoNoCuadra, SinClase, SinCuenta
from .indice import DETRACCION_DEL_ESTANDAR, Cabecera, ComprobanteDelAsiento
from .resolucion import (asienta_sin_efecto, cuenta_por_pagar_detraccion, cuenta_tercero, limites_del_periodo,
                         lleva_centro, numerar_en_orden, partes_de, reparto_no_cuadra, sin_efecto_contable,
                         sub_diario, tiene_detraccion)
from .lineas import LineaDiario

# Hasta la 0.10 este módulo importaba las `Opciones` de los drivers solo para quitar los ceros del número: el núcleo
# dependía de una pieza de los drivers. Desde la 1.0 lee `opciones.sin_ceros` de lo que llegue; los dos nombres
# siguieron resolviendo desde aquí con aviso hasta la 2.0, que los retiró. Viven en `contaperu.drivers.kit`.

# El papel de cada línea en el asiento. Es lo que un driver necesita para traducir sin adivinar: un
# ERP que pida el IGV en una columna aparte encuentra esa línea por su rol, no por su cuenta, que la
# elige cada empresa.
# Del catálogo del estándar (`vocabulario.ROLES`): una sola fuente, publicada y citable por la URL del tag. Estaba
# aquí y otra vez como enum del esquema, y ningún test comparaba las dos.
ROLES = vocabulario.ROLES
# Y los que el motor **escribe**, que desde la 1.1 del catálogo ya no son todos, y que desde la 5.0 **tampoco son
# los seis de la 1.0**: tres de ellos se renombraron para sacarles el tributo del nombre, y los viejos siguen en el
# catálogo marcados en `obsoletos`. Así que esta tupla y la de la 1.0 divergen para siempre, a propósito. `contrapartida` y `tesoreria`
# entraron como vocabulario para quien produce un asiento que el motor no origina —una depreciación, un pago, una
# planilla—, y el motor no los emite: genera compras y ventas.
#
# La diferencia importa en dos sitios opuestos, y por eso hay dos nombres. Un **driver** tiene que entender los ocho,
# porque puede recibir un documento que los traiga, así que lee `ROLES`. Un **test** que compruebe «todos los roles
# salen con su clase» solo puede exigir estos seis, porque los otros dos no hay forma de producirlos desde un
# comprobante. Confundirlos daba un rojo que invitaba a emitir un rol solo para que el test pasara.
ROLES_DEL_MOTOR = ("principal", "impuesto", "retencion", "tercero", "recorte", "detraccion")
# Las líneas que llevan además el centro de costo en su anexo auxiliar. Lo del estándar es la del tercero —el «doble
# anexo», también en la línea que le descuenta la detracción—; cada driver lo cambia con las columnas que su sistema
# elige (`drivers.contrato.centro_en_anexo`). La principal lo lleva ahí solo cuando su cuenta no lo lleva en la suya.
CENTRO_EN_ANEXO = frozenset({"tercero"})


def glosa_de(c: Comprobante) -> str:
    """La glosa del comprobante: su concepto o, si no trae, el nombre de la contraparte —para que
    ninguna línea salga sin glosa—. En mayúsculas y SIN cortar: el largo lo decide cada ERP."""
    return ((c.concepto or "").strip() or (c.contraparte_nombre or "").strip()).upper()


def _iso(fecha: date | None) -> str:
    return fecha.isoformat() if fecha else ""


def _detraccion_del_estandar(c: Comprobante) -> dict:
    """La detracción del comprobante con lo que el estándar admite: sus siete claves declaradas y las anotaciones
    `_`. Sin las vacías, porque el estándar distingue «no lo sé» de «es esto» y lo primero se dice omitiendo la clave.

    **Es una frontera y filtra a propósito.** `$defs/detraccion` es un bloque cerrado, así que copiarlo tal cual hace
    que el documento de un driver falle su propio esquema en cuanto el bloque lleve algo de más — y puede llevarlo:
    quien usa la librería construye sus comprobantes en memoria, y un `Comprobante` no vigila las claves de este dict.
    Hasta la 3.10 el caso que lo justificaba era `tasa_tabla`, la anotación del motor, que el esquema rechazaba; desde
    la 4.0 esa anotación se llama `_tasa_tabla` y **sí pasa**, porque el bloque admite el prefijo que el estándar ya
    reservaba (enmienda 0019). Lo que no cambia es que aquí no se cuela nada que el esquema no admita."""
    bloque = c.detraccion if isinstance(c.detraccion, dict) else {}
    admitidas = set(DETRACCION_DEL_ESTANDAR)
    return {k: v for k, v in bloque.items()
            if v not in ("", None) and (k in admitidas or k.startswith("_"))}


def cabecera_de(c: Comprobante) -> Cabecera:
    """Los hechos del comprobante que un driver necesita al lado de sus líneas (`asiento.indice`).

    **Todos los del estándar menos los del proceso** (3.9: antes también faltaban los ocho que ya viajaban dentro de
    la línea, y por eso el documento que escribía un driver no podía volver a entrar al motor); el porqué y la regla,
    en el docstring de `Cabecera`.
    `valor_no_gravado` va YA RESUELTO (`adquisiciones_no_gravadas`): el campo del estándar admite nulo y significa
    «exonerado más inafecto», y esa cuenta la hace el modelo una vez y no cada driver a su manera.
    """
    return Cabecera(tipo_cp=c.tipo_cp or "", serie=c.serie or "", numero=c.numero or "",
                    numero_final=c.numero_final or "", fecha_emision=_iso(c.fecha_emision),
                    condicion_pago=c.condicion_pago or "", medio_pago=c.medio_pago or "",
                    id_externo=c.id_externo or "",
                    contraparte_tipo_doc=c.contraparte_tipo_doc or "", contraparte_doc=c.contraparte_doc or "",
                    contraparte_nombre=c.contraparte_nombre or "", concepto=c.concepto or "",
                    fecha_vencimiento=_iso(c.fecha_vencimiento), tipo_cambio=str(c.tipo_cambio or ""),
                    ref_tipo_cp=c.ref_tipo_cp or "", ref_serie=c.ref_serie or "",
                    ref_numero=c.ref_numero or "", ref_fecha=_iso(c.ref_fecha),
                    detraccion=_detraccion_del_estandar(c),
                    moneda=c.moneda or "", base_gravada=str(c.base_gravada), igv=str(c.igv),
                    dscto_base=str(c.dscto_base), dscto_igv=str(c.dscto_igv), exonerado=str(c.exonerado),
                    inafecto=str(c.inafecto), exportacion=str(c.exportacion), isc=str(c.isc),
                    base_ivap=str(c.base_ivap), ivap=str(c.ivap), icbper=str(c.icbper), otros=str(c.otros), dscto_otros=str(c.dscto_otros),
                    total=str(c.total), retencion=str(c.retencion),
                    destino_igv=c.destino_igv or "", valor_no_gravado=str(c.adquisiciones_no_gravadas),
                    anio_dua=c.anio_dua or "", cod_dep_aduanera=c.cod_dep_aduanera or "",
                    clasif_bienes=c.clasif_bienes or "", id_contrato=c.id_contrato or "",
                    tipo_nota=c.tipo_nota or "")


def _numero(numero: str, opciones: Any) -> str:
    """El número tal como va a la línea: sin ceros a la izquierda, salvo que las opciones del destino digan lo
    contrario (`sin_ceros`). Sin opciones, sin ceros: la regla de contabilidad de los tres destinos de serie."""
    if getattr(opciones, "sin_ceros", True):
        return numero_sin_ceros(numero)
    return (numero or "").strip()


def serie_numero_de(c: Comprobante, opciones: Any = None) -> str:
    """El serie-número del comprobante tal como va a la línea de ese destino: la serie sin espacios y el número según sus
    opciones. `diagnosticar` lo escribe igual, así un comprobante se nombra lo mismo en el diagnóstico y en el asiento."""
    return serie_y_numero((c.serie or "").strip(), _numero(c.numero, opciones))


def _limpio(campos: dict) -> dict:
    """Sin las claves vacías: un documento `open-accounting` no lleva ruido."""
    return {k: v for k, v in campos.items() if v not in ("", None)}


def constancia_de(c: Comprobante, config: dict | None = None, *, comodin: bool = True) -> dict[str, str]:
    """La constancia del depósito de la detracción de ese comprobante: su número y su fecha, como van al archivo.

    Una sola regla para los dos caminos que la necesitan, y son distintos a propósito: un driver de ASIENTO la
    recibe ya resuelta dentro de la línea de detracción, pero uno de REGISTRO —CONTASIS— nunca ve esa línea,
    porque el asiento lo arma su propio sistema. Hasta la 2.7 la reescribía, con el comodín incluido, y su
    docstring lo admitía.

    Lo que dice la regla: **sin detracción no hay constancia**, las dos en blanco; con detracción, el número cae
    al comodín cuando nadie ha pegado el vóucher —que es el caso normal al exportar el mes, porque el depósito se
    hace días después— y **la fecha no tiene comodín**, que una fecha inventada es peor que ninguna.

    **Con `comodin=False` no hay comodín ninguno** (3.9): ni se inventa el pendiente ni se repite el que venga en el
    documento, porque un comodín guardado de una exportación anterior tampoco es un depósito. Es lo que pide el
    vocabulario del estándar: el `999999999` es un apaño de los sistemas peruanos para llenar una columna obligatoria,
    y un ERP de fuera que lo reciba se apunta un vóucher que no existe. Sin constancia, la clave no viaja."""
    bloque = c.detraccion or {}
    if not str(bloque.get("codigo") or "").strip():
        return {"nro_constancia": "", "fecha_constancia": ""}
    numero = str(bloque.get("nro_constancia") or "").strip()
    if comodin:
        numero = numero or numero_pendiente(config)
    elif es_comodin(numero, config):
        numero = ""
    return {"nro_constancia": numero,
            "fecha_constancia": str(bloque.get("fecha_constancia") or "").strip()}


def _detraccion(c: Comprobante, config: dict, total: Decimal, neutral: bool = False) -> dict:
    """El bloque de la línea de detracción: el código SUNAT del bien o servicio (Catálogo 54), la tasa —la misma con
    la que se calcula el monto, que decide `detracciones.tasa_detraccion`— y el total del documento como base. Con
    vocabulario neutral no lleva el comodín de la constancia, que es de un sistema legacy.

    **Y SOLO el código de SUNAT** (4.0). Hasta la 3.10 el núcleo anotaba al lado `codigo_interno`, el de la T.G. 28
    del contribuyente, inventando el de SUNAT más «01» para lo que nadie hubiera mapeado. Era la única traducción al
    vocabulario de un ERP que hacía el asiento, y se la llevaban igual el CSV y STARSOFT, que escriben el de SUNAT a
    propósito. La hace ahora quien conoce esa tabla: `drivers.concar.proyeccion.codigo_interno_detraccion`.

    **Y la constancia del depósito** (2.6): el número y la fecha que alguien haya pegado, porque la detracción tiene
    dos tiempos —se provisiona al registrar y se paga días después— y hasta ahora el segundo no volvía al archivo.
    El número cae al COMODÍN cuando no hay constancia, que es el caso normal al exportar el mes; la fecha no, que
    una fecha inventada es peor que ninguna. Se resuelve aquí, y no en cada driver, porque es la contabilidad la
    que dice «esto está pendiente»: el driver solo elige en qué columna lo escribe, si es que tiene una."""
    bloque = c.detraccion or {}
    sunat = str(bloque.get("codigo") or "").strip()
    tasa = tasa_detraccion(c, config)
    return _limpio({"codigo": sunat,
                    "tasa": format(Decimal(tasa).normalize(), "f") if tasa > 0 else "", "base": str(total),
                    **constancia_de(c, config, comodin=not neutral)})


def lineas_del_comprobante(c: Comprobante, config: dict, limites: tuple[date, date], correlativo: str,
                           opciones: Any = None, es_venta: bool = False,
                           centro_en_anexo: frozenset[str] = CENTRO_EN_ANEXO,
                           vocabulario: str = "legacy") -> list[LineaDiario]:
    """Un comprobante → sus líneas de diario (de 2 a 5, más una por parte si la base va repartida), en el orden
    del manual de asientos. `centro_en_anexo` dice qué líneas llevan además el centro en su anexo auxiliar
    (`principal`, `tercero`).

    `vocabulario="neutral"` (1.1) arma las mismas líneas —las mismas cuentas, sentidos, importes y roles— sin el
    vocabulario de un sistema legacy: sin sub-diario ni correlativo, sin la sigla del documento ni de su referencia, y
    con la detracción sobre el propio comprobante en vez del documento comodín `DR` y `9999999999`."""
    # Lo que no mueve dinero no tiene asiento que armar, y se decide ANTES de pedir cuentas: un comprobante dado de
    # baja por SUNAT llega con todos sus importes en cero, y hasta la 3.5.0 pedía cuenta contable para acabar
    # produciendo dos líneas a `0.00` que cuadraban entre sí. Se puede volver al comportamiento anterior con
    # `asentar_sin_efecto_contable`. El comprobante sigue en el registro que se declara a SUNAT: eso no lo decide aquí.
    if sin_efecto_contable(c) and not asienta_sin_efecto(config):
        return []
    neutral = vocabulario == "neutral"
    moneda = (c.moneda or "PEN").upper()
    # A qué cuentas va la base: lo decide la imputación del documento, que llega aparte (una línea por parte si
    # trae reparto), o lo de siempre (`partes_de`). Una parte sin cuenta detiene el asiento igual que una fila sin
    # ella, y un reparto que no suma la base también: ese asiento no cuadraría.
    partes = partes_de(c, config, es_venta)
    if not all(cuenta for cuenta, _, _ in partes):
        raise SinCuenta([c])
    if reparto_no_cuadra(c, config, es_venta):
        raise RepartoNoCuadra([c])
    es_honorarios = not es_venta and c.tipo_cp == TIPO_HONORARIOS
    invierte = c.tipo_cp in TIPOS_INVIERTEN
    total = Decimal(c.total or 0).quantize(CENTIMO)
    # Compras: boleta y recibo por honorarios no dan crédito fiscal → todo al gasto, sin línea de IGV. En
    # VENTAS la boleta emitida SÍ lleva su IGV (débito fiscal del emisor). La regla vive en `igv.py`: la
    # comprobación de que un reparto cuadra con la base la necesita igual.
    igv = igv_del_asiento(c, es_venta)
    base = base_imputable(c, es_venta)
    ruc = (c.contraparte_doc or "").strip()
    usa_centros = config.get("usa_centros_costo", True)                                   # apagado: sin centro
    # El doble anexo del tercero lleva el centro del comprobante; con la base repartida, solo si todas las
    # partes comparten uno: con dos centros distintos no hay uno que poner.
    centros = {(centro or "").strip() for _, centro, _ in partes}
    centro_comun = (next(iter(centros)) if len(centros) == 1 else "") if usa_centros else ""
    serie_numero = serie_numero_de(c, opciones)
    # UNA sola glosa para TODAS las líneas, la misma y sin adornos (John, 21-sep-2026). Hasta la 2.1 las
    # derivadas anteponían lo que las identificaba —`IGV - `, `RET 4TA - `, `DETRACCION - `—, y era
    # información repetida: qué es cada línea lo dice su `rol`, y su cuenta. El prefijo solo gastaba los
    # 30 caracteres que admite CONCAR en su columna de detalle. Cortarla sigue siendo cosa del driver.
    glosa = glosa_de(c)
    tasa_leida = tasa_calculada(igv, Decimal(c.base_gravada or 0))
    tasa = "" if tasa_leida is None else texto_tasa(tasa_leida)
    # El tipo de cambio del comprobante, venga en la moneda que venga: es un HECHO suyo y la línea lo
    # transporta (texto exacto; `float` solo al escribir una celda). Hasta la 2.1 se descartaba cuando la
    # moneda era PEN, y eso dejaba sin él a un destino que lo pide en todas las filas —STARSOFT lo hace
    # (John, 21-sep-2026)—. Qué driver lo escribe y cuándo es decisión de FORMATO, y vive en cada driver:
    # CONCAR sigue llenando su columna solo en moneda extranjera, que es lo que valida su plantilla.
    tc = str(c.tipo_cambio) if c.tipo_cambio else ""
    emision = c.fecha_emision
    vencimiento = c.fecha_vencimiento or emision
    # Cada comprobante se asienta con SU fecha de emisión; el extemporáneo (mes anterior) cae al
    # primer día del periodo, y uno emitido después del periodo (error FECHA_POSTERIOR, que no bloquea
    # el Excel) al último: el asiento cae en el mes de esta fecha y todo debe caer en el mes del
    # proceso (un contador, 30-ago-2026). La fecha del documento se conserva aparte, siempre.
    primero, ultimo = limites
    fecha_asiento = min(max(emision, primero), ultimo) if emision else primero
    # Sentido de la partida: compras = gasto D / proveedor H; ventas = ingreso H / cliente D.
    # La nota de crédito invierte el caso que toque.
    normal = ("H", "D") if es_venta else ("D", "H")
    sentido_base, sentido_tercero = (normal[::-1] if invierte else normal)
    sub_diario_asiento = "" if neutral else sub_diario(c, config, es_venta)

    # `id_externo`: el id con el que el sistema que PRODUJO el comprobante lo conoce. Cierra el enlace entre la
    # línea, el comprobante y su imputación sin depender de la serie y el número, que son la identidad tributaria y
    # no la del sistema (1.0). No es `id_en_destino`, que está reservado para el id del sistema que RECIBE.
    # Sin `tipo`: la sigla con la que un sistema legacy llama al tipo (en CONCAR, su T.G. 06) la escribe su driver
    # desde la 4.0, con `resolucion.sigla_de_tipo`. Aquí viaja el código de SUNAT, que es el que manda; la sigla se
    # conservaba «por compatibilidad» desde los consumidores de la 0.6.
    documento = {"tipo_cp": c.tipo_cp,
                 "serie_numero": serie_numero, "id_externo": c.id_externo or "",
                 "fecha_emision": _iso(emision), "fecha_vencimiento": _iso(vencimiento)}
    referencia: dict[str, str] = {}
    if c.tipo_cp in TIPOS_NOTA and (c.ref_serie or c.ref_numero):
        numero_ref = _numero(c.ref_numero, opciones)
        referencia = {"tipo_cp": c.ref_tipo_cp,
                      "serie_numero": serie_y_numero(c.ref_serie, numero_ref),
                      "fecha": _iso(c.ref_fecha)}

    def linea(rol: str, importe: Decimal, cuenta_linea: str, sentido: str, glosa_linea: str = glosa,
              **extra) -> LineaDiario:
        # La clase es obligatoria en el estándar y `a_dict()` omite lo vacío, así que una línea sin ella produciría
        # un documento que el propio esquema 1.0 rechaza, y en silencio. Aquí se corta: es el último guardián, el que
        # alcanza a las cuentas que no son la de la base —la del tercero, la del IGV, la de la retención, la de la
        # detracción—, que vienen de la configuración o de la imputación. Lo que lo DICE antes, con su motivo y sin
        # excepción, es el diagnóstico (`resolucion.comprobantes_sin_clase`).
        clase_linea = pcge.clase_de(cuenta_linea)
        if not clase_linea:
            raise SinClase([c])
        campos = dict(cuenta=cuenta_linea, debe_haber=sentido, importe=str(Decimal(importe).quantize(CENTIMO)),
                      rol=rol, clase=clase_linea, sub_diario=sub_diario_asiento,
                      correlativo=correlativo, fecha=_iso(fecha_asiento),
                      moneda=moneda, tipo_cambio=tc, glosa=glosa_linea, documento=_limpio(documento),
                      referencia=_limpio(referencia), tasa_igv=tasa)
        campos.update(extra)
        return LineaDiario(**campos)

    # Recibo por honorarios con retención de 4ta: el gasto va por el TOTAL, la retención al Haber en
    # su cuenta de tributos, y a la cuenta por pagar solo el NETO que se le paga al profesional (regla
    # de contabilidad). Sin retención —lo normal con suspensión— el total completo va a la cuenta por pagar.
    retenido = Decimal(c.retencion or 0).quantize(CENTIMO) if es_honorarios else Decimal(0)
    if retenido > total:
        retenido = total
    # La CUENTA decide dónde va el centro (el contador, 09-sep-2026): en su línea si la cuenta lo lleva
    # habilitado, y si no, como referencia (anexo auxiliar) cuando el sistema lo elige así. Nunca en los
    # dos. El doble anexo del tercero es otra cosa y no depende de esto.
    def principal(cuenta: str, centro: str, importe: Decimal) -> LineaDiario:   # gasto (compras) / ingreso (ventas)
        centro = (centro or "").strip() if usa_centros else ""
        en_linea = lleva_centro(cuenta, config)
        return linea("principal", importe, cuenta, sentido_base, centro_costo=centro if en_linea else "",
                     anexo_auxiliar=centro if (not en_linea and "principal" in centro_en_anexo) else "")

    principales = [principal(cuenta, centro, base if importe is None else importe)
                   for cuenta, centro, importe in partes]
    # El bloque dice QUÉ TRIBUTO es, que es lo que el nombre del rol dejó de decir: `impuesto` a secas no sabría
    # distinguir el IGV del ISC o del ICBPER. El motor escribe el 1000, el único que lleva a una línea de asiento.
    # Las dos cuentas se leen igual —con su respaldo de fábrica—, y no es cosmética: `lineas_del_comprobante` es
    # pública, así que un ERP puede llamarla con la configuración que quiera. La del IGV se indexaba sin red mientras
    # la de la retención, en la línea siguiente, caía al defecto; con una `cuentas` sin la clave, la primera daba un
    # `KeyError: 'igv'` pelado, que no es un `ErrorContaperu` y por tanto no lo caza quien atrapa los errores del
    # motor. El espejo de esto en el diagnóstico (`resolucion.cuentas_del_asiento`) ya era simétrico.
    cuenta_impuesto = str((config.get("cuentas") or {}).get("igv") or CONFIG_POR_DEFECTO["cuentas"]["igv"])
    linea_impuesto = (linea("impuesto", igv, cuenta_impuesto, sentido_base, glosa,
                            impuesto={"codigo": TRIBUTO_IGV})
                      if igv > 0 else None)
    cuenta_retencion = str((config.get("cuentas") or {}).get("retencion_4ta") or CONFIG_POR_DEFECTO["cuentas"]["retencion_4ta"])
    # La categoría es `4` con certeza y no por deducción: esta línea solo nace de un recibo por honorarios
    # (`retenido > 0` exige `es_honorarios`). El tributo es el 3000, Impuesto a la Renta, y no el del IGV.
    linea_de_retencion = (linea("retencion", retenido, cuenta_retencion, sentido_tercero, glosa,
                                retencion={"codigo": TRIBUTO_RENTA, "categoria": CATEGORIA_RENTA_4TA})
                          if retenido > 0 else None)
    cuenta_del_tercero = cuenta_tercero(c, config, es_venta)
    anexo_tercero = centro_comun if ("tercero" in centro_en_anexo and not es_honorarios) else ""
    # El tercero: el proveedor en compras, el cliente en ventas.
    tercero = linea("tercero", total - retenido, cuenta_del_tercero, sentido_tercero,
                    contraparte_doc=ruc, anexo_auxiliar=anexo_tercero)

    # La detracción, calcada del Excel real validado en CONCAR (2026): el total COMPLETO queda en el
    # proveedor y se añaden DOS líneas por el monto detraído — el proveedor al Debe (se le pagará menos)
    # y la cuenta de detracciones al Haber, con su propio tipo de documento y el comodín 9999999999
    # (la constancia no existe todavía al provisionar). Lo dispara que la factura TENGA detracción, no
    # el sub-diario. Solo compras; el recibo por honorarios nunca.
    linea_recorte = linea_detraccion = None
    if not es_venta and not es_honorarios and tiene_detraccion(c):
        _, detraido = monto_detraccion(c, config)
        if detraido > 0:
            linea_recorte = linea("recorte", detraido, cuenta_del_tercero, sentido_base,
                                             contraparte_doc=ruc, anexo_auxiliar=anexo_tercero)
            # De QUÉ documento sale esta detracción: en una factura, del propio comprobante (lo que
            # CONCAR aceptó). En una NOTA que ya referencia la factura que corrige se RESPETA esa
            # referencia: ningún archivo validado dice otra cosa. Pendiente de una NC real.
            cuenta_detraccion = cuenta_por_pagar_detraccion(config["cuentas"], moneda)
            if neutral:
                # Sin documento comodín: la detracción es del propio comprobante, y la constancia llega después.
                documento_detraccion, referencia_detraccion = documento, referencia
            else:
                referencia_detraccion = referencia if referencia.get("tipo_cp") else {
                    "tipo_cp": c.tipo_cp, "serie_numero": serie_numero, "fecha": _iso(emision)}
                # El número del documento `DR` **es** la constancia del depósito: el comodín solo ocupa su sitio
                # mientras nadie la haya pegado (3.2). Hasta entonces aquí se escribía el comodín y nada más, así
                # que el vóucher llegaba a STARSOFT y a CONTASIS y no a CONCAR, que es donde vive esa columna —y
                # el LEEME de CONCAR ya prometía lo contrario. La FECHA del documento sigue siendo la de la
                # factura: ningún Excel validado dice que sea la del depósito, y eso no se decide de memoria.
                # Sin `tipo`: la sigla de la T.G. 06 (`DR`) es de CONCAR y la escribe su driver en la columna R
                # (`drivers.concar.proyeccion.tipo_doc_detraccion`). Lo demás del comodín se queda, porque es
                # contabilidad y no formato: dice que este depósito está pendiente.
                documento_detraccion = {"serie_numero": constancia_de(c, config)["nro_constancia"],
                                        "id_externo": c.id_externo or "",
                                        "fecha_emision": _iso(emision), "fecha_vencimiento": _iso(vencimiento)}
            linea_detraccion = linea("detraccion", detraido, cuenta_detraccion, sentido_tercero,
                                     glosa, contraparte_doc=ruc,
                                     documento=_limpio(documento_detraccion), referencia=_limpio(referencia_detraccion),
                                     detraccion=_detraccion(c, config, total, neutral))

    if es_venta and not invierte:
        # Venta normal: cliente (D) · IGV (H) · ingreso (H).
        #
        # El IGV va ANTES del ingreso desde la 2.2 (John, 21-sep-2026). Lo piden dos archivos reales de STARSOFT
        # —una hoja de su plantilla y un TXT de otro generador— que ordenan así las tres cuentas, y en compras el
        # motor ya lo hacía: el IGV sigue al principal, no al revés. Era la única asimetría entre los dos libros.
        orden = [tercero, linea_impuesto, *principales]
    else:
        # Compras (y NC de venta, que invierte): principal · IGV · retención · tercero · detracción.
        orden = [*principales, linea_impuesto, linea_de_retencion, tercero, linea_recorte, linea_detraccion]
    return [ln for ln in orden if ln is not None]


def lineas_e_indice_del_libro(libro: Libro, comprobantes: list[Comprobante], config: dict,
                              correlativos: dict[str, int], opciones: Any = None,
                              centro_en_anexo: frozenset[str] = CENTRO_EN_ANEXO, vocabulario: str = "legacy",
                              ) -> tuple[list[LineaDiario], dict[str, dict], tuple[ComprobanteDelAsiento, ...]]:
    """Todos los comprobantes de un libro → sus líneas numeradas por sub-diario (`MMNNNN`), el rango de correlativos
    que usó cada sub-diario y el índice: qué tramo de líneas es de qué comprobante, con su cabecera
    (`asiento.indice`). Es la entrada de cualquier driver de asientos. Con `vocabulario="neutral"` no numera: no hay
    sub-diarios, y los rangos salen vacíos."""
    es_venta = libro.es_venta
    neutral = vocabulario == "neutral"
    if neutral:
        numeros, rangos = [""] * len(comprobantes), {}
    else:
        numeros, rangos = numerar_en_orden(comprobantes, config, libro.periodo, correlativos, es_venta)
    limites = limites_del_periodo(libro)
    lineas: list[LineaDiario] = []
    indice: list[ComprobanteDelAsiento] = []
    for posicion, (c, numero) in enumerate(zip(comprobantes, numeros)):
        propias = lineas_del_comprobante(c, config, limites, numero, opciones, es_venta, centro_en_anexo, vocabulario)
        indice.append(ComprobanteDelAsiento(posicion=posicion, sub_diario="" if neutral else sub_diario(c, config, es_venta),
                                            correlativo=numero, desde=len(lineas), hasta=len(lineas) + len(propias),
                                            cabecera=cabecera_de(c)))
        lineas.extend(propias)
    return lineas, rangos, tuple(indice)


class LineaSinComprobante(ValueError):
    """Una línea del asiento que llega de fuera y no se puede atribuir a ningún comprobante del documento."""


def indice_de_lineas_dadas(comprobantes: list[Comprobante], lineas: list[LineaDiario],
                           ) -> tuple[ComprobanteDelAsiento, ...]:
    """Unas líneas que YA vienen armadas → el índice de qué tramo es de qué comprobante (5.2).

    Es la vuelta de `lineas_e_indice_del_libro`: ahí el índice nace de generar las líneas, y aquí de reconocerlas.
    Hace falta porque un driver de asientos escribe cada fila **con hechos del comprobante que ninguna línea
    guarda** —el Libro Diario del PLE saca cuatro de sus veintiún campos de la cabecera: el tipo de documento del
    tercero, la serie, el número y el vencimiento—, y sin índice saldrían incompletas en silencio
    (`drivers/kit/forma.exigir_indice`).

    **El enlace es `linea.documento.id_externo`**, que el estándar puso en la línea justamente para esto
    ([enmienda 0009](../../estandar/enmiendas/0009-id-externo-en-la-linea.md)). No se adivina por cuenta ni por
    importe.

    Y **no se renumera nada**: el `sub_diario` y el `correlativo` salen de las propias líneas, así que el CUO que
    escriba el destino es el que puso quien las produjo. Renumerar aquí cambiaría el número de un asiento que ya
    salió.

    Dos cosas se rechazan en voz alta, porque pasarlas por alto daría un archivo incompleto que parece correcto:
    una línea sin `id_externo` o con uno que ningún comprobante tiene, y las líneas de un mismo comprobante **no
    contiguas** —el índice es un tramo `desde`/`hasta`, así que un asiento partido en dos trozos no se puede
    representar—."""
    de_su_id: dict[str, tuple[int, Comprobante]] = {}
    for posicion, c in enumerate(comprobantes):
        if c.id_externo:
            de_su_id[str(c.id_externo)] = (posicion, c)

    indice: list[ComprobanteDelAsiento] = []
    vistos: set[str] = set()
    i = 0
    while i < len(lineas):
        id_externo = str((lineas[i].documento or {}).get("id_externo") or "")
        if not id_externo:
            raise LineaSinComprobante(
                f"la línea {i + 1} del asiento no dice de qué comprobante es: le falta `documento.id_externo`, "
                "que es el enlace con el bloque `comprobantes`")
        if id_externo not in de_su_id:
            raise LineaSinComprobante(
                f"la línea {i + 1} del asiento dice ser del comprobante {id_externo!r}, que no está en el documento")
        if id_externo in vistos:
            raise LineaSinComprobante(
                f"las líneas del comprobante {id_externo!r} no van seguidas: el índice de un asiento es un tramo, "
                "así que un comprobante partido en dos trozos no se puede representar")
        vistos.add(id_externo)
        desde = i
        while i < len(lineas) and str((lineas[i].documento or {}).get("id_externo") or "") == id_externo:
            i += 1
        posicion, c = de_su_id[id_externo]
        indice.append(ComprobanteDelAsiento(posicion=posicion, sub_diario=lineas[desde].sub_diario,
                                            correlativo=lineas[desde].correlativo, desde=desde, hasta=i,
                                            cabecera=cabecera_de(c)))
    return tuple(indice)


def rangos_de_lineas_dadas(indice: tuple[ComprobanteDelAsiento, ...]) -> dict[str, dict]:
    """El rango de correlativos que usó cada sub-diario, leído de unas líneas dadas en vez de al numerarlas.

    Mantiene la forma que `numerar_en_orden` devuelve, para que el resumen de una exportación diga lo mismo por las
    dos puertas: hasta la 1.2.0 la respuesta cambiaba según por dónde entrara el mismo documento, y eso se arregló
    una vez."""
    rangos: dict[str, dict] = {}
    for entrada in indice:
        if not entrada.sub_diario or not entrada.correlativo:
            continue
        codigo = str(entrada.correlativo)
        n = int(codigo[-4:] or 0)
        r = rangos.setdefault(entrada.sub_diario, {"desde": n, "hasta": n, "comprobantes": 0, "mes": codigo[:-4]})
        r["desde"], r["hasta"] = min(r["desde"], n), max(r["hasta"], n)
        r["comprobantes"] += 1
    # Las mismas cuatro claves derivadas que pone `numerar_en_orden`, y en el mismo orden: el resumen de una
    # exportación tiene que decir lo mismo por las dos puertas.
    for r in rangos.values():
        mes = r.pop("mes")
        r["desde_codigo"], r["hasta_codigo"] = f"{mes}{r['desde']:04d}", f"{mes}{r['hasta']:04d}"
        r["desborda"] = r["hasta"] > 9999
    return rangos


def lineas_del_libro(libro: Libro, comprobantes: list[Comprobante], config: dict, correlativos: dict[str, int],
                     opciones: Any = None, centro_en_anexo: frozenset[str] = CENTRO_EN_ANEXO,
                     ) -> tuple[list[LineaDiario], dict[str, dict]]:
    """Todos los comprobantes de un libro → sus líneas, numeradas por sub-diario (`MMNNNN`), y el rango de correlativos
    que usó cada sub-diario, que es lo que se recuerda para proponer el siguiente. Con el índice de cada comprobante:
    `lineas_e_indice_del_libro`."""
    lineas, rangos, _ = lineas_e_indice_del_libro(libro, comprobantes, config, correlativos, opciones,
                                                  centro_en_anexo)
    return lineas, rangos
