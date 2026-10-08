"""Lo que a un comprobante le falta para un destino que lo exige, y la puerta que lo hace cumplir.

`faltantes_para` **describe** y `exigir_requisitos` **lanza**: una sola lista de reglas para las tres cosas que
la consultan —exportar, armar el asiento y diagnosticar—, y así ninguna puede ser más laxa que otra. Cómo se
llama cada falta y a quién se le pide es el catálogo de `faltas.py`; aquí viven las reglas que lo comprueban.
"""
from __future__ import annotations

from ...modelo import Comprobante
from ...pcge import clase_de as _clase_de
from ...tributos.detracciones import (MARCA_SIRE, codigos_de, con_el_codigo_del_contador, esta_pendiente,
                                      normalizar_una)
from ..configuracion import MONEDAS_CODIGO
from ..faltas import FALTAS
from .clasificacion import (anulada_por_nota, con_efecto_contable, con_reparto, cuentas_del_asiento,
                            equivalencia_tipo, lleva_centro, reparto_no_cuadra, tiene_detraccion)
from .imputado import partes_de


def tipos_sin_sigla(comprobantes: list[Comprobante], config: dict) -> list[str]:
    """Códigos SUNAT presentes que no tienen sigla configurada (en orden de aparición)."""
    vistos: list[str] = []
    for c in comprobantes:
        if not equivalencia_tipo(c, config) and c.tipo_cp not in vistos:
            vistos.append(c.tipo_cp)
    return vistos


def monedas_sin_codigo(comprobantes: list[Comprobante], config: dict) -> list[str]:
    codigos = config.get(MONEDAS_CODIGO) or {}
    vistas: list[str] = []
    for c in comprobantes:
        moneda = (c.moneda or "PEN").upper()
        if not codigos.get(moneda) and moneda not in vistas:
            vistas.append(moneda)
    return vistas


