"""La detracción contrastada con la tabla del contribuyente, y su monto calculado una sola vez.

El caso que motiva la tabla: una IA lee «retención 3 %» en una factura y devuelve una detracción con
código «000». Si ese código llega al asiento, se provisiona una detracción que no existe.

El caso que motiva el monto (10-sep-2026): la pantalla enseñaba una cifra —calculada en el navegador o
leída del PDF— y a CONCAR iba otra. Ahora las dos salen de `detracciones.monto_detraccion()`.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from contaperu import api
from contaperu.pipeline import preparacion as prep
from contaperu.drivers import concar as driver_concar
from contaperu.drivers import contrato
from contaperu import asiento, detracciones, validar
from contaperu.asiento.configuracion import NUMERO_DETRACCION_PENDIENTE
from contaperu.drivers import contasis as driver_contasis
from contaperu.drivers import sire as driver_sire
from contaperu.modelo import Comprobante, Libro

# `con_imputaciones` mete las imputaciones de prueba en la configuración: desde la 3.0 la cuenta de un comprobante
# es suya y llega por ahí, así que sin esto el asiento se plantaría con «sin cuenta contable».
from util import comprobante as _comprobante_de_prueba, con_imputaciones     # noqa: E402

CONTAB = con_imputaciones(prep.config_aplicada(None, "concar"))
CODIGOS = detracciones.codigos_de(CONTAB)
# Una tabla explícita para todo lo que depende de las tasas: no se apoya en lo que traigan los defaults.
TABLA = dict(CONTAB, detraccion_codigos={"027": "02701", "037": "03701"}, detraccion_tasas={"027": 4, "037": 12})


def comprobante(det, **k) -> Comprobante:
    base = dict(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-08-11",
                contraparte_doc="20601111111", base_gravada="100", igv="18", total="118", detraccion=det,
                cuenta_contable="659999")
    base.update(k)
    return _comprobante_de_prueba(**base)


def test_el_codigo_de_la_tabla_se_conserva():
    assert detracciones.normalizar_una({"codigo": "027", "porcentaje": 4}, CODIGOS) == \
        {"codigo": "027", "porcentaje": 4}


def test_el_codigo_corto_se_completa_a_tres_digitos():
    assert detracciones.normalizar_una({"codigo": "27"}, CODIGOS) == {"codigo": "027"}


def test_el_codigo_que_no_esta_en_la_tabla_queda_en_blanco():
    """«000» es lo que devuelve una IA que confundió la retención del IGV con una detracción."""
    for malo in ({"codigo": "000"}, {"codigo": ""}, {"codigo": "999"}, {"porcentaje": 3}, None, "027"):
        assert detracciones.normalizar_una(malo, CODIGOS) is None


def test_normalizar_devuelve_solo_lo_que_cambio():
    """Cambian la que se limpia y la que recibe el monto del motor; la tasa de la buena no se toca."""
    buena = comprobante({"codigo": "027", "porcentaje": 4})
    mala = comprobante({"codigo": "000", "porcentaje": 3})
    sin = comprobante(None)

    assert detracciones.normalizar([buena, mala, sin], TABLA) == [buena, mala]
    assert mala.detraccion is None            # se limpió
    # 118 × 4 % = 4.72 → 5 soles enteros; y la tasa de la tabla, anotada para compararla.
    assert buena.detraccion == {"codigo": "027", "porcentaje": 4, "monto": "5", "_tasa_tabla": "4"}
    assert sin.detraccion is None
    # Idempotente: repetirla no cambia nada, así la revalidación no reescribe filas de más.
    assert detracciones.normalizar([buena, mala, sin], TABLA) == []


def test_sin_detracciones_no_hace_nada():
    assert detracciones.normalizar([comprobante(None)], CONTAB) == []


def test_la_tabla_vive_en_el_motor_con_su_fuente():
    """La tabla de detracciones es del motor (John, 15-sep-2026): sin configuración ya se reconocen sus códigos, cada uno
    con su nombre y su tasa, y la tabla dice de dónde sale. El código interno de CONCAR no decide qué se reconoce."""
    del_motor = detracciones.tabla_del_motor()
    assert del_motor["fuente"].strip()
    assert detracciones.codigos_de({}) == set(del_motor["codigos"]) >= {"027", "030", "037"}
    assert detracciones.tabla_de_detracciones()["030"] == {"nombre": "Contratos de construcción", "tasa": Decimal("4")}
    assert detracciones.normalizar_una({"codigo": "27"}, detracciones.codigos_de({})) == {"codigo": "027"}
    assert detracciones.codigos_de({"detraccion_codigos": {"999": "99901"}}) == detracciones.codigos_de({})


def test_los_codigos_de_detraccion_de_concar_son_de_la_tabla_del_motor():
    """El mapa de la Tabla General 28 de CONCAR traduce códigos de SUNAT, así que sus claves tienen que ser códigos
    que el motor reconozca: uno que no esté en la tabla no llegaría nunca a la columna AI, porque `normalizar_una`
    deja en blanco la detracción cuyo código no reconoce, y el mapeo mentiría.

    **Al revés no**: la tabla tiene, y tendrá, códigos que este mapa de muestra no trae; el que aparezca se añade con
    el código interno que use el contribuyente. Y cada interno empieza por su código de SUNAT, que es cómo se numera
    esa tabla (el de SUNAT más 2 propios): de eso depende el respaldo del lector (`proyeccion._codigo_sunat_de`).

    Si las dos listas se separan a propósito, se cambian las dos. El precedente es `test_cuentas_del_sistema.py`,
    que compara las cuentas de CONCAR con las de fábrica por el mismo motivo."""
    mapa = contrato.seccion_por_defecto(driver_concar)["detraccion_codigos"]
    del_motor = detracciones.codigos_de({})
    sobran = sorted(set(mapa) - del_motor)
    assert not sobran, f"CONCAR mapea códigos que el motor no reconoce: {sobran}. Añádelos a la tabla del motor con " \
                       "su fuente (datos/sunat/detracciones.json), o quítalos del mapa."
    mal = sorted(f"{sunat}->{interno}" for sunat, interno in mapa.items() if not interno.startswith(sunat))
    assert not mal, f"un código de la T.G. 28 no empieza por el de SUNAT: {mal}"


def test_el_erp_sobreescribe_la_tabla_del_motor():
    """Quien integra el motor cambia una tasa o un nombre, o suma un código (`null`: sin tasa, la trae el comprobante)."""
    propia = {"detraccion_tasas": {"037": 10, "031": None}, "detraccion_nombres": {"030": "Obras", "999": "No suma"}}
    assert detracciones.tasa_de_tabla("037", propia) == 10              # la del ERP manda
    assert detracciones.tasa_de_tabla("027", propia) == 4               # la que no toca sigue siendo la del motor
    assert "031" in detracciones.codigos_de(propia) and detracciones.tasa_de_tabla("031", propia) == 0
    assert detracciones.normalizar_una({"codigo": "31"}, detracciones.codigos_de(propia)) == {"codigo": "031"}
    tabla = detracciones.tabla_de_detracciones(propia)
    assert tabla["030"]["nombre"] == "Obras" and "999" not in tabla     # un nombre no suma un código


def test_la_configuracion_de_la_1_0_da_lo_mismo_que_la_tabla_del_motor():
    """Quien guardó los 14 códigos que traía la configuración hasta la 1.0 sobreescribe con los mismos valores; la de
    fábrica ya no los trae, porque viven en el motor."""
    de_la_1_0 = {"detraccion_tasas": {"008": 4, "009": 10, "010": 15, "012": 12, "019": 10, "020": 12, "021": 10,
                                      "022": 12, "024": 10, "025": 10, "026": 10, "027": 4, "030": 4, "037": 12}}
    assert detracciones.tabla_de_detracciones(de_la_1_0) == detracciones.tabla_de_detracciones({})
    assert api.configuracion_por_defecto()["detraccion_tasas"] == {}
    assert api.configuracion_por_defecto()["detraccion_nombres"] == {}


def test_el_asiento_y_el_diagnostico_dejan_en_blanco_la_misma_detraccion():
    """El mismo documento, la misma respuesta (1.1): la detracción con un código que no está en la tabla no llega a las
    líneas de `generar_asiento`, y `diagnosticar` tampoco la espera."""
    mala = dict(comprobante({"codigo": "000", "porcentaje": 3}).a_dict(), id_externo="f1")
    doc = {"libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608",
                     "tipo": "compra"}, "comprobantes": [mala]}
    configuracion = {"usa_centros_costo": False}
    imputacion = {"f1": {"cuenta_contable": "659999"}}      # la cuenta es del comprobante desde la 3.0
    asiento = api.generar_asiento(doc, driver="csv", configuracion=configuracion, imputacion=imputacion,
                                  incluir_observados=True)
    assert all(linea.get("rol") != "detraccion" for linea in asiento["asiento"])
    assert set(asiento["_asiento"]["sub_diarios"]) == {"11"}
    assert api.diagnosticar(doc, driver="csv", configuracion=configuracion,
                            imputacion=imputacion)["detracciones_pendientes"] == []


def test_una_detraccion_limpiada_no_llega_al_asiento():
    """La consecuencia real de la regla: sin código válido no hay líneas de detracción."""
    c = comprobante({"codigo": "000", "porcentaje": 3})
    detracciones.normalizar([c], CONTAB)
    filas = driver_concar.filas_de_comprobante(c, CONTAB, (date(2026, 8, 1), date(2026, 8, 31)), "080001")
    assert len(filas) == 3 and all(f["R"] != "DR" for f in filas)


# ── El monto: una sola cifra, la que va a CONCAR ─────────────────────────────

def test_el_monto_va_en_soles_enteros():
    """Del Excel real validado en CONCAR: 4 956 × 4 % = 198.24 → 198. Y el caso que destapó el problema:
    330.40 al 12 % son 40, no los 33.65 que enseñaba la pantalla."""
    assert detracciones.monto_detraccion(comprobante({"codigo": "027", "porcentaje": 4}, total="4956"), TABLA) == \
        (Decimal("198"), Decimal("198"))
    assert detracciones.monto_detraccion(comprobante({"codigo": "037", "porcentaje": 12}, total="330.40"), TABLA)[0] == 40


def test_en_dolares_se_deposita_en_soles():
    c = comprobante({"codigo": "037", "porcentaje": 12}, total="1000", moneda="USD", tipo_cambio="3.5")
    assert detracciones.monto_detraccion(c, TABLA) == (Decimal("420"), Decimal("120.00"))
    sin_tc = comprobante({"codigo": "037", "porcentaje": 12}, total="1000", moneda="USD")
    assert detracciones.monto_detraccion(sin_tc, TABLA) == (0, 0)


def test_sin_tasa_en_el_comprobante_usa_la_de_la_tabla():
    c = comprobante({"codigo": "037"}, total="330.40")
    assert detracciones.tasa_detraccion(c, TABLA) == 12 and detracciones.monto_detraccion(c, TABLA)[0] == 40


def test_el_asiento_usa_el_mismo_monto():
    """Una sola implementación: lo que ve la persona es lo que sale en las líneas de la detracción."""
    c = comprobante({"codigo": "037", "porcentaje": 12}, total="330.40", base_gravada="280", igv="50.40")
    filas = driver_concar.filas_de_comprobante(c, TABLA, (date(2026, 8, 1), date(2026, 8, 31)), "080001")
    detraccion = [f for f in filas if f["R"] == "DR"]
    assert detraccion and all(f["O"] == 40 for f in detraccion)


# ── El aviso de tasa ─────────────────────────────────────────────────────────

def _codigos(c: Comprobante) -> set[str]:
    validar.validar(c, Libro(ruc="20601111112", razon_social="EMPRESA", periodo="202608", tipo="compra"))
    return {o.codigo for o in c.observaciones}


def test_avisa_si_la_tasa_no_es_la_de_la_tabla():
    """El caso que teme John: la IA lee un 10 % y el código es del 12 %."""
    c = comprobante({"codigo": "037", "porcentaje": 10}, total="330.40")
    detracciones.normalizar([c], TABLA)
    assert "DETRACCION_TASA_DISTINTA" in _codigos(c)


def test_no_avisa_si_coincide_o_si_la_tasa_sale_de_la_tabla():
    igual = comprobante({"codigo": "037", "porcentaje": 12}, total="330.40")
    de_tabla = comprobante({"codigo": "037"}, total="330.40")
    detracciones.normalizar([igual, de_tabla], TABLA)
    assert "DETRACCION_TASA_DISTINTA" not in _codigos(igual)
    assert "DETRACCION_TASA_DISTINTA" not in _codigos(de_tabla)


# --- la constancia del depósito: una sola regla para los dos caminos (2.7) ---------------------------------------

def _compra_con_detraccion(**extra) -> Comprobante:
    """Una factura afecta a detracción, con lo mínimo para que el asiento salga."""
    return _comprobante_de_prueba(tipo_cp="01", serie="F001", numero="123", fecha_emision=date(2026, 1, 15),
                                  contraparte_doc="20512333797", contraparte_nombre="PROVEEDOR SAC", moneda="PEN",
                                  base_gravada=Decimal("1000.00"), igv=Decimal("180.00"), total=Decimal("1180.00"),
                                  cuenta_contable="659999", detraccion={"codigo": "027", **extra})


def test_sin_constancia_pegada_el_numero_sale_con_el_comodin():
    """Es el caso normal al exportar el mes: el depósito se hace días después, «casi pasando el otro mes»."""
    constancia = asiento.constancia_de(_compra_con_detraccion())
    assert constancia == {"nro_constancia": NUMERO_DETRACCION_PENDIENTE, "fecha_constancia": ""}


def test_con_constancia_pegada_sale_la_suya():
    constancia = asiento.constancia_de(
        _compra_con_detraccion(nro_constancia="12345678901234567", fecha_constancia="2026-02-10"))
    assert constancia == {"nro_constancia": "12345678901234567", "fecha_constancia": "2026-02-10"}


def test_sin_comodin_el_pendiente_no_se_inventa_ni_se_repite():
    """`comodin=False` es lo que pide el vocabulario del estándar (3.9): el `999999999` llena una columna obligatoria
    de un sistema peruano, y para un ERP de fuera es un vóucher que no existe.

    Se descartan los dos casos: el que el motor inventaría y el que ya viene en el documento —un comodín guardado de
    una exportación anterior tampoco es un depósito—. La constancia de verdad no se toca."""
    assert asiento.constancia_de(_compra_con_detraccion(), comodin=False) == {
        "nro_constancia": "", "fecha_constancia": ""}
    guardado = _compra_con_detraccion(nro_constancia=NUMERO_DETRACCION_PENDIENTE)
    assert asiento.constancia_de(guardado, comodin=False)["nro_constancia"] == ""
    real = _compra_con_detraccion(nro_constancia="12345678901234567", fecha_constancia="2026-02-10")
    assert asiento.constancia_de(real, comodin=False) == {
        "nro_constancia": "12345678901234567", "fecha_constancia": "2026-02-10"}


def test_sin_detraccion_no_hay_constancia_ni_comodin():
    """El comodín dice «está pendiente», y una compra sin detracción no tiene nada pendiente."""
    c = _compra_con_detraccion()
    c.detraccion = None
    assert asiento.constancia_de(c) == {"nro_constancia": "", "fecha_constancia": ""}


def test_el_driver_de_asiento_y_el_de_registro_dicen_lo_MISMO():
    """Es para lo que se extrajo la regla (2.7). CONCAR la recibe dentro de la línea de detracción que arma el
    núcleo; CONTASIS nunca ve esa línea —su sistema arma el asiento— y hasta la 2.7 la reescribía por su cuenta,
    comodín incluido. Dos copias de una regla acaban diciendo cosas distintas; esto lo comprueba."""
    c = _compra_con_detraccion(nro_constancia="98765432109876543", fecha_constancia="2026-02-10")
    lineas = asiento.lineas_del_comprobante(c, CONTAB, (date(2026, 1, 1), date(2026, 1, 31)), "0001")
    de_la_linea = next(ln.detraccion for ln in lineas if ln.rol == "detraccion" and ln.detraccion)
    del_registro = driver_contasis.proyeccion._constancia(c, CONTAB)
    assert de_la_linea["nro_constancia"] == del_registro["U"] == "98765432109876543"
    assert de_la_linea["fecha_constancia"] == "2026-02-10" and del_registro["V"].date() == date(2026, 2, 10)


def test_el_comodin_del_numero_se_configura_y_llega_a_los_dos_caminos():
    """Cierra una deuda que el código llevaba anotada: el TIPO del documento de la detracción se configuraba
    (`detraccion_tipo_doc`) y el NÚMERO no, «una asimetría de cuando el comodín era un detalle de CONCAR».

    Va en lo GENERAL y no en la configuración del asiento, aunque su hermano el tipo sí sea del asiento, y el
    motivo se ve aquí: el tipo solo existe en la línea comodín `DR`, y el número sale ADEMÁS en las columnas de
    constancia de un registro, que no arma ningún asiento. Declararlo en la sección del asiento habría dejado a
    CONTASIS sin poder leerlo — lo cazó el espía del contrato al intentarlo."""
    propio = {**CONTAB, "detraccion_numero_pendiente": "123456789"}
    c = _compra_con_detraccion()

    # El camino del ASIENTO: el documento comodín de la línea `DR` y la constancia de su bloque.
    lineas = asiento.lineas_del_comprobante(c, propio, (date(2026, 1, 1), date(2026, 1, 31)), "0001")
    de_la_linea = next(ln for ln in lineas if ln.rol == "detraccion")
    assert de_la_linea.documento["serie_numero"] == "123456789"
    assert de_la_linea.detraccion["nro_constancia"] == "123456789"

    # El camino del REGISTRO, que nunca ve esa línea.
    assert driver_contasis.proyeccion._constancia(c, propio)["U"] == "123456789"

    # Y sin configurar nada, el de partida.
    assert asiento.constancia_de(c)["nro_constancia"] == NUMERO_DETRACCION_PENDIENTE


# --- cuándo una detracción cuenta como PAGADA (3.2) ---------------------------------------------------------------

ESQUEMA_DEL_ESTANDAR = Path(__file__).resolve().parents[1] / "estandar" / "open-accounting.schema.json"


def test_los_dos_estados_son_exactamente_los_del_estandar():
    """Los nombres se declaran en el motor para que nadie escriba la cadena a mano, y el esquema los declara para
    quien no usa el motor. Dos listas que dicen lo mismo en dos sitios acaban diciendo cosas distintas."""
    esquema = json.loads(ESQUEMA_DEL_ESTANDAR.read_text(encoding="utf-8"))
    del_estandar = esquema["$defs"]["detraccion"]["properties"]["estado"]["enum"]
    assert del_estandar == [detracciones.PROVISIONADO, detracciones.PAGADO]


def test_pagada_exige_el_numero_Y_la_fecha():
    """El criterio de John (25-sep-2026). Con el número solo —lo que pasa cuando alguien pega el vóucher y se deja
    la fecha— la detracción SIGUE pendiente, y por eso el mes la sigue listando: es lo que hace que vuelva."""
    sin_nada = _compra_con_detraccion()
    solo_numero = _compra_con_detraccion(nro_constancia="00123456789")
    solo_fecha = _compra_con_detraccion(fecha_constancia="2026-02-10")
    completa = _compra_con_detraccion(nro_constancia="00123456789", fecha_constancia="2026-02-10")
    assert detracciones.estado_de(sin_nada) == detracciones.PROVISIONADO
    assert detracciones.estado_de(solo_numero) == detracciones.PROVISIONADO
    assert detracciones.estado_de(solo_fecha) == detracciones.PROVISIONADO
    assert detracciones.estado_de(completa) == detracciones.PAGADO
    assert detracciones.esta_pendiente(solo_numero) is True
    assert detracciones.esta_pendiente(completa) is False


def test_el_comodin_no_es_un_deposito_aunque_venga_con_fecha():
    """Se descartan los DOS: el comodín en vigor y el de partida. Un contribuyente que configuró el suyo puede
    tener guardado el de fábrica de una exportación anterior, y ese número tampoco es un vóucher."""
    con_el_de_fabrica = _compra_con_detraccion(nro_constancia=NUMERO_DETRACCION_PENDIENTE,
                                               fecha_constancia="2026-02-10")
    assert detracciones.estado_de(con_el_de_fabrica) == detracciones.PROVISIONADO
    propio = {**CONTAB, "detraccion_numero_pendiente": "123456789"}
    con_el_suyo = _compra_con_detraccion(nro_constancia="123456789", fecha_constancia="2026-02-10")
    assert detracciones.estado_de(con_el_suyo, propio) == detracciones.PROVISIONADO
    assert detracciones.estado_de(con_el_de_fabrica, propio) == detracciones.PROVISIONADO
    assert detracciones.numero_pendiente(propio) == "123456789"
    assert detracciones.numero_pendiente() == NUMERO_DETRACCION_PENDIENTE


def test_el_estado_que_trae_el_documento_no_se_lee():
    """Es informativo (John, 25-sep-2026): lo escribe quien quiera para que se vea. Un `estado` PAGADO sin
    constancia no convierte en pagada una detracción que no lo está, y uno PROVISIONADO con el depósito
    documentado no la deja pendiente."""
    miente_pagada = _compra_con_detraccion(estado="PAGADO")
    miente_provisional = _compra_con_detraccion(estado="PROVISIONADO", nro_constancia="00123456789",
                                                fecha_constancia="2026-02-10")
    assert detracciones.estado_de(miente_pagada) == detracciones.PROVISIONADO
    assert detracciones.estado_de(miente_provisional) == detracciones.PAGADO


def test_sin_detraccion_no_hay_estado():
    c = _compra_con_detraccion()
    c.detraccion = None
    assert detracciones.estado_de(c) == ""
    assert detracciones.esta_pendiente(c) is False


def test_el_voucher_llega_al_documento_DR_de_CONCAR():
    """Lo que faltaba (3.2): el número real llegaba a STARSOFT y a CONTASIS y **no a CONCAR**, que es el destino en
    producción y donde el número del documento `DR` ES la constancia. El comodín solo ocupa su sitio."""
    def documento_dr(c, config=CONTAB) -> tuple[str, str]:
        lineas = asiento.lineas_del_comprobante(c, config, (date(2026, 1, 1), date(2026, 1, 31)), "0001")
        dr = next(ln for ln in lineas if ln.rol == "detraccion")
        return driver_concar.proyeccion.fila(dr, c, config)["S"], dr.documento["serie_numero"]

    # Sin vóucher, el comodín, como siempre: es el caso normal al cerrar el mes.
    assert documento_dr(_compra_con_detraccion()) == (NUMERO_DETRACCION_PENDIENTE, NUMERO_DETRACCION_PENDIENTE)
    pagada = _compra_con_detraccion(nro_constancia="00123456789", fecha_constancia="2026-02-10")
    assert documento_dr(pagada) == ("00123456789", "00123456789")
    # Con número y sin fecha el archivo TAMBIÉN lleva el número: el vóucher existe, lo que falta es anotar el día.
    assert documento_dr(_compra_con_detraccion(nro_constancia="00123456789"))[0] == "00123456789"


# ── La marca que SUNAT afirma en su propuesta, y el código que pone el contador (4.1) ─────────────────────────────

MARCADA = {detracciones.MARCA_SIRE: "D"}


def test_la_marca_del_sire_sobrevive_al_blanqueo():
    """Lo que la 4.1 arregla. `normalizar` blanquea la detracción sin código reconocible, y hasta la 4.0 se llevaba el
    bloque entero: la marca que el lector del SIRE escribe —la única prueba de que a ese comprobante le FALTA algo— se
    perdía, y el mes se exportaba sin su línea de detracción y en silencio.

    Si alguien quita la conservación de anotaciones en `normalizar`, este test cae."""
    marcada = comprobante(dict(MARCADA))
    assert detracciones.normalizar([marcada], TABLA) == []      # no hay nada que cambiarle: ya está así
    assert marcada.detraccion == MARCADA                        # y la marca sigue ahí

    # Y una detracción con código ilegible que ADEMÁS venía marcada conserva la marca y pierde el resto.
    mixta = comprobante({"codigo": "000", "porcentaje": 3, **MARCADA})
    assert detracciones.normalizar([mixta], TABLA) == [mixta]
    assert mixta.detraccion == MARCADA


def test_la_anotacion_de_la_tabla_no_sobrevive_al_blanqueo():
    """`_tasa_tabla` es la tasa de un código, así que sin código no hay nada que anotar: se va con él. Conservarla
    dejaría en el bloque una tasa que no corresponde a ninguna detracción."""
    c = comprobante({"codigo": "027", "porcentaje": 4})
    detracciones.normalizar([c], TABLA)
    assert c.detraccion["_tasa_tabla"] == "4"
    c.detraccion = {"codigo": "000", "_tasa_tabla": "4", **MARCADA}
    detracciones.normalizar([c], TABLA)
    assert c.detraccion == MARCADA


def test_el_codigo_que_pone_el_contador_completa_la_marca():
    """El circuito entero: SUNAT dice QUE hay detracción, el contador dice CUÁL por su imputación, y el motor saca la
    tasa de su tabla y el monto de `total × tasa`. Desde ahí es indistinguible de un comprobante leído de un XML."""
    c = comprobante(dict(MARCADA), id_externo="c-detra")
    config = dict(TABLA, imputaciones={"c-detra": {"detraccion_codigo": "037"}})
    assert detracciones.normalizar([c], config) == [c]
    # 118 × 12 % = 14.16 → 14 soles enteros, y la tasa de la tabla anotada al lado.
    assert c.detraccion == {"codigo": "037", "monto": "14", "_tasa_tabla": "12", **MARCADA}


def test_lo_que_trae_el_comprobante_manda_sobre_lo_que_dice_el_contador():
    """El archivo gana a la persona: si el XML trajo el código, la imputación no lo pisa. Solo rellena lo que falta."""
    c = comprobante({"codigo": "027", "porcentaje": 4}, id_externo="c-detra")
    config = dict(TABLA, imputaciones={"c-detra": {"detraccion_codigo": "037"}})
    detracciones.normalizar([c], config)
    assert c.detraccion["codigo"] == "027"


def test_un_codigo_del_contador_que_no_esta_en_la_tabla_no_cuela():
    """La imputación no es una puerta trasera a la tabla: un código que el contribuyente no reconoce se blanquea igual,
    y el comprobante sigue marcado y sigue faltándole el código."""
    c = comprobante(dict(MARCADA), id_externo="c-detra")
    config = dict(TABLA, imputaciones={"c-detra": {"detraccion_codigo": "999"}})
    detracciones.normalizar([c], config)
    assert c.detraccion == MARCADA


def _doc_marcado(imputacion_extra: dict | None = None) -> tuple[dict, dict, dict]:
    """Un mes de una compra que SUNAT marcó con detracción, como lo deja el lector del SIRE."""
    marcado = dict(comprobante(dict(MARCADA)).a_dict(), id_externo="f1", origen="sire")
    doc = {"libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608",
                     "tipo": "compra"}, "comprobantes": [marcado]}
    imputacion = {"f1": {"cuenta_contable": "659999", **(imputacion_extra or {})}}
    return doc, {"usa_centros_costo": False}, imputacion


def test_sin_el_codigo_la_exportacion_se_niega_y_dice_a_quien_pedirlo():
    """Lo que la 4.1 cambia de verdad. Hasta la 4.0 este mes se exportaba **sin la línea de detracción y en silencio**:
    sin código no hay tasa, sin tasa el monto es 0 y la línea no nace, así que el Excel salía con la cuenta por pagar
    al proveedor inflada y nadie se enteraba. Ahora se para, con su lista para que el portal la filtre."""
    doc, configuracion, imputacion = _doc_marcado()
    d = api.diagnosticar(doc, driver="concar", configuracion=configuracion, imputacion=imputacion)
    assert d["listo_para_exportar"] is False
    assert d["faltantes"]["sin_codigo_detraccion"] == ["F001-1"]
    assert {"motivo": "sin_codigo_detraccion", "pedir_a": "contador"}.items() <= \
        next(f for f in d["que_falta"] if f["motivo"] == "sin_codigo_detraccion").items()
    with pytest.raises(asiento.SinCodigoDetraccion, match="marcó con detracción"):
        api.exportar(doc, driver="concar", configuracion=configuracion, imputacion=imputacion)


def test_el_driver_del_sire_sigue_exportando_un_mes_marcado():
    """El registro tributario no lleva detracción, así que no tiene por qué pararse: lo que se declara a SUNAT no
    cambia porque falte un dato del asiento. Si esto se rompiera, un mes del SIRE no se podría ni declarar."""
    doc, configuracion, imputacion = _doc_marcado()
    assert "detraccion" not in contrato.exige(driver_sire)
    assert api.exportar(doc, driver="sire", configuracion=configuracion,
                        imputacion=imputacion)["archivo"].endswith(".TXT")


# ── La factura anulada por una nota de crédito (5.3) ──────────────────────────────────────────────────────────
#
# El descubrimiento de John (2-oct-2026), importando notas de crédito en un CONCAR real: una factura de compra con
# detracción da CINCO líneas y su nota de crédito da TRES, así que el par no cuadra y quedan colgados el recorte y la
# provisión del depósito. Lo que queda colgado dice algo falso: que se le deben al Banco de la Nación unos soles por
# una factura anulada, un depósito que nunca se hizo.

FACTURA_CON_DETRACCION = {"tipo_cp": "01", "serie": "E001", "numero": "209", "fecha_emision": "2026-09-11",
                          "contraparte_doc": "20602222226", "contraparte_nombre": "TRANSPORTES DE PRUEBA SAC",
                          "moneda": "PEN", "concepto": "SERVICIO DE TRANSPORTE", "base_gravada": "2900.00",
                          "igv": "522.00", "total": "3422.00",
                          "detraccion": {"codigo": "027", "porcentaje": "4"}}
SU_NOTA_DE_CREDITO = {"tipo_cp": "07", "serie": "E001", "numero": "13", "fecha_emision": "2026-09-30",
                      "contraparte_doc": "20602222226", "contraparte_nombre": "TRANSPORTES DE PRUEBA SAC",
                      "moneda": "PEN", "concepto": "ANULACION DE LA OPERACION", "base_gravada": "2900.00",
                      "igv": "522.00", "total": "3422.00", "tipo_nota": "01",
                      "ref_tipo_cp": "01", "ref_serie": "E001", "ref_numero": "209", "ref_fecha": "2026-09-11"}


def _par(anulada: bool, detraccion: dict | None = None) -> list[dict]:
    """El par factura + su nota de crédito, con la factura marcada o no."""
    factura = dict(FACTURA_CON_DETRACCION, id_externo="f1")
    if detraccion is not None:
        factura["detraccion"] = detraccion
    doc = {"open_accounting": "1.0",
           "libro": {"ruc": "20601234567", "razon_social": "", "periodo": "202609", "tipo": "compra"},
           "comprobantes": [factura, dict(SU_NOTA_DE_CREDITO, id_externo="f2")],
           "imputaciones": {"f1": {"cuenta_contable": "631101", "centro_costo": "001",
                                   "anulada_por_nota": anulada},
                            "f2": {"cuenta_contable": "631101", "centro_costo": "001"}}}
    return api.generar_asiento(doc, driver="concar", incluir_observados=True)["asiento"]


def _neto(asiento: list[dict]) -> dict[str, str]:
    """Lo que queda en cada cuenta: vacío si el par cuadra."""
    from collections import defaultdict
    neto: defaultdict = defaultdict(Decimal)
    for l in asiento:
        neto[l["cuenta"]] += Decimal(l["importe"]) * (1 if l["debe_haber"] == "D" else -1)
    return {cuenta: str(v) for cuenta, v in neto.items() if v}


def test_sin_marcar_la_factura_el_par_deja_colgada_la_detraccion():
    """El problema, con los importes de John: cinco líneas contra tres, y 137 soles colgados en el par 421201/421203.

    Se fija el comportamiento de HOY a propósito: no se arregla solo, hace falta que el contador lo diga. Si algún día
    el motor lo decidiera por su cuenta, este test cae y hay que decidirlo."""
    a = _par(anulada=False)
    assert [l["rol"] for l in a if l["documento"].get("serie_numero") == "E001-209"] == [
        "principal", "impuesto", "tercero", "recorte"]
    assert _neto(a) == {"421201": "137.00", "421203": "-137.00"}


def test_marcada_como_anulada_la_factura_no_provisiona_y_el_par_cuadra():
    """**La prueba del cambio.** La factura marcada da tres líneas, su nota revierte esas tres, y no queda nada
    colgado. El 137 que decía que se le debía al Banco de la Nación desaparece, porque ese depósito no se hizo."""
    a = _par(anulada=True)
    assert [l["rol"] for l in a if l["documento"].get("serie_numero") == "E001-209"] == [
        "principal", "impuesto", "tercero"]
    assert _neto(a) == {}, "el par tiene que cuadrar a cero"
    # Y la nota de crédito no se toca: sigue dando sus tres.
    assert len([l for l in a if l["documento"].get("serie_numero") == "E001-13"]) == 3


def test_el_comprobante_anulado_sigue_entero_en_el_registro():
    """La frontera que `sin_efecto_contable` ya tiene escrita: el asiento es una cosa y el registro es otra. La
    factura anulada **sigue saliendo en el que se declara a SUNAT**, con su detracción y todo, porque el correlativo
    de SUNAT necesita su fila y la marca es del asiento, no del registro."""
    doc = {"open_accounting": "1.0",
           "libro": {"ruc": "20601234567", "razon_social": "", "periodo": "202609", "tipo": "compra"},
           "comprobantes": [dict(FACTURA_CON_DETRACCION, id_externo="f1")],
           "imputaciones": {"f1": {"cuenta_contable": "631101", "anulada_por_nota": True}}}
    r = api.exportar(doc, driver="sire", fecha="2026-10-01", incluir_observados=True)
    assert "E001" in r["texto"] and r["resumen"]["comprobantes"] == 1


def test_anulada_con_su_deposito_ya_hecho_se_para_y_dice_cual():
    """La contradicción. Con una constancia de verdad el dinero SÍ salió al Banco de la Nación: suprimir esas dos
    líneas esconderría un pago real, y el asiento diría que nunca hubo obligación.

    Anular una factura cuya detracción ya se depositó es contabilidad distinta —hay que recuperar el depósito— y no
    una línea de menos. El motor no elige: se para y dice cuál es el comprobante."""
    from contaperu.asiento.faltas import AnuladaConDeposito

    depositada = {"codigo": "027", "porcentaje": "4", "nro_constancia": "00123456",
                  "fecha_constancia": "2026-09-20"}
    with pytest.raises(AnuladaConDeposito) as e:
        _par(anulada=True, detraccion=depositada)
    assert e.value.clave == "anulada_con_deposito" and len(e.value.comprobantes) == 1

    # Y el estado se DEDUCE de la constancia, no de lo que el bloque declare: un productor no consigue que el motor
    # se crea un depósito que no documentó.
    solo_dicho = {"codigo": "027", "porcentaje": "4", "estado": "PAGADO"}
    assert _neto(_par(anulada=True, detraccion=solo_dicho)) == {}


def test_el_diagnostico_lo_dice_y_a_quien_pedirselo():
    """Y bloquea para CUALQUIER driver, no solo para los que exigen la detracción: no es que al destino le falte un
    dato, es que dos hechos del documento se contradicen."""
    doc = {"open_accounting": "1.0",
           "libro": {"ruc": "20601234567", "razon_social": "", "periodo": "202609", "tipo": "compra"},
           "comprobantes": [dict(FACTURA_CON_DETRACCION, id_externo="f1",
                                 detraccion={"codigo": "027", "porcentaje": "4",
                                             "nro_constancia": "00123456", "fecha_constancia": "2026-09-20"})],
           "imputaciones": {"f1": {"cuenta_contable": "631101", "anulada_por_nota": True}}}
    for driver in ("concar", "asiento_contable", "csv"):
        r = api.diagnosticar(doc, driver=driver, configuracion={"usa_centros_costo": False})
        assert r["listo_para_exportar"] is False, driver
        assert r["faltantes"]["anulada_con_deposito"] == ["E001-209"], driver
        motivos = {m["motivo"]: m for m in r["que_falta"]}
        assert motivos["anulada_con_deposito"]["pedir_a"] == "contador", driver


def test_el_motor_avisa_de_la_factura_que_tiene_nota_de_credito():
    """**El primer cruce de dos comprobantes del motor.** Hacía falta porque el enlace es de una sola dirección: la
    nota dice a qué factura apunta y la factura no dice nada — medido sobre un RCE real, ninguna de sus 41 columnas
    distingue las que tienen nota de las que no.

    Avisa y no decide: que una factura tenga nota de crédito no significa que esté anulada —puede ser un descuento o
    una corrección—, pero sí que conviene mirarla. El aviso nombra la nota, para no tener que buscarla."""
    doc = {"open_accounting": "1.0",
           "libro": {"ruc": "20601234567", "razon_social": "", "periodo": "202609", "tipo": "compra"},
           "comprobantes": [dict(FACTURA_CON_DETRACCION, id_externo="f1"),
                            dict(SU_NOTA_DE_CREDITO, id_externo="f2")]}
    r = api.revisar(doc)
    de_la_factura = next(c for c in r["comprobantes"] if c["numero"] == "209")
    aviso = next(o for o in de_la_factura["observaciones"] if o["codigo"] == "FACTURA_CON_NOTA_DE_CREDITO")
    assert aviso["nivel"] == "aviso" and "E001-13" in aviso["texto"] and "anulada_por_nota" in aviso["texto"]
    # Y NO bloquea, que es lo que importa: queda `observada` —cualquier aviso lo hace— pero el mes se exporta igual,
    # sin pedir `incluir_observados`, y con sus cinco líneas mientras nadie la marque.
    assert de_la_factura["estado"] == "observada"
    exportado = api.exportar(dict(doc, imputaciones={"f1": {"cuenta_contable": "631101", "centro_costo": "001"},
                                                     "f2": {"cuenta_contable": "631101", "centro_costo": "001"}}),
                             driver="concar", fecha="2026-10-01")
    assert exportado["resumen"]["filas"] == 8, "cinco de la factura y tres de la nota"
    # La nota NO se avisa a sí misma: el aviso es de la factura, que es la que decide si da cinco líneas o tres.
    de_la_nota = next(c for c in r["comprobantes"] if c["numero"] == "13")
    assert not [o for o in de_la_nota["observaciones"] if o["codigo"] == "FACTURA_CON_NOTA_DE_CREDITO"]


def test_una_nota_de_credito_parcial_no_dispara_el_aviso():
    """Una nota que no anula el total es un DESCUENTO o una devolución parcial, no una anulación: la factura conserva
    sus cinco líneas y nadie tiene que mirar nada. Avisar aquí sería ruido en un mes de tres mil filas."""
    parcial = dict(SU_NOTA_DE_CREDITO, base_gravada="1000.00", igv="180.00", total="1180.00")
    doc = {"open_accounting": "1.0",
           "libro": {"ruc": "20601234567", "razon_social": "", "periodo": "202609", "tipo": "compra"},
           "comprobantes": [dict(FACTURA_CON_DETRACCION, id_externo="f1"), dict(parcial, id_externo="f2")]}
    r = api.revisar(doc)
    for c in r["comprobantes"]:
        assert not [o for o in c["observaciones"] if o["codigo"] == "FACTURA_CON_NOTA_DE_CREDITO"]


def test_una_nota_cuya_factura_no_esta_en_el_lote_no_avisa_de_nada():
    """El caso que ningún dato puede resolver: la nota llega el mes siguiente y su factura no está aquí. No hay de
    dónde deducirlo, y por eso el campo de la imputación existe — para que el contador lo marque a mano."""
    doc = {"open_accounting": "1.0",
           "libro": {"ruc": "20601234567", "razon_social": "", "periodo": "202610", "tipo": "compra"},
           "comprobantes": [dict(SU_NOTA_DE_CREDITO, id_externo="f2", fecha_emision="2026-10-05")]}
    r = api.revisar(doc)
    assert not [o for c in r["comprobantes"] for o in c["observaciones"]
                if o["codigo"] == "FACTURA_CON_NOTA_DE_CREDITO"]


def test_con_el_codigo_del_contador_la_detraccion_llega_al_asiento():
    """Y el otro lado: puesto el código, el mes exporta y la detracción nace completa —sus dos líneas y su monto—,
    exactamente como si el comprobante hubiera entrado por su XML."""
    doc, configuracion, imputacion = _doc_marcado({"detraccion_codigo": "037"})
    assert api.diagnosticar(doc, driver="concar", configuracion=configuracion,
                            imputacion=imputacion)["faltantes"]["sin_codigo_detraccion"] == []
    asi = api.generar_asiento(doc, driver="csv", configuracion=configuracion, imputacion=imputacion)
    roles = [linea.get("rol") for linea in asi["asiento"]]
    assert roles.count("detraccion") == 1 and roles.count("recorte") == 1
    # 118 × 12 % = 14.16 → 14 soles enteros, y la línea lleva el código de SUNAT, no el interno de ningún ERP.
    detra = next(linea for linea in asi["asiento"] if linea.get("rol") == "detraccion")
    assert detra["importe"] == "14.00" and detra["detraccion"]["codigo"] == "037"
