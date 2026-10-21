"""Las líneas de diario de un movimiento de tesorería (12.7).

El motor sabe armarlas y todavía nadie se las pide: es el grano más fino de «el motor va primero». Lo que estos
casos fijan es que **no se inventa ninguna regla contable** —la del catálogo del estándar más la imputación más la
104 del maestro bastan para las cinco formas— y que cada asiento **cuadra por sí solo**, sin tolerancia.

La regla, publicada con su fuente en `estandar/catalogos.json` (`efectos_de_tesoreria`, NIC 7): una entrada lleva
el efectivo al DEBE, una salida al HABER, y una transferencia es el único efecto cuyas dos patas son cuentas
declaradas.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from contaperu import asiento, tesoreria
from contaperu.configuracion import CONFIG_POR_DEFECTO
from contaperu.contable import partida_doble
from contaperu.modelo import Libro

LIBRO = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202610", tipo="tesoreria")
LIMITES = asiento.limites_del_periodo(LIBRO)

CUENTAS = tesoreria.por_id([
    {"id": "bbva-soles", "banco": "BBVA", "moneda": "PEN", "cuenta_contable": "104101"},
    {"id": "bcp-soles", "banco": "BCP", "moneda": "PEN", "cuenta_contable": "104102"},
])


def mov(**campos) -> tesoreria.Movimiento:
    base = {"cuenta": "bbva-soles", "fecha": "2026-10-15", "importe": "2000.00", "sentido": "cargo",
            "moneda": "PEN", "descripcion": "TRANSFERENCIA A TERCEROS", "medio_pago": "003",
            "referencia": "000123", "id_externo": "mov-1"}
    return tesoreria.Movimiento(**dict(base, **campos))


def imputacion(**campos) -> tesoreria.ImputacionDeMovimiento:
    return tesoreria.ImputacionDeMovimiento(**campos)


def lineas(m, imp, config=None) -> list:
    return asiento.lineas_del_movimiento(m, imp, CUENTAS, config or CONFIG_POR_DEFECTO, LIMITES)


def plano(ln) -> tuple:
    return (ln.cuenta, ln.debe_haber, ln.importe)


# --- las cinco formas ---------------------------------------------------------------------------------------------

def test_un_pago_a_proveedor_son_dos_lineas_y_el_efectivo_va_al_haber():
    """Una salida: la contrapartida al Debe y el efectivo al Haber, que es lo que dice el catálogo."""
    ls = lineas(mov(contraparte_doc="20602222226"),
                imputacion(cuenta_contable="421201", contraparte_doc="20602222226"))
    assert [plano(ln) for ln in ls] == [("421201", "D", "2000.00"), ("104101", "H", "2000.00")]
    assert partida_doble.cuadra(ls).cuadra
    assert ls[0].contraparte_doc == "20602222226", "el tercero lleva su documento"
    assert ls[1].medio_pago == "003" and not ls[1].contraparte_doc, "el medio de pago va en la línea del dinero"
    assert ls[0].clase == "pasivo" and ls[1].clase == "activo"


def test_un_cobro_lleva_el_efectivo_al_debe_y_no_tiene_linea_de_IGV():
    """El débito fiscal se reconoció en la venta: cobrarla no vuelve a tocar el IGV."""
    ls = lineas(mov(sentido="abono", importe="1180.00", contraparte_doc="20607777773"),
                imputacion(cuenta_contable="121201", contraparte_doc="20607777773"))
    assert [plano(ln) for ln in ls] == [("104101", "D", "1180.00"), ("121201", "H", "1180.00")]
    assert partida_doble.cuadra(ls).cuadra
    assert not any(ln.impuesto for ln in ls)


def test_una_comision_bancaria_es_un_gasto_contra_el_efectivo():
    """Un cargo del banco es su propio movimiento (enmienda 0028): no necesita campo, necesita su imputación."""
    ls = lineas(mov(importe="15.00", descripcion="COMISION MANTENIMIENTO", id_externo="mov-2"),
                imputacion(cuenta_contable="639101", centro_costo="CC-10"))
    assert [plano(ln) for ln in ls] == [("639101", "D", "15.00"), ("104101", "H", "15.00")]
    assert ls[0].clase == "gasto" and partida_doble.cuadra(ls).cuadra


def test_un_reparto_de_tres_partes_da_tres_lineas_contra_una_del_efectivo():
    """Un cargo que paga tres facturas. Cuadra por construcción: `exigir_que_sume` ya bloqueó al leer."""
    partes = [tesoreria.Parte(importe="800.00", cuenta_contable="421201", contraparte_doc="20602222226"),
              tesoreria.Parte(importe="700.00", cuenta_contable="421201", contraparte_doc="20607777773"),
              tesoreria.Parte(importe="500.00", cuenta_contable="639101", centro_costo="CC-10")]
    ls = lineas(mov(importe="2000.00"), imputacion(reparto=partes))
    assert [plano(ln) for ln in ls] == [("421201", "D", "800.00"), ("421201", "D", "700.00"),
                                        ("639101", "D", "500.00"), ("104101", "H", "2000.00")]
    assert partida_doble.cuadra(ls).cuadra
    assert [ln.contraparte_doc for ln in ls[:3]] == ["20602222226", "20607777773", ""]


def test_un_traspaso_entre_cuentas_propias_tiene_sus_dos_patas_declaradas():
    """El único efecto que no necesita imputación para su contrapartida: las dos cuentas las declaró el
    contribuyente. Y por eso no es un flujo de efectivo (NIC 7 §9)."""
    ls = lineas(mov(importe="5000.00"), imputacion(cuenta_propia="bcp-soles"))
    assert [plano(ln) for ln in ls] == [("104102", "D", "5000.00"), ("104101", "H", "5000.00")]
    assert partida_doble.cuadra(ls).cuadra
    assert not any(ln.contraparte_doc for ln in ls), "un traspaso es con uno mismo"
    assert ls[1].medio_pago == "003" and not ls[0].medio_pago, "el medio de pago solo en la pata que vimos"


def test_un_traspaso_que_entra_invierte_los_dos_lados():
    ls = lineas(mov(sentido="abono", importe="5000.00"), imputacion(cuenta_propia="bcp-soles"))
    assert [plano(ln) for ln in ls] == [("104101", "D", "5000.00"), ("104102", "H", "5000.00")]


# --- el ITF, que es su propio asiento --------------------------------------------------------------------------

def test_el_itf_sale_en_su_propio_asiento_y_no_se_resta_del_pago():
    """Un pago de 2 000 con 0,50 de ITF **son dos asientos** (enmienda 0028). Restarlo del pago descuadraría el
    asiento y escondería un cargo que el banco sí hizo."""
    ls = lineas(mov(itf="0.50", contraparte_doc="20602222226"), imputacion(cuenta_contable="421201"))
    assert [plano(ln) for ln in ls] == [("421201", "D", "2000.00"), ("104101", "H", "2000.00"),
                                        ("641201", "D", "0.50"), ("104101", "H", "0.50")]
    assert partida_doble.cuadra(ls).cuadra, "los dos asientos juntos también cuadran"
    assert partida_doble.cuadra(ls[:2]).cuadra and partida_doble.cuadra(ls[2:]).cuadra, "y cada uno por su lado"
    assert ls[2].clase == "gasto"


def test_el_importe_del_itf_lo_dice_el_banco_y_nunca_se_calcula():
    """La fuente del asiento es el documento fehaciente —la constancia o el extracto—, no una tasa: por eso no
    hace falta su norma para asentarlo, y por eso dos importes distintos salen distintos sin ninguna regla."""
    for cuanto in ("0.50", "13.75"):
        ls = lineas(mov(itf=cuanto), imputacion(cuenta_contable="421201"))
        assert ls[2].importe == cuanto and ls[3].importe == cuanto


def test_sin_itf_no_hay_segundo_asiento():
    ls = lineas(mov(), imputacion(cuenta_contable="421201"))
    assert len(ls) == 2


def test_la_cuenta_del_itf_se_configura():
    """Es la `6412` del PCGE a seis dígitos, y cada empresa abre la suya."""
    config = dict(CONFIG_POR_DEFECTO, cuentas=dict(CONFIG_POR_DEFECTO["cuentas"], itf="641299"))
    ls = lineas(mov(itf="0.50"), imputacion(cuenta_contable="421201"), config)
    assert ls[2].cuenta == "641299"


# --- lo común a todas las líneas -----------------------------------------------------------------------------------

def test_ninguna_linea_sale_sin_glosa_y_la_decide_el_contador():
    """La cadena de respaldo de `glosa_de_movimiento`: la de la parte manda sobre la de la imputación, y ésa sobre
    el texto del banco."""
    partes = [tesoreria.Parte(importe="2000.00", cuenta_contable="421201", glosa="pago factura F001-1")]
    ls = lineas(mov(), imputacion(reparto=partes, glosa="PAGO A PROVEEDORES"))
    assert ls[0].glosa == "PAGO FACTURA F001-1"
    assert ls[1].glosa == "PAGO A PROVEEDORES"
    # Y sin que nadie decida nada, el texto del banco antes que una celda vacía.
    assert all(ln.glosa for ln in lineas(mov(), imputacion(cuenta_contable="421201")))


def test_el_documento_de_la_linea_nombra_el_papel_y_no_lleva_tipo_cp():
    """Un vóucher del banco no es un comprobante de SUNAT — el mismo precedente que la línea de la detracción."""
    ls = lineas(mov(constancia="V-00987"), imputacion(cuenta_contable="421201"))
    assert ls[0].documento == {"serie_numero": "V-00987", "id_externo": "mov-1", "fecha_emision": "2026-10-15"}
    assert "tipo_cp" not in ls[0].documento
    # Sin constancia manda el número que dio el banco.
    assert lineas(mov(), imputacion(cuenta_contable="421201"))[0].documento["serie_numero"] == "000123"


def test_la_fecha_del_asiento_se_encaja_en_el_periodo_y_la_del_papel_se_conserva():
    """La misma regla que un comprobante extemporáneo: el asiento cae dentro de su mes, el documento conserva la
    suya."""
    ls = lineas(mov(fecha="2026-09-20"), imputacion(cuenta_contable="421201"))
    assert ls[0].fecha == "2026-10-01" and ls[0].documento["fecha_emision"] == "2026-09-20"
    ls = lineas(mov(fecha="2026-11-20"), imputacion(cuenta_contable="421201"))
    assert ls[0].fecha == "2026-10-31"


def test_el_centro_va_donde_la_cuenta_lo_lleva_con_la_MISMA_regla_que_un_comprobante():
    """`cuentas_con_centro` no cambia porque el dinero venga de un banco: un gasto lo lleva y la cuenta del
    proveedor no."""
    ls = lineas(mov(importe="15.00"), imputacion(cuenta_contable="639101", centro_costo="CC-10"))
    assert ls[0].centro_costo == "CC-10"
    ls = lineas(mov(), imputacion(cuenta_contable="421201", centro_costo="CC-10"))
    assert ls[0].centro_costo == "", "la cuenta del proveedor no lleva centro"


def test_sin_sub_diario_ni_correlativo_porque_el_vocabulario_es_neutral():
    """Aquí lo legacy es lo que todavía no existe: ni sub-diario ni correlativo tienen clave de configuración
    hasta que un archivo real los pida."""
    ls = lineas(mov(), imputacion(cuenta_contable="421201"))
    assert all(not ln.sub_diario and not ln.correlativo for ln in ls)


def test_la_moneda_sale_del_movimiento_o_de_su_cuenta():
    ls = lineas(mov(moneda=""), imputacion(cuenta_contable="421201"))
    assert all(ln.moneda == "PEN" for ln in ls)


def test_toda_linea_vuelve_a_entrar_por_de_dict():
    """La ida y la vuelta: lo que el motor escribe tiene que poder volver a leerse, con su clase casando con su
    cuenta."""
    from contaperu.asiento.lineas import LineaDiario

    for ln in lineas(mov(itf="0.50"), imputacion(cuenta_contable="421201")):
        assert LineaDiario.de_dict(ln.a_dict()).a_dict() == ln.a_dict()


# --- lo que para ---------------------------------------------------------------------------------------------------

def test_un_movimiento_sin_imputacion_no_se_puede_saldar():
    """«Sin imputación no hay cuenta», aplicado al dinero: la 104 sale del maestro, pero contra qué se salda lo
    decide el contador."""
    with pytest.raises(asiento.MovimientoSinImputar):
        lineas(mov(), None)
    with pytest.raises(asiento.MovimientoSinImputar):
        lineas(mov(), imputacion(glosa="PAGO"))


def test_una_cuenta_que_el_maestro_no_declara_para_y_dice_por_que():
    with pytest.raises(asiento.SinCuentaDeEfectivo, match="no está en el maestro"):
        lineas(mov(cuenta="interbank-soles"), imputacion(cuenta_contable="421201"))


def test_una_cuenta_declarada_sin_su_cuenta_contable_tambien():
    """El motor **no deriva la 104**: cada empresa abre las divisionarias que quiere."""
    cuentas = tesoreria.por_id([{"id": "bbva-soles", "banco": "BBVA", "moneda": "PEN"}])
    with pytest.raises(asiento.SinCuentaDeEfectivo, match="sin su cuenta contable"):
        asiento.lineas_del_movimiento(mov(), imputacion(cuenta_contable="421201"), cuentas,
                                      CONFIG_POR_DEFECTO, LIMITES)


def test_un_traspaso_a_una_cuenta_que_nadie_declaro_para():
    with pytest.raises(asiento.SinCuentaDeEfectivo):
        lineas(mov(), imputacion(cuenta_propia="scotia-soles"))


def test_una_cuenta_de_un_elemento_sin_clase_para():
    """El 8 y el 0 del PCGE no tienen clase contable: una imputación a ellas es casi seguro un error."""
    with pytest.raises(asiento.CuentaSinClase):
        lineas(mov(), imputacion(cuenta_contable="801101"))


def test_un_traspaso_declarado_por_sus_dos_patas_se_caza_antes_de_contarlo_dos_veces():
    """Desde un movimiento solo no se puede ver —por eso `Movimiento.efecto` nunca devuelve `transferencia`—, así
    que se mira con todos delante."""
    ida = mov(cuenta="bbva-soles", importe="5000.00", sentido="cargo", id_externo="mov-ida")
    vuelta = mov(cuenta="bcp-soles", importe="5000.00", sentido="abono", id_externo="mov-vuelta")
    imputaciones = {"mov-ida": imputacion(cuenta_propia="bcp-soles"),
                    "mov-vuelta": imputacion(cuenta_propia="bbva-soles")}
    assert asiento.traspasos_en_dos_patas([ida, vuelta], imputaciones)
    # Una sola pata es lo normal y no avisa de nada.
    assert asiento.traspasos_en_dos_patas([ida], {"mov-ida": imputaciones["mov-ida"]}) == []


def test_la_falta_de_un_traspaso_doble_dice_cuales():
    with pytest.raises(asiento.TraspasoEnDosPatas, match="dos veces"):
        raise asiento.TraspasoEnDosPatas(["bbva-soles ↔ bcp-soles por 5000.00"])


# --- y lo que estas faltas comparten con los avisos que ya existían ------------------------------------------------

def test_las_faltas_del_asiento_son_las_de_revisar_tesoreria_endurecidas():
    """Mirar no obliga a nada y asentar sí: `revisar_tesoreria` avisa de lo mismo sin parar, porque un informe
    puede reportar lo que falta y un asiento no puede escribirlo."""
    from contaperu import api

    doc = {"open_accounting": "4.0",
           "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
                     "periodo": "202610", "tipo": "tesoreria"},
           "movimientos": [mov().a_dict()]}
    avisos = [a["codigo"] for a in api.revisar_tesoreria(doc, [c.a_dict() for c in CUENTAS.values()])["avisos"]]
    assert "MOVIMIENTO_SIN_IMPUTAR" in avisos
    # El mismo mes, asentado, no avisa: para.
    with pytest.raises(asiento.MovimientoSinImputar):
        lineas(mov(), None)


def test_las_cuatro_faltas_llevan_su_clave_y_quedan_fuera_de_la_tabla():
    """Fuera de `FALTAS` por lo mismo que `LibroQueElMotorNoOrigina`: esa tabla reparte faltas por comprobante, y
    un movimiento no tiene serie-número."""
    nuevas = (asiento.MovimientoSinImputar, asiento.SinCuentaDeEfectivo, asiento.TraspasoEnDosPatas,
              asiento.CuentaSinClase)
    for falta in nuevas:
        assert issubclass(falta, asiento.NoExportable) and falta.clave
        assert falta.clave not in asiento.FALTA, "no son faltas por comprobante"
    assert len({f.clave for f in nuevas}) == 4, "cada una con su clave"


def test_la_cuenta_del_efectivo_se_resuelve_en_un_solo_sitio():
    assert asiento.cuenta_de_efectivo("bbva-soles", CUENTAS) == "104101"
    assert asiento.GRUPO_EFECTIVO == "10", "el elemento del PCGE donde vive el efectivo"
    assert Decimal(CONFIG_POR_DEFECTO["cuentas"][asiento.CUENTA_ITF][:4]) == Decimal("6412")


def test_el_libro_de_tesoreria_lo_origina_el_motor_por_su_propia_puerta():
    """Desde la 12.8 el motor lo origina, y por una puerta distinta: la de los comprobantes sigue siendo de
    comprobantes, y lo dice en vez de intentarlo."""
    with pytest.raises(ValueError, match="no sale de movimientos"):
        asiento.lineas_e_indice_de_movimientos(
            Libro(ruc="20601234567", razon_social="X", periodo="202610", tipo="compra"), [], CONFIG_POR_DEFECTO)
    assert "tesoreria" in asiento.TIPOS_DEL_MOTOR
    assert date(2026, 10, 1) == LIMITES[0] and date(2026, 10, 31) == LIMITES[1]


# --- el índice, y la clave que dice la tabla (12.8) ----------------------------------------------------------------

def documento_con(*movimientos, imputaciones=None) -> tuple:
    """Lo que `lineas_e_indice_de_movimientos` recibe: la imputación y el maestro viajan DENTRO de la config, que es
    el mismo sitio por el que ya llega la imputación de un comprobante."""
    config = dict(CONFIG_POR_DEFECTO, imputaciones_de_movimientos=imputaciones or {},
                  cuentas_bancarias=CUENTAS)
    return asiento.lineas_e_indice_de_movimientos(LIBRO, list(movimientos), config)


def test_el_indice_parte_las_lineas_sin_hueco_ni_solape():
    uno, dos = mov(id_externo="m1"), mov(id_externo="m2", importe="15.00")
    imputaciones = {"m1": imputacion(cuenta_contable="421201"), "m2": imputacion(cuenta_contable="639101")}
    lineas, rangos, indice = documento_con(uno, dos, imputaciones=imputaciones)
    assert rangos == {}, "con vocabulario neutral no se numera"
    assert [(e.desde, e.hasta) for e in indice] == [(0, 2), (2, 4)]
    assert sum(len(e.lineas(lineas)) for e in indice) == len(lineas)


def test_la_cabecera_del_movimiento_lleva_la_104_y_el_efecto_ya_compuesto():
    """Dos cosas que el movimiento NO trae y que ninguna línea guarda: con qué cuenta se asentó, y que ese cargo
    era en realidad media transferencia."""
    _, _, indice = documento_con(mov(id_externo="m1"),
                                 imputaciones={"m1": imputacion(cuenta_propia="bcp-soles")})
    cabecera = indice[0].cabecera
    assert cabecera.cuenta_contable == "104101" and cabecera.efecto == "transferencia"
    assert cabecera.cuenta == "bbva-soles" and cabecera.sentido == "cargo"


def test_la_cabecera_escribe_un_movimiento_del_estandar():
    """Espejo de `como_comprobante`: fuera lo vacío y fuera lo que el estándar no declara —la 104 sale del maestro
    y el efecto es derivado—."""
    jsonschema = pytest.importorskip("jsonschema")
    from contaperu import api

    _, _, indice = documento_con(mov(id_externo="m1"), imputaciones={"m1": imputacion(cuenta_contable="421201")})
    escrito = indice[0].cabecera.como_movimiento()
    assert "cuenta_contable" not in escrito and "efecto" not in escrito
    assert not [k for k, v in escrito.items() if v in ("", None)]
    validador = jsonschema.Draft202012Validator({"$ref": "#/$defs/movimiento",
                                                 "$defs": api.esquema_open_accounting()["$defs"]})
    assert list(validador.iter_errors(escrito)) == []


def test_la_identidad_de_un_movimiento_es_su_clave_escrita():
    """Un test que las ata: si el diccionario y la tupla se separan, dos movimientos iguales dejarían de
    reconocerse en uno de los dos caminos y nadie lo vería."""
    _, _, indice = documento_con(mov(id_externo="m1"), imputaciones={"m1": imputacion(cuenta_contable="421201")})
    identidad = indice[0].identidad(LIBRO)
    assert identidad == {"ruc": LIBRO.ruc, "libro": "tesoreria", "cuenta": "bbva-soles", "referencia": "000123"}
    assert tuple(v for k, v in identidad.items() if k not in ("ruc", "libro")) == indice[0].cabecera.clave
    # Y sin número del banco, las otras cinco piezas: la misma segunda rama de `clave_de`.
    _, _, otro = documento_con(mov(id_externo="m2", referencia=""),
                               imputaciones={"m2": imputacion(cuenta_contable="421201")})
    assert set(otro[0].identidad(LIBRO)) == {"ruc", "libro", "cuenta", "fecha", "sentido", "importe", "descripcion"}


def test_la_clave_de_la_exportacion_la_dice_la_tabla():
    """`RASGOS.origen` es singular para esto: en tesorería la respuesta habla de `movimientos`, no de
    `comprobantes`. Quien la lee sabe qué hay dentro sin mirar."""
    lineas, _, indice = documento_con(mov(id_externo="m1"),
                                      imputaciones={"m1": imputacion(cuenta_contable="421201")})
    exportacion = asiento.exportacion_de(LIBRO, lineas, indice)
    assert set(exportacion) == {"huella", "movimientos"}
    assert exportacion["movimientos"][0]["lineas"] == [0, 2] and exportacion["movimientos"][0]["huella"]


def test_un_movimiento_sin_imputar_los_reune_todos_antes_de_parar():
    """Decirlos de uno en uno obliga a diez vueltas para arreglar diez."""
    with pytest.raises(asiento.MovimientoSinImputar) as e:
        documento_con(mov(id_externo="m1", referencia="A1"), mov(id_externo="m2", referencia="A2"))
    assert "A1" in str(e.value) and "A2" in str(e.value)


def test_un_traspaso_doble_para_antes_de_armar_nada():
    ida, vuelta = mov(id_externo="m1", importe="5000.00"), mov(id_externo="m2", cuenta="bcp-soles",
                                                               importe="5000.00", sentido="abono")
    with pytest.raises(asiento.TraspasoEnDosPatas):
        documento_con(ida, vuelta, imputaciones={"m1": imputacion(cuenta_propia="bcp-soles"),
                                                 "m2": imputacion(cuenta_propia="bbva-soles")})


def test_el_vocabulario_legacy_para_porque_el_libro_todavia_no_se_numera():
    """La puerta legacy, cerrada en voz alta: sin sub-diario, `clasificacion.sub_diario` reventaría con un
    `KeyError` pelado que no es un `ErrorContaperu` y que nadie atrapa."""
    config = dict(CONFIG_POR_DEFECTO, imputaciones_de_movimientos={}, cuentas_bancarias=CUENTAS)
    with pytest.raises(asiento.LibroQueTodaviaNoSeNumera, match="no se numera"):
        asiento.lineas_e_indice_de_movimientos(LIBRO, [], config, vocabulario="legacy")