def comprobantes_sin_cuenta(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[Comprobante]:
    """Las filas sin cuenta: basta con que a una parte de su base le falte (`partes_de`). Una parte del reparto
    no toma la cuenta por defecto: repartir entre la misma cuenta no reparte nada."""
    return [c for c in comprobantes if not all(cuenta for cuenta, _, _ in partes_de(c, config, es_venta))]


def comprobantes_anulados_con_deposito(comprobantes: list[Comprobante], config: dict) -> list[Comprobante]:
    """Las marcadas como anuladas cuya detracción YA tiene constancia de depósito: los dos hechos se contradicen.

    El estado se deduce de la constancia y de su fecha, nunca de lo que el bloque declare (`detracciones.estado_de`),
    así que un productor no puede conseguir que el motor se crea un depósito que no documentó."""
    return [c for c in comprobantes
            if anulada_por_nota(c, config) and tiene_detraccion(c) and not esta_pendiente(c, config)]


def comprobantes_sin_codigo_detraccion(comprobantes: list[Comprobante], config: dict) -> list[Comprobante]:
    """Las compras que SUNAT marcó con detracción y a las que todavía les falta el código del Catálogo 54.

    Mira la anotación `_marca_sire`, que es la afirmación de SUNAT, y no la detracción a secas: una detracción con un
    código que el contribuyente no reconoce ya se blanquea desde antes (`detracciones.normalizar`) y es otra regla,
    con otro caso real. Y usa `normalizar_una` para decidir si el código sirve, en vez de repetir aquí la prueba: una
    segunda copia de esa regla acabaría diciendo algo distinto.

    Las ventas nunca entran: el RVIE no tiene columna de detracción, así que el lector solo marca compras.

    **Y las que el contador declaró anuladas tampoco** (5.3.1). El campo `anulada_por_nota` entró en la 5.3
    cableado solo donde nacen las líneas (`motor.lineas_del_comprobante`) y no bajó hasta aquí, así que una compra
    del SIRE ya marcada seguía sin poder exportar hasta que le inventaran un código **que el asiento no iba a usar**:
    puesto el código, las líneas salen exactamente igual. Pedir un dato y acto seguido ignorarlo no es una guarda,
    es una friccion.

    No afloja la regla de la 0020, que existe porque «si el contador acepta el txt está consintiendo que tiene
    detracción» (John). `anulada_por_nota` es una declaración igual de explícita del mismo contador, y más fuerte:
    no dice «esta no tiene detracción», dice «esta factura ya no existe». La compra marcada por SUNAT que nadie
    declaró anulada sigue bloqueada, que son 221 de 3018 en el mes real de setiembre. Y la contradicción de verdad
    —anulada con su depósito ya hecho— la sigue parando `comprobantes_anulados_con_deposito`, que va aparte.

    La exclusión va AQUÍ y no en `faltantes_para`, donde vive el otro filtro de este estilo: `sin_efecto_contable`
    exime de **todas** las faltas, y esto solo de la detracción. A una factura anulada se le siguen pidiendo su
    cuenta, su centro y su sigla, porque sigue dando tres líneas y entra entera en el registro."""
    codigos = codigos_de(config)
    return [c for c in comprobantes
            if isinstance(c.detraccion, dict) and c.detraccion.get(MARCA_SIRE)
            and not anulada_por_nota(c, config)
            and normalizar_una(con_el_codigo_del_contador(c, config), codigos) is None]


def cuentas_sin_denominacion(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[str]:
    """Las cuentas que el asiento va a tocar y que la empresa **no ha dicho cómo se llaman**
    (`configuracion.denominacion_cuentas`), ordenadas y sin repetir.

    Se dice por CUENTA y no por comprobante, como la sigla o el código de moneda: lo que falta no es de un documento
    sino del plan de la empresa, y la lista con la que se arregla es la de cuentas a completar.

    Lo pide el detalle del plan contable del PLE (formato 5.3), cuyo campo 3 es obligatorio. El motor conoce el nombre
    de la divisionaria del PCGE —`101` es «Caja»— y **no sirve**: el catálogo llega hasta cinco dígitos y la empresa
    desagrega hasta donde quiera, así que de `101101` solo sabría decir «Caja» donde la empresa escribe «CAJA CHICA
    M.N.». Inventarlo sería declararle a SUNAT una denominación que el contribuyente no usa."""
    denominaciones = config.get("denominacion_cuentas") or {}
    faltan = {cuenta for c in comprobantes for cuenta in cuentas_del_asiento(c, config, es_venta)
              if not str(denominaciones.get(cuenta) or "").strip()}
    return sorted(faltan)


def comprobantes_sin_clase(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[Comprobante]:
    """Las filas que tocarían una cuenta cuyo elemento del PCGE no tiene clase contable: el 8 (saldos intermediarios
    de gestión) y el 0 (cuentas de orden). Se miran **todas** las cuentas de su asiento (`cuentas_del_asiento`), no
    solo la de la base: basta con que una no tenga clase para que el asiento no se pueda armar, porque esa línea
    saldría sin `clase` y la clase es obligatoria desde la 1.0."""
    return [c for c in comprobantes
            if any(not _clase_de(cuenta) for cuenta in cuentas_del_asiento(c, config, es_venta))]


def comprobantes_sin_centro(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[Comprobante]:
    """Las filas a las que les falta un centro de costo que SÍ hace falta.

    El centro es obligatorio solo donde de verdad se escribe: en la columna M de las cuentas de
    `cuentas_con_centro` (el contador, 06-sep-2026 y 09-sep-2026). Una cuenta fuera de la lista
    NO bloquea nunca, ni siquiera con la X de su línea elegida como referencia: una referencia que se
    puede dejar en blanco no puede impedir exportar un mes.

    `es_venta` va opcional a propósito, calcando a `comprobantes_sin_cuenta`: esto es una librería que se
    instala fuera, y un positional obligatorio sería romper su API pública por una regla interna
    de CONCAR. Ojo al llamarla: sin el flag, un libro de ventas resolvería la cuenta como gasto.
    """
    if not config.get("usa_centros_costo", True):
        return []

    def falta(c: Comprobante) -> bool:
        # Cada parte de la base con su cuenta y su centro (`partes_de`): basta con que a una le falte.
        return any(not (centro or "").strip() and lleva_centro(cuenta, config)
                   for cuenta, centro, _ in partes_de(c, config, es_venta))

    return [c for c in comprobantes if falta(c)]


def repartos_que_no_cuadran(comprobantes: list[Comprobante], config: dict, es_venta: bool = False) -> list[Comprobante]:
    return [c for c in comprobantes if reparto_no_cuadra(c, config, es_venta)]


def faltantes_para(comprobantes: list[Comprobante], config: dict, es_venta: bool = False,
                   exige: frozenset[str] | set[str] = frozenset()) -> dict[str, list]:
    """Lo que les falta a estos comprobantes para un destino que EXIGE eso — solo las claves exigidas.

    No lanza: describe. Es la misma comprobación que `exigir_requisitos` hace cumplir, y la que
    `diagnosticar` cuenta por serie-número; una sola lista de reglas para las tres.

    **Lo que no mueve dinero no se le pide a nadie** (`sin_efecto_contable`): un comprobante dado de baja por SUNAT
    llega con todos sus importes en cero y no hay cuenta, centro ni reparto que ponerle. Se filtra aquí, en el único
    sitio donde se decide qué le falta a una imputación, y no en cada regla por separado. La sigla y el código de
    moneda **sí se le siguen pidiendo**: los escribe también un driver de registro, que no arma ningún asiento.
    """
    de_la_imputacion = con_efecto_contable(comprobantes, config)
    salida: dict[str, list] = {}
    if "tipo_cp" in exige:
        salida["sin_sigla"] = tipos_sin_sigla(comprobantes, config)
    if "moneda" in exige:
        salida["sin_codigo_de_moneda"] = monedas_sin_codigo(comprobantes, config)
    if "cuenta_unica" in exige:
        salida["reparto_no_admitido"] = con_reparto(de_la_imputacion, config)
    if "cuenta_contable" in exige:
        salida["sin_cuenta"] = comprobantes_sin_cuenta(de_la_imputacion, config, es_venta)
        salida["sin_clase"] = comprobantes_sin_clase(de_la_imputacion, config, es_venta)
        salida["reparto_que_no_cuadra"] = repartos_que_no_cuadran(de_la_imputacion, config, es_venta)
    if "centro_costo" in exige:
        salida["sin_centro"] = comprobantes_sin_centro(de_la_imputacion, config, es_venta)
    if "denominacion" in exige:
        salida["sin_denominacion"] = cuentas_sin_denominacion(de_la_imputacion, config, es_venta)
    if "detraccion" in exige:
        salida["sin_codigo_detraccion"] = comprobantes_sin_codigo_detraccion(de_la_imputacion, config)
    # Esta NO depende de lo que el destino exija: no es un requisito de un formato, es que dos hechos del documento se
    # contradicen. Una factura marcada como anulada deja de provisionar su detracción en el núcleo, para cualquier
    # driver, así que la contradicción tiene que pararse para cualquier driver.
    # Solo si hay alguna: las demás claves aparecen vacías cuando su requisito se exige, y así significan «esto se
    # comprobó». Esta no cuelga de ningún requisito, así que aparecería siempre y no diría nada.
    anuladas = comprobantes_anulados_con_deposito(de_la_imputacion, config)
    if anuladas:
        salida["anulada_con_deposito"] = anuladas
    return salida


def exigir_requisitos(comprobantes: list[Comprobante], config: dict, es_venta: bool = False,
                      exige: frozenset[str] | set[str] = frozenset()) -> None:
    """Hace cumplir `faltantes_para`: la primera falta, en el orden de `FALTAS` (tipo → moneda → reparto no admitido →
    cuenta → reparto que no cuadra → centro), detiene la exportación con su excepción. Un tipo sin sigla no se
    inventa."""
    falta = faltantes_para(comprobantes, config, es_venta, exige)
    for regla in FALTAS:
        if regla.excepcion is not None and falta.get(regla.clave):
            raise regla.excepcion(falta[regla.clave])
