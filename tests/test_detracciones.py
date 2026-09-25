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

from contaperu import api
from contaperu.pipeline import preparacion as prep
from contaperu.drivers import concar as driver_concar
from contaperu import asiento, detracciones, validar
from contaperu.asiento.configuracion import NUMERO_DETRACCION_PENDIENTE
from contaperu.drivers import contasis as driver_contasis
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
    assert buena.detraccion == {"codigo": "027", "porcentaje": 4, "monto": "5", "tasa_tabla": "4"}
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
