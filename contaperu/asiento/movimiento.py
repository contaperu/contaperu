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
from .faltas import (CuentaBancariaSinSubDiario, CuentaSinClase, LibroQueTodaviaNoSeNumera, MovimientoSinImputar,
                     SinCuentaDeEfectivo, TraspasoEnDosPatas)
from .indice import CabeceraDeMovimiento, MovimientoDelAsiento
from .lineas import LineaDiario
from . import comun
from .comun import iso as _iso, limpio as _limpio
# El número de una línea con la regla de ceros de su destino: el MISMO que escribe la línea de la compra, para que el
# documento de una parte que paga una factura salga escrito igual que el de su provisión (enmienda 0035).
from .comprobante import _numero
from ..modelo.coerciones import serie_y_numero
from ..modelo.accesores import campo as _campo
from .resolucion import limites_del_periodo, lleva_centro

# El bloque del documento que este motor sabe asentar. Es la IDENTIDAD del módulo, no una decisión: la guarda de
# abajo no elige camino —de eso se encargan las tablas de cada capa— sino que afirma «este motor es el del dinero»
# y manda al otro a quien se equivoque de puerta. Escrito como constante para que se lea así y para que no parezca
# uno de los `if` por nombre de libro que la 13.1 retiró.
MI_ORIGEN = "movimientos"

# El elemento del PCGE en el que vive el efectivo: «10 · EFECTIVO Y EQUIVALENTES AL EFECTIVO» (PCGE 2026, p. 17).
# Es la fuente con la que la regla del rol distingue la línea del dinero de la de un gasto, y el motivo por el que
# una cuenta de efectivo que no empiece así se avisa.
GRUPO_EFECTIVO = "10"

# La clave de la cuenta del ITF en la configuración. El gasto es la `6412` del PCGE («Impuesto a las transacciones
# financieras», p. 40), escrita a seis dígitos como todas las de aquí, que es como numeran CONCAR y CONTASIS.
CUENTA_ITF = "itf"

# Las cinco con que este módulo se niega a asentar un movimiento, en el orden en que se comprueban: el libro
# primero —se sabe antes de mirar una fila—, después lo que solo se ve con todos los movimientos delante, y al
# final las tres de cada uno. Viven aquí y no en la tabla `FALTAS` por lo que dice `faltas.py`: aquélla reparte
# faltas **por comprobante** y un movimiento no lo es. Es la lista de claves que `faltantes_de_movimientos`
# contesta y la que `diagnosticar` traduce, así que una falta nueva del dinero entra por aquí.
#
# **La sexta entra en la 15.14.0, `CuentaBancariaSinSubDiario`**, y es la que sustituye a la primera: tesorería se numera
# por el sub-diario de cada cuenta bancaria. `LibroQueTodaviaNoSeNumera` ya no se lanza, pero su clave se queda —siempre
# vacía— porque `diagnosticar` la publica y quitarla cambiaría su contrato.
FALTAS_DEL_MOVIMIENTO = (LibroQueTodaviaNoSeNumera, CuentaBancariaSinSubDiario, TraspasoEnDosPatas,
                         MovimientoSinImputar, SinCuentaDeEfectivo, CuentaSinClase)




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


def nombre_de_movimiento(m: Any) -> str:
    """Cómo se nombra un movimiento cuando hay que señalarlo: por el papel que lo prueba si lo tiene, por el número
    que le dio el banco si no, y por su `id_externo` cuando no trae ninguno de los dos.

    La misma regla que `api.revisar_tesoreria` usa en sus informes, con una cola más: aquí el nombre tiene que
    existir siempre, porque es con lo que una falta señala cuál arreglar."""
    return (str(_campo(m, "constancia") or "") or str(_campo(m, "referencia") or "")
            or str(_campo(m, "id_externo") or ""))


