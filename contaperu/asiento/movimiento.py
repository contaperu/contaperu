"""Las líneas de diario de un movimiento de tesorería: el dinero, contabilizado (12.7).

Hermano de `motor.lineas_del_comprobante` y no una rama suya, porque no comparten ni una regla: allí hay IGV,
detracción, honorarios y notas de crédito; aquí hay **dos caras y un importe**. Lo que sí comparten es todo lo que
viene después —`LineaDiario`, el cuadre, la huella, el resumen—, que no sabe de dónde salió la línea.

**No inventa ninguna regla contable, y eso es lo que lo hace posible.** La que gobierna esto ya está publicada,
con su fuente, en el catálogo del estándar (`efectos_de_tesoreria`, NIC 7):

- una **entrada** lleva la cuenta de efectivo al DEBE, y la contrapartida la pone la imputación;
- una **salida**, al HABER;
- una **transferencia** entre cuentas propias es el único efecto cuyas **dos** patas son cuentas declaradas, así
  que es el único que no necesita imputación — y por eso no es un flujo de efectivo (NIC 7 §9).

De dónde sale cada cosa, que es la mitad del diseño:

| Qué | De dónde |
|---|---|
| la cuenta de efectivo (la 104) | `CuentaBancaria.cuenta_contable` del maestro, buscada por `movimiento.cuenta`. **El motor no la deriva** |
| la contrapartida | `imputaciones_de_movimientos`, igual que la cuenta de un gasto. «Sin imputación no hay cuenta» |
| el lado | `tesoreria.efecto_de(movimiento, imputacion)` |
| la glosa | `tesoreria.glosa_de_movimiento`, con su cadena de respaldo: ninguna línea sale sin glosa |

**El ITF es su propio asiento** ([enmienda 0028](../../estandar/enmiendas/0028-un-cargo-del-banco-es-su-propio-movimiento.md)):
un pago de 2 000 con 0,50 de ITF son dos asientos, no una línea más. Se asienta `6412` contra la cuenta de
efectivo, y **su importe nunca se calcula**: lo dice el banco. La fuente es el criterio de John del 13-oct-2026:
*«el ITF se registra en base a lo que dice la constancia de pago o los movimientos bancarios… un asiento contable
se da por hechos fehacientes y sustentados (vóucher de pago o estado de cuenta)»*. El `40181` no entra: el banco
ya lo retuvo, así que no queda nada por pagar.

**El orden de las líneas es el Debe primero**, que es lo único que compras y ventas ya cumplen hoy. Importa
decidirlo una vez y escribirlo, porque **el orden entra en la huella**.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from .. import pcge
from .. import tesoreria
from ..configuracion import CONFIG_POR_DEFECTO
from ..modelo import CENTIMO, CERO, Rasgos, monto, rasgos_de
from .faltas import (CuentaSinClase, LibroQueTodaviaNoSeNumera, MovimientoSinImputar,
                     SinCuentaDeEfectivo, TraspasoEnDosPatas)
from .indice import CabeceraDeMovimiento, MovimientoDelAsiento
from .lineas import LineaDiario
from . import comun
from .comun import iso as _iso, limpio as _limpio
from ..modelo.accesores import campo as _campo
from .resolucion import limites_del_periodo, lleva_centro

# El elemento del PCGE en el que vive el efectivo: «10 · EFECTIVO Y EQUIVALENTES AL EFECTIVO» (PCGE 2026, p. 17).
# Es la fuente con la que la regla del rol distingue la línea del dinero de la de un gasto, y el motivo por el que
# una cuenta de efectivo que no empiece así se avisa.
GRUPO_EFECTIVO = "10"

# La clave de la cuenta del ITF en la configuración. El gasto es la `6412` del PCGE («Impuesto a las transacciones
# financieras», p. 40), escrita a seis dígitos como todas las de aquí, que es como numeran CONCAR y CONTASIS.
CUENTA_ITF = "itf"




def cuenta_de_efectivo(cual: str, cuentas: dict) -> str:
    """La cuenta contable con la que se asienta esa cuenta bancaria, o se para diciendo por qué no se puede.

    Dos motivos distintos y los dos se nombran: el `id` no está en el maestro —nadie declaró esa cuenta— o está y
    no trae su cuenta contable, que el motor **no adivina** porque cada empresa abre las divisionarias que quiere.
    """
    cuenta = cuentas.get(str(cual or "").strip()) if cuentas else None
    if cuenta is None:
        raise SinCuentaDeEfectivo([str(cual or "")], "no está en el maestro de cuentas bancarias")
    contable = str(_campo(cuenta, "cuenta_contable") or "").strip()
    if not contable:
        raise SinCuentaDeEfectivo([str(cual or "")], "declarada sin su cuenta contable")
    return contable


def traspasos_en_dos_patas(movimientos, imputaciones: dict) -> list[str]:
    """Los traspasos que vienen declarados por sus DOS movimientos, que contarían el dinero dos veces.

    Un par recíproco es: dos movimientos de sentidos opuestos, por el mismo importe, cada uno en la cuenta que el
    otro declara como su `cuenta_propia`. Se mira aquí, con todos los movimientos delante, porque desde uno solo
    no se puede ver — igual que `Movimiento.efecto` nunca devuelve `transferencia`, porque una línea sola no sabe
    que es la mitad de un traspaso."""
    traspasos = []
    for m in movimientos:
        imputacion = imputaciones.get(str(_campo(m, "id_externo") or ""))
        destino = str(_campo(imputacion, "cuenta_propia") or "") if imputacion is not None else ""
        if destino:
            traspasos.append((str(_campo(m, "cuenta") or ""), destino, monto(_campo(m, "importe")),
                              str(_campo(m, "sentido") or ""), m))
    dobles, vistos = [], []
    for origen, destino, importe, sentido, m in traspasos:
        for otro_origen, otro_destino, otro_importe, otro_sentido, otro in vistos:
            if (origen, destino) == (otro_destino, otro_origen) and importe == otro_importe \
                    and sentido != otro_sentido:
                dobles.append(f"{origen} ↔ {destino} por {importe}")
        vistos.append((origen, destino, importe, sentido, m))
    return dobles


def lineas_del_movimiento(m: Any, imputacion: Any, cuentas: dict, config: dict,
                          limites: tuple[date, date], correlativo: str = "",
                          opciones: Any = None, libro: Rasgos | None = None,
                          vocabulario: str = "neutral") -> list[LineaDiario]:
    """Las líneas de diario de un movimiento, cuadradas entre ellas.

    `cuentas` es el maestro **ya indexado** (`tesoreria.por_id`) y no una cuenta resuelta, porque un traspaso
    necesita dos: la del movimiento y la que su imputación declara.

    `vocabulario` es `neutral` por defecto, al revés que en el comprobante: aquí lo legacy es lo que todavía no
    existe —ni sub-diario ni correlativo tienen clave de configuración hasta que un archivo real los pida—.

    Devuelve las líneas del pago y, si el banco descontó el ITF sin darle fila, **las dos de su propio asiento**.
    Cada grupo cuadra por su cuenta: el ITF no se resta del importe del pago, porque restarlo descuadraría el
    asiento y escondería un cargo que el banco sí hizo."""
    rasgos = rasgos_de(libro) if libro is not None else None
    neutral = vocabulario == "neutral"
    efecto = tesoreria.efecto_de(m, imputacion)
    importe = monto(_campo(m, "importe"))
    moneda = str(_campo(m, "moneda") or "").upper()
    nombre = str(_campo(m, "constancia") or "") or str(_campo(m, "referencia") or "")

    efectivo = cuenta_de_efectivo(_campo(m, "cuenta"), cuentas)
    if not moneda:
        moneda = str(_campo(cuentas.get(str(_campo(m, "cuenta") or "")), "moneda") or "PEN").upper()

    primero, ultimo = limites
    fecha_movimiento = _campo(m, "fecha")
    fecha_asiento = min(max(fecha_movimiento, primero), ultimo) if fecha_movimiento else primero

    # El documento de la línea: el papel que prueba el movimiento. **Sin `tipo_cp`**, porque un vóucher del banco
    # no es un comprobante de SUNAT — el mismo precedente que la línea de la detracción, cuyo documento tampoco lo
    # es. El `id_externo` es lo que permite reconocer estas líneas si el documento vuelve a entrar.
    documento = _limpio({"serie_numero": nombre, "id_externo": str(_campo(m, "id_externo") or ""),
                         "fecha_emision": _iso(fecha_movimiento)})
    glosa = tesoreria.glosa_de_movimiento(m, imputacion)
    sub_diario = "" if neutral or rasgos is None else rasgos.sub_diario

    def linea(cuenta: str, sentido: str, cuanto: Decimal, glosa_linea: str = "", **extra) -> LineaDiario:
        clase = pcge.clase_de(cuenta)
        if not clase:
            raise CuentaSinClase([cuenta])
        campos = dict(cuenta=cuenta, debe_haber=sentido, importe=str(Decimal(cuanto).quantize(CENTIMO)),
                      clase=clase, sub_diario=sub_diario, correlativo=correlativo, fecha=_iso(fecha_asiento),
                      moneda=moneda, glosa=(glosa_linea or glosa), documento=dict(documento))
        campos.update(extra)
        return LineaDiario(**campos)

    # El lado del efectivo lo dice el efecto, y el efecto lo dice el catálogo. Una entrada al DEBE, una salida al
    # HABER; en un traspaso manda el sentido del movimiento que lo declara, porque es el que vimos.
    entra = efecto == tesoreria.ENTRADA or (efecto == tesoreria.TRANSFERENCIA and not _campo(m, "es_cargo"))
    lado_efectivo, lado_contrario = ("D", "H") if entra else ("H", "D")
    medio = str(_campo(m, "medio_pago") or "")
    del_efectivo = linea(efectivo, lado_efectivo, importe, medio_pago=medio)

    if efecto == tesoreria.TRANSFERENCIA:
        # El único efecto sin imputación: sus dos patas son cuentas que el contribuyente declaró.
        otra = linea(cuenta_de_efectivo(_campo(imputacion, "cuenta_propia"), cuentas), lado_contrario, importe)
        contrarias = [otra]
    else:
        if imputacion is None:
            raise MovimientoSinImputar([nombre or str(_campo(m, "id_externo") or "")])
        contrarias = _contrapartidas(m, imputacion, importe, lado_contrario, linea, config)

    del_pago = [del_efectivo, *contrarias] if entra else [*contrarias, del_efectivo]
    return del_pago + _asiento_del_itf(m, linea, lado_efectivo, efectivo, config)


def _contrapartidas(m: Any, imputacion: Any, importe: Decimal, lado: str, linea, config: dict) -> list[LineaDiario]:
    """La otra cara, que pone el ERP: una cuenta, o una por cada parte cuando el movimiento se reparte.

    El reparto ya viene cuadrado: `ImputacionDeMovimiento.exigir_que_sume` lo bloqueó al leer el documento, exacto
    y sin tolerancia. Aquí solo se escribe."""
    reparto = list(_campo(imputacion, "reparto") or [])
    contraparte_del_movimiento = str(_campo(m, "contraparte_doc") or "")
    if not reparto:
        cuenta = str(_campo(imputacion, "cuenta_contable") or "")
        if not cuenta:
            raise MovimientoSinImputar([str(_campo(m, "id_externo") or "")])
        return [_una_contrapartida(linea, cuenta, lado, importe,
                                   str(_campo(imputacion, "centro_costo") or ""),
                                   str(_campo(imputacion, "contraparte_doc") or "") or contraparte_del_movimiento,
                                   tesoreria.glosa_de_movimiento(m, imputacion), config)]
    return [_una_contrapartida(linea, str(_campo(p, "cuenta_contable") or ""), lado, monto(_campo(p, "importe")),
                               str(_campo(p, "centro_costo") or ""),
                               str(_campo(p, "contraparte_doc") or "") or contraparte_del_movimiento,
                               tesoreria.glosa_de_movimiento(m, imputacion, p), config)
            for p in reparto]


def _una_contrapartida(linea, cuenta: str, lado: str, importe: Decimal, centro: str, contraparte: str,
                       glosa: str, config: dict) -> LineaDiario:
    """Una línea de la otra cara. El centro va si la cuenta lo lleva, con la MISMA regla que un comprobante
    (`cuentas_con_centro`): una cuenta de gasto lo lleva y la del proveedor no, y eso no cambia porque el dinero
    venga de un banco."""
    usa_centros = config.get("usa_centros_costo", True) if config else True
    en_linea = lleva_centro(cuenta, config or {})
    return linea(cuenta, lado, importe, glosa,
                 centro_costo=(centro if (usa_centros and en_linea) else ""),
                 contraparte_doc=contraparte)


def _asiento_del_itf(m: Any, linea, lado_efectivo: str, efectivo: str, config: dict) -> list[LineaDiario]:
    """El asiento del ITF, cuando el banco lo descontó sin darle su propia fila.

    **Son dos líneas y un asiento aparte** (enmienda 0028): el gasto contra la cuenta de efectivo, siempre en ese
    sentido —el titular lo paga cobre o pague, que es lo que `tesoreria.cuadra` ya sabía al restarlo del saldo en
    los dos sentidos—. Su importe lo dice el banco y **no se calcula**: el asiento se sustenta en el documento
    fehaciente, no en una tasa.

    Un banco que le da su fila al ITF no pasa por aquí: ese cargo es su propio movimiento, con su imputación."""
    itf = _campo(m, "itf")
    if itf is None or monto(itf) <= CERO:
        return []
    cuenta = str(((config or {}).get("cuentas") or {}).get(CUENTA_ITF)
                 or CONFIG_POR_DEFECTO["cuentas"][CUENTA_ITF])
    gasto = linea(cuenta, "D", monto(itf))
    salida = linea(efectivo, "H", monto(itf))
    return [gasto, salida]


def cabecera_de_movimiento(m: Any, imputacion: Any, cuentas: dict) -> CabeceraDeMovimiento:
    """Los hechos del movimiento que un driver necesita al lado de sus líneas.

    Lleva dos cosas que el movimiento **no** trae y que ninguna línea guarda: la `cuenta_contable` con la que se
    asentó —que sale del maestro— y el `efecto` ya compuesto con su imputación, que es la única forma de saber que
    un cargo era la mitad de un traspaso."""
    cuenta = cuentas.get(str(_campo(m, "cuenta") or "")) if cuentas else None
    itf = _campo(m, "itf")
    return CabeceraDeMovimiento(
        cuenta=str(_campo(m, "cuenta") or ""),
        cuenta_contable=str(_campo(cuenta, "cuenta_contable") or "") if cuenta is not None else "",
        fecha=_iso(_campo(m, "fecha")), fecha_valor=_iso(_campo(m, "fecha_valor")),
        descripcion=str(_campo(m, "descripcion") or ""), importe=str(monto(_campo(m, "importe"))),
        sentido=str(_campo(m, "sentido") or ""), efecto=tesoreria.efecto_de(m, imputacion),
        moneda=str(_campo(m, "moneda") or ""), referencia=str(_campo(m, "referencia") or ""),
        constancia=str(_campo(m, "constancia") or ""),
        contraparte_tipo_doc=str(_campo(m, "contraparte_tipo_doc") or ""),
        contraparte_doc=str(_campo(m, "contraparte_doc") or ""),
        contraparte_nombre=str(_campo(m, "contraparte_nombre") or ""),
        medio_pago=str(_campo(m, "medio_pago") or ""),
        itf="" if itf is None else str(monto(itf)),
        id_externo=str(_campo(m, "id_externo") or ""))


def lineas_e_indice_de_movimientos(libro: Any, movimientos, config: dict, correlativos: dict | None = None,
                                   vocabulario: str = "neutral",
                                   ) -> tuple[list[LineaDiario], dict, tuple[MovimientoDelAsiento, ...]]:
    """Las líneas del asiento de un libro de tesorería, su índice y sus rangos por sub-diario.

    Hermana de `motor.lineas_e_indice_del_libro` y con la misma forma de salida, para que lo que viene después
    —cuadrar, hashear, escribir— no tenga que saber de cuál de las dos salió.

    **La imputación y el maestro viajan dentro de `config`**, que es el mismo sitio por el que ya llega la
    imputación de un comprobante: «se le entrega al núcleo dentro de la configuración, que es lo que ya recibe todo
    el asiento».

    Con vocabulario `neutral` no numera —`rangos` sale vacío—, igual que el comprobante: los correlativos de
    tesorería esperan su sub-diario, y el sub-diario espera un archivo real que lo pida."""
    rasgos = rasgos_de(libro)
    if rasgos.origen != "movimientos":
        raise ValueError(f"Un libro {rasgos.tipo!r} no sale de movimientos sino de {rasgos.origen!r}: "
                         "sus líneas las arma `asiento.lineas_e_indice_del_libro`")
    if vocabulario != "neutral" and not rasgos.sub_diario:
        raise LibroQueTodaviaNoSeNumera(rasgos.tipo)

    imputaciones = (config or {}).get("imputaciones_de_movimientos") or {}
    # El maestro llega por las dos formas, y las dos son legítimas: **la lista** es como la guarda la configuración
    # —es lo que una pantalla de ajustes edita y lo que `Campo("cuentas_bancarias", "lista")` declara— y **el
    # diccionario** es como se usa, buscando por el `id` con el que un movimiento nombra su cuenta. Se normaliza
    # aquí en vez de guardarla transformada en la configuración, que daría a una misma clave dos tipos según por
    # dónde entre, y la haría fallar su propia validación al pasar otra vez por `armado.config_para`.
    cuentas = (config or {}).get("cuentas_bancarias") or {}
    if isinstance(cuentas, (list, tuple)):
        cuentas = tesoreria.por_id(list(cuentas))
    dobles = traspasos_en_dos_patas(movimientos, imputaciones)
    if dobles:
        raise TraspasoEnDosPatas(dobles)

    limites = limites_del_periodo(libro) if hasattr(libro, "anio") else None
    lineas: list[LineaDiario] = []
    indice: list[MovimientoDelAsiento] = []
    sin_imputar: list[str] = []
    for posicion, m in enumerate(movimientos):
        imputacion = imputaciones.get(str(_campo(m, "id_externo") or ""))
        if imputacion is None and not _campo(m, "itf"):
            # Se reúnen todas antes de parar: decirlas de una en una obliga a diez vueltas para arreglar diez.
            sin_imputar.append(str(_campo(m, "constancia") or "") or str(_campo(m, "referencia") or "")
                               or str(_campo(m, "id_externo") or ""))
            continue
        propias = lineas_del_movimiento(m, imputacion, cuentas, config, limites, "", None, rasgos, vocabulario)
        indice.append(MovimientoDelAsiento(posicion=posicion, sub_diario="", correlativo="",
                                           desde=len(lineas), hasta=len(lineas) + len(propias),
                                           cabecera=cabecera_de_movimiento(m, imputacion, cuentas)))
        lineas.extend(propias)
    if sin_imputar:
        raise MovimientoSinImputar(sin_imputar)
    return lineas, {}, tuple(indice)


class LineaSinMovimiento(ValueError):
    """Una línea del asiento que llega de fuera y no se puede atribuir a ningún movimiento del documento.

    Hermana de `LineaSinComprobante` y con su mismo papel en el otro camino: lo que se rechaza es lo que daría un
    archivo incompleto con pinta de correcto."""


def indice_de_movimientos_dados(movimientos, lineas: list[LineaDiario], config: dict | None = None,
                                ) -> tuple[MovimientoDelAsiento, ...]:
    """Unas líneas que YA vienen armadas → el índice de qué tramo es de qué movimiento (12.10).

    La vuelta de `lineas_e_indice_de_movimientos`, y hermana exacta de `motor.indice_de_lineas_dadas`: allí el
    índice nace de generar las líneas y aquí de reconocerlas. **El enlace es el mismo**,
    `linea.documento.id_externo`, que en un libro de movimientos es el del movimiento
    ([enmienda 0032](../../estandar/enmiendas/0032-el-documento-de-una-linea-de-tesoreria.md)). No se adivina por
    cuenta ni por importe.

    `config` se pide para reconstruir la cabecera entera —el `efecto` sale de la imputación y la `cuenta_contable`
    del maestro, y ninguna línea guarda ni una de las dos—. Sin él la cabecera sale sin esos dos campos, que es
    exactamente lo que `como_movimiento()` omite, así que **el bloque `movimientos` reescrito sale igual**; lo que
    se pierde es lo que vería un driver que lea `cabecera.a_dict()`.

    **Las dos líneas del ITF van dentro del tramo de su movimiento**, porque llevan su mismo `id_externo`: su
    asiento es aparte, pero el hecho que lo produjo es el mismo cargo.

    Se rechaza en voz alta lo mismo que en el otro camino: una línea sin `id_externo` o con uno que ningún
    movimiento tiene, y las líneas de un mismo movimiento **no contiguas**, porque el índice es un tramo."""
    imputaciones = (config or {}).get("imputaciones_de_movimientos") or {}
    cuentas = (config or {}).get("cuentas_bancarias") or {}
    if isinstance(cuentas, (list, tuple)):
        cuentas = tesoreria.por_id(list(cuentas))

    return comun.indice_de_lineas_por_id(
        movimientos, lineas, excepcion=LineaSinMovimiento, sustantivo="movimiento", bloque="movimientos",
        clase=MovimientoDelAsiento,
        cabecera=lambda m, id_externo: cabecera_de_movimiento(m, imputaciones.get(id_externo), cuentas))