def imputaciones_y_cuentas(config: dict | None) -> tuple[dict, dict]:
    """Las dos cosas que todo camino de tesorería saca de la configuración: la imputación de cada movimiento y el
    maestro de cuentas bancarias **indexado por `id`**.

    El maestro llega por las dos formas, y las dos son legítimas: **la lista** es como la guarda la configuración
    —es lo que una pantalla de ajustes edita y lo que `Campo("cuentas_bancarias", "lista")` declara— y **el
    diccionario** es como se usa, buscando por el `id` con el que un movimiento nombra su cuenta. Se normaliza
    aquí en vez de guardarla transformada en la configuración, que daría a una misma clave dos tipos según por
    dónde entre, y la haría fallar su propia validación al pasar otra vez por `armado.config_para`."""
    imputaciones = (config or {}).get("imputaciones_de_movimientos") or {}
    cuentas = (config or {}).get("cuentas_bancarias") or {}
    if isinstance(cuentas, (list, tuple)):
        cuentas = tesoreria.por_id(list(cuentas))
    return imputaciones, cuentas


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
                          vocabulario: str = "neutral", sub_diario: str | None = None) -> list[LineaDiario]:
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
    # El sub-diario lo da quien numera —el de la cuenta bancaria, desde la 15.14.0— y, si no lo da, el del libro.
    if neutral:
        sub_diario = ""
    elif sub_diario is None:
        sub_diario = rasgos.sub_diario if rasgos is not None else ""

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
        contrarias = _contrapartidas(m, imputacion, importe, lado_contrario, linea, config, opciones)

    del_pago = [del_efectivo, *contrarias] if entra else [*contrarias, del_efectivo]
    return del_pago + _asiento_del_itf(m, linea, lado_efectivo, efectivo, config)


def _contrapartidas(m: Any, imputacion: Any, importe: Decimal, lado: str, linea, config: dict,
                    opciones: Any = None) -> list[LineaDiario]:
    """La otra cara, que pone el ERP: una cuenta, o una por cada parte cuando el movimiento se reparte.

    El reparto ya viene cuadrado: `ImputacionDeMovimiento.exigir_que_sume` lo bloqueó al leer el documento, exacto
    y sin tolerancia. Aquí solo se escribe.

    **La parte que nombra su comprobante lleva el documento de ese comprobante** (15.13.0, enmienda 0035): una 42 se
    lleva por documento, y en el Excel de pagos que un CONCAR real aceptó cada línea del proveedor lleva su factura
    —tipo, serie-número, fecha y vencimiento— y solo la del banco lleva el vóucher."""
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
                               (str(_campo(p, "contraparte_doc") or "")
                                or str((_campo(p, "comprobante") or {}).get("contraparte_doc") or "")
                                or contraparte_del_movimiento),
                               tesoreria.glosa_de_movimiento(m, imputacion, p), config,
                               documento=_documento_del_comprobante(_campo(p, "comprobante"), opciones))
            for p in reparto]


def _documento_del_comprobante(comprobante: Any, opciones: Any = None) -> dict | None:
    """El documento de la línea de una parte que nombra el comprobante que paga, o `None` para dejar el del vóucher.

    Escrito **como lo escribe la línea de ese comprobante en su compra** —el serie-número con la misma regla de ceros
    (`comprobante._numero`, según las opciones del destino) y el vencimiento que cae a la emisión—, porque el sistema
    de destino casa el pago con la provisión por ese documento: escrito distinto, no lo cancela."""
    c = dict(comprobante or {})
    if not c:
        return None
    emision = c.get("fecha_emision") or ""
    return _limpio({"tipo_cp": c.get("tipo_cp") or "",
                    "serie_numero": serie_y_numero((c.get("serie") or "").strip(), _numero(c.get("numero") or "", opciones)),
                    "fecha_emision": emision, "fecha_vencimiento": c.get("fecha_vencimiento") or emision})


def _una_contrapartida(linea, cuenta: str, lado: str, importe: Decimal, centro: str, contraparte: str,
                       glosa: str, config: dict, documento: dict | None = None) -> LineaDiario:
    """Una línea de la otra cara. El centro va si la cuenta lo lleva, con la MISMA regla que un comprobante
    (`cuentas_con_centro`): una cuenta de gasto lo lleva y la del proveedor no, y eso no cambia porque el dinero
    venga de un banco."""
    usa_centros = config.get("usa_centros_costo", True) if config else True
    en_linea = lleva_centro(cuenta, config or {})
    extra = {"documento": documento} if documento else {}
    return linea(cuenta, lado, importe, glosa,
                 centro_costo=(centro if (usa_centros and en_linea) else ""),
                 contraparte_doc=contraparte, **extra)


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

    Con vocabulario `neutral` no numera —`rangos` sale vacío—, igual que el comprobante.

    **Con uno legacy, numera por el sub-diario de la CUENTA BANCARIA de cada movimiento** (15.14.0): en CONCAR cada
    banco tiene el suyo —el 24 del BCP, el 26 del BBVA—, que el usuario declara en su maestro
    (`CuentaBancaria.sub_diario`), y el pago entra en el de su cuenta. El número es el de las compras: `MM` más cuatro
    dígitos, uno por movimiento en el orden recibido y empezando por lo que diga `correlativos` para cada sub-diario
    —el 1 si no lo dice—. Una cuenta sin sub-diario para el libro entero (`CuentaBancariaSinSubDiario`), nombrando las
    cuentas: hasta la 15.13 esto paraba siempre en `LibroQueTodaviaNoSeNumera`, porque el archivo real que dijera cuál
    era el sub-diario de bancos todavía no había llegado."""
    rasgos = rasgos_de(libro)
    if rasgos.origen != MI_ORIGEN:
        raise ValueError(f"Un libro {rasgos.tipo!r} no sale de movimientos sino de {rasgos.origen!r}: "
                         "sus líneas las arma `asiento.lineas_e_indice_del_libro`")
    neutral = vocabulario == "neutral"

    imputaciones, cuentas = imputaciones_y_cuentas(config)
    dobles = traspasos_en_dos_patas(movimientos, imputaciones)
    if dobles:
        raise TraspasoEnDosPatas(dobles)
    if not neutral:
        sin_sub_diario = cuentas_sin_sub_diario(movimientos, cuentas)
        if sin_sub_diario:
            raise CuentaBancariaSinSubDiario(sin_sub_diario)
    mes = str(getattr(libro, "periodo", "") or "")[4:6]
    contadores: dict[str, int] = {}
    rangos: dict[str, dict] = {}

    limites = limites_del_periodo(libro) if hasattr(libro, "anio") else None
    lineas: list[LineaDiario] = []
    indice: list[MovimientoDelAsiento] = []
    sin_imputar: list[str] = []
    for posicion, m in enumerate(movimientos):
        imputacion = imputaciones.get(str(_campo(m, "id_externo") or ""))
        if imputacion is None and not _campo(m, "itf"):
            # Se reúnen todas antes de parar: decirlas de una en una obliga a diez vueltas para arreglar diez.
            sin_imputar.append(nombre_de_movimiento(m))
            continue
        sub_diario, correlativo, n = "", "", 0
        if not neutral:
            sub_diario = sub_diario_de_la_cuenta(m, cuentas)
            n = contadores.setdefault(sub_diario, int((correlativos or {}).get(sub_diario, 1)))
            if n < 1:
                raise ValueError("Los correlativos empiezan en 1")
            correlativo = f"{mes}{n:04d}"
        propias = lineas_del_movimiento(m, imputacion, cuentas, config, limites, correlativo, None, rasgos,
                                        vocabulario, sub_diario=sub_diario)
        if not neutral:
            rango = rangos.setdefault(sub_diario, {"desde": n, "hasta": n - 1, "comprobantes": 0})
            rango["hasta"], rango["comprobantes"] = n, rango["comprobantes"] + 1
            contadores[sub_diario] = n + 1
        indice.append(MovimientoDelAsiento(posicion=posicion, sub_diario=sub_diario, correlativo=correlativo,
                                           desde=len(lineas), hasta=len(lineas) + len(propias),
                                           cabecera=cabecera_de_movimiento(m, imputacion, cuentas)))
        lineas.extend(propias)
    if sin_imputar:
        raise MovimientoSinImputar(sin_imputar)
    # Los mismos campos que el rango de un sub-diario de compras (`numerar_en_orden`): `comprobantes` cuenta asientos,
    # que aquí son movimientos, y es lo que quien exporta lee para proponer el correlativo del mes siguiente.
    for rango in rangos.values():
        rango["desde_codigo"], rango["hasta_codigo"] = f"{mes}{rango['desde']:04d}", f"{mes}{rango['hasta']:04d}"
        rango["desborda"] = rango["hasta"] > 9999
    return lineas, rangos, tuple(indice)


def sub_diario_de_la_cuenta(m: Any, cuentas: dict) -> str:
    """El sub-diario de la cuenta bancaria de un movimiento, o vacío: el de su maestro (`CuentaBancaria.sub_diario`)."""
    return str(_campo(cuentas.get(str(_campo(m, "cuenta") or "")), "sub_diario") or "").strip()


def cuentas_sin_sub_diario(movimientos, cuentas: dict) -> list[str]:
    """Las cuentas de estos movimientos que el maestro declara SIN sub-diario, cada una una vez y en el orden en que
    aparecen. Una cuenta que no está en el maestro no sale aquí: eso es `SinCuentaDeEfectivo`, y decirla dos veces
    mandaría a arreglar lo mismo por dos sitios."""
    sin: list[str] = []
    for m in movimientos:
        cuenta = str(_campo(m, "cuenta") or "")
        if cuenta in cuentas and not sub_diario_de_la_cuenta(m, cuentas) and cuenta not in sin:
            sin.append(cuenta)
    return sin


def faltantes_de_movimientos(libro: Any, movimientos, config: dict,
                             vocabulario: str = "neutral") -> dict[str, list[str]]:
    """Lo que impediría asentar estos movimientos, TODO de una vez y sin parar: lo que `diagnosticar` cuenta.

    Hermana de `resolucion.faltantes_para` y con su mismo papel —describir lo que la otra hace cumplir—, pero
    construida al revés, y el motivo es dónde vive cada regla. A un comprobante se le puede preguntar qué le falta
    **sin armar su asiento**, porque las reglas son suyas: `comprobantes_sin_cuenta` mira su imputación y ya está.
    A un movimiento no: lo que le falta solo se sabe armando su línea —la 104 sale del maestro, el lado sale del
    efecto, la clase sale de la cuenta que resulte—, así que esto **arma y recoge lo que se cae**, en vez de
    copiar las cinco comprobaciones a un segundo sitio donde envejecerían distinto. Las líneas se tiran; lo que se
    guarda es la falta. Es la misma garantía que el otro camino da con una sola lista de reglas, conseguida de la
    única forma que aquí sirve.

    Las cinco claves van **siempre**, vacías cuando no falta nada, y eso significa «esto se comprobó» —el mismo
    criterio de `faltantes_para`—. Ninguna cuelga de un requisito del destino (`contrato.exige`), porque los que
    un driver exige hoy están escritos sobre comprobantes y ninguno vale para una línea de tesorería; el hueco
    está declarado en `armado._asiento_de_movimientos`.

    Y lo que nombra cada lista es lo que hay que arreglar, que no siempre es el movimiento: la cuenta bancaria sin
    104 y la cuenta sin clase se dicen por la cuenta, porque el arreglo está en el maestro o en la imputación.
    """
    rasgos = rasgos_de(libro)
    faltan: dict[str, list[str]] = {clase.clave: [] for clase in FALTAS_DEL_MOVIMIENTO}

    imputaciones, cuentas = imputaciones_y_cuentas(config)
    if vocabulario != "neutral":
        faltan[CuentaBancariaSinSubDiario.clave] = cuentas_sin_sub_diario(movimientos, cuentas)
    faltan[TraspasoEnDosPatas.clave] = traspasos_en_dos_patas(movimientos, imputaciones)

    limites = limites_del_periodo(libro) if hasattr(libro, "anio") else None
    for m in movimientos:
        imputacion = imputaciones.get(str(_campo(m, "id_externo") or ""))
        if imputacion is None and not _campo(m, "itf"):
            faltan[MovimientoSinImputar.clave].append(nombre_de_movimiento(m))
            continue
        try:
            lineas_del_movimiento(m, imputacion, cuentas, config, limites, "", None, rasgos, vocabulario)
        except MovimientoSinImputar:
            faltan[MovimientoSinImputar.clave].append(nombre_de_movimiento(m))
        except SinCuentaDeEfectivo as falta:
            _sumar(faltan[SinCuentaDeEfectivo.clave], falta.cuales)
        except CuentaSinClase as falta:
            _sumar(faltan[CuentaSinClase.clave], falta.cuentas)
    return faltan


def _sumar(cuales: list[str], nuevas) -> None:
    """Añade sin repetir y en el orden en que aparecieron: dos movimientos de la misma cuenta sin 104 son **un**
    arreglo, no dos, y decirlo dos veces haría contar mal al que cuenta."""
    cuales.extend(cual for cual in nuevas if cual not in cuales)


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
    imputaciones, cuentas = imputaciones_y_cuentas(config)
    return comun.indice_de_lineas_por_id(
        movimientos, lineas, excepcion=LineaSinMovimiento, sustantivo="movimiento", bloque="movimientos",
        clase=MovimientoDelAsiento,
        cabecera=lambda m, id_externo: cabecera_de_movimiento(m, imputaciones.get(id_externo), cuentas))
