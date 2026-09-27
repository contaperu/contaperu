"""El comprobante que no mueve dinero: sale en el registro y no lleva asiento (3.5.0).

Nace de un mes real declarado ante SUNAT. Cuando un contribuyente da de baja un comprobante, SUNAT **no lo quita del
registro**: lo declara con todos sus importes en cero —hasta el tipo de cambio— para que el correlativo no quede con
huecos. En un registro de ventas de 52 filas eran cinco: tres facturas y dos notas de crédito.

El motor los trataba como comprobantes normales de importe cero, y eso dejaba dos salidas y las dos malas: o se
quedaban sin cuenta contable y el mes no cerraba nunca, o se les inventaba una y entraban al Excel como **dos líneas de
asiento a `0.00`** con su número de vóucher gastado.

**Lo que decide es el importe, no lo que SUNAT diga del comprobante.** El «Est. Comp» del SIRE se transporta y se
enseña, pero no manda: la norma no publica su tabla de valores, así que decidir con él sería inventarle un significado.
«No mueve dinero» se comprueba mirando el documento, y además atrapa el comprobante en cero que llegue de un XML, de
una foto o dictado por un ERP, que no trae estado ninguno.
"""
from __future__ import annotations

from datetime import date

from contaperu import api, asiento as asi, comparar_sire, validar
from contaperu.asiento import motor
from contaperu.drivers import concar as driver_concar
from contaperu.modelo import Comprobante, Libro
from contaperu.pipeline import preparacion as prep
from util import comprobante, con_imputaciones, en_secciones, por_la_fachada

CONTAB = con_imputaciones(prep.config_aplicada(en_secciones(None, "concar"), "concar"))
MES = (date(2026, 2, 1), date(2026, 2, 28))
VENTAS = Libro(ruc="20601111111", razon_social="EMPRESA DE PRUEBA SAC", periodo="202602", tipo="venta")

diagnosticar = por_la_fachada(api.diagnosticar)
exportar = por_la_fachada(api.exportar)

LIBRO = {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202602", "tipo": "venta"}


def dado_de_baja(**kw) -> Comprobante:
    """Un comprobante como los declara SUNAT cuando se da de baja: todo en cero, con su cuenta ya puesta para que lo
    único que decida sea el importe."""
    base = dict(tipo_cp="01", serie="F001", numero="117", fecha_emision="2026-02-10",
                contraparte_doc="20602222226", contraparte_nombre="CLIENTE DE PRUEBA SAC",
                base_gravada="0", igv="0", total="0", origen="sire", estado_sunat="2",
                cuenta_contable="701101", centro_costo="CC-64")
    return comprobante(**{**base, **kw})


def lineas(c: Comprobante, config: dict = CONTAB) -> list:
    return motor.lineas_del_comprobante(c, config, MES, "0001", opciones=driver_concar.OPCIONES, es_venta=True)


# ── El asiento ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_un_comprobante_en_cero_no_produce_asiento():
    """Antes salían dos líneas a `0.00` que cuadraban entre sí: `121201 D 0.00` y `701101 H 0.00`. Un vóucher con dos
    líneas en cero no es contabilidad, es ruido en el diario."""
    assert lineas(dado_de_baja()) == []


def test_un_comprobante_en_cero_no_pide_cuenta_ni_centro():
    """Y esto es lo que de verdad dolía: a un comprobante dado de baja no se le pone cuenta, así que el mes se quedaba
    incompleto para siempre. Se comprueba sin cuenta Y sin centro, que son las dos cosas que se le pedían."""
    c = dado_de_baja(cuenta_contable="", centro_costo="")
    assert lineas(c) == []                                        # antes: SinCuenta
    assert asi.comprobantes_sin_cuenta([c], CONTAB, True) == [c]   # la regla suelta sigue diciendo la verdad…
    # …y lo que cuenta es que `faltantes_para`, que es por donde pasan los tres caminos (diagnóstico, exportación y
    # `exigir_requisitos`), ya no lo pide.
    faltan = asi.faltantes_para([c], CONTAB, True, exige={"cuenta_contable", "centro_costo"})
    assert faltan["sin_cuenta"] == [] and faltan["sin_centro"] == []


def test_un_comprobante_en_cero_no_gasta_un_numero_de_voucher():
    """Si consumiera uno, el asiento tendría un vóucher sin líneas y el rango que se recuerda para el mes siguiente
    contaría comprobantes que nunca se escribieron."""
    venta = comprobante(tipo_cp="01", serie="F001", numero="118", fecha_emision="2026-02-11",
                        contraparte_doc="20602222226", contraparte_nombre="CLIENTE DE PRUEBA SAC",
                        base_gravada="100", igv="18", total="118", cuenta_contable="701101", centro_costo="CC-64")
    numeros, rangos = asi.numerar_en_orden([dado_de_baja(), venta], CONTAB, "202602", {"05": 1}, es_venta=True)
    assert numeros == ["", "020001"]                              # el suyo en blanco; el 1 se lo lleva la venta
    assert rangos["05"]["comprobantes"] == 1 and rangos["05"]["hasta"] == 1


def test_lo_que_mueve_dinero_sigue_asentandose():
    """Los tres casos que NO se apartan, y el segundo es el que más importa: total cero con IGV distinto de cero existe
    de verdad —una nota de crédito que SUNAT tiene con la base sin declarar— y ahí sí hay algo que mirar."""
    normal = dado_de_baja(base_gravada="100", igv="18", total="118")
    assert len(lineas(normal)) == 3
    con_igv = dado_de_baja(igv="18")                              # total 0 pero IGV 18
    assert len(lineas(con_igv)) == 3
    con_detraccion = dado_de_baja(detraccion={"codigo": "022", "porcentaje": "12", "monto": "0"})
    assert lineas(con_detraccion) != []
    con_retencion = dado_de_baja(tipo_cp="02", serie="R001", retencion="10")
    assert asi.sin_efecto_contable(con_retencion) is False


def test_el_predicado_no_mira_el_estado_de_sunat():
    """**El test que impide que esto se apoye en un código sin tabla publicada.** El mismo comprobante en cero se
    aparta igual con estado «2», con «1», con uno inventado o sin estado — y uno que mueve dinero se asienta igual
    aunque SUNAT lo marque con «2»."""
    for estado in ("2", "1", "", "9", "a1"):
        assert asi.sin_efecto_contable(dado_de_baja(estado_sunat=estado)) is True
        assert lineas(dado_de_baja(estado_sunat=estado)) == []
    # Y al revés: el estado no aparta a quien sí mueve dinero.
    assert lineas(dado_de_baja(estado_sunat="2", base_gravada="100", igv="18", total="118")) != []


def test_con_la_opcion_encendida_vuelve_a_asentarse():
    """Configurable por quien integre el ERP (John, 26-sep-2026), con el comportamiento nuevo por defecto. Quien
    quiera esas líneas en cero las tiene con una clave, y sin tocar el motor."""
    con_opcion = {**CONTAB, "asentar_sin_efecto_contable": True}
    assert [(l.cuenta, l.debe_haber, l.importe) for l in lineas(dado_de_baja(), con_opcion)] == [
        ("121201", "D", "0.00"), ("701101", "H", "0.00")]
    # Y entonces vuelve a pedir cuenta y a gastar número, que es el paquete entero.
    faltan = asi.faltantes_para([dado_de_baja(cuenta_contable="")], con_opcion, True, exige={"cuenta_contable"})
    assert len(faltan["sin_cuenta"]) == 1
    numeros, _ = asi.numerar_en_orden([dado_de_baja()], con_opcion, "202602", {"05": 1}, es_venta=True)
    assert numeros == ["020001"]
    # La clave viaja en la configuración general y está declarada, así que una aplicación la puede pintar.
    assert "asentar_sin_efecto_contable" in api.configuracion_por_defecto()
    assert api.errores_de_configuracion({"asentar_sin_efecto_contable": True}) == []


# ── El registro: ahí sí sale ────────────────────────────────────────────────────────────────────────────────────

def fila(**kw) -> dict:
    """El comprobante como lo manda una aplicación, con su cuenta y su centro: `por_la_fachada` los convierte en su
    imputación (open-accounting 0.3)."""
    base = dict(tipo_cp="01", serie="F001", numero="117", fecha_emision="2026-02-10",
                contraparte_doc="20602222226", contraparte_nombre="CLIENTE DE PRUEBA SAC",
                base_gravada="0", igv="0", total="0", origen="sire", estado_sunat="2",
                cuenta_contable="701101", centro_costo="CC-64")
    return {**base, **kw}


LA_VENTA = dict(numero="118", base_gravada="100", igv="18", total="118", estado_sunat="1")


def test_un_comprobante_en_cero_sigue_en_el_registro_del_sire():
    """**El hecho central**: el asiento es una cosa y el registro es otra. SUNAT declara lo que se da de baja en cero
    precisamente para no dejar huecos en el correlativo, así que quitarlo del TXT sería romper lo que se declara."""
    r = exportar({"open_accounting": "1.0", "libro": LIBRO, "comprobantes": [fila(), fila(**LA_VENTA)]},
                 driver="sire")
    assert r["comprobantes"] == 2
    filas = r["texto"].splitlines()
    assert len(filas) == 2
    assert filas[0].split("|")[8] == "117"      # el dado de baja tiene su fila, con su número…
    assert filas[0].split("|")[25] == "0.00"    # …y su total en cero, como lo tiene SUNAT


def test_el_diagnostico_los_cuenta_aparte_y_el_mes_esta_listo():
    """No cuentan como faltantes ni impiden exportar, y tienen su propia casilla: `fuera_del_destino` significa otra
    cosa —«este destino no lleva ese tipo de comprobante»— y mezclarlos borraría la diferencia."""
    doc = {"open_accounting": "1.0", "libro": LIBRO,
           "comprobantes": [fila(cuenta_contable="", centro_costo=""), fila(**LA_VENTA)]}
    d = diagnosticar(doc, driver="concar")
    assert d["listo_para_exportar"] is True and d["por_que_no"] == []
    assert d["totales"]["sin_efecto_contable"] == 1
    assert d["totales"]["fuera_del_destino"] == 0
    assert d["faltantes"]["sin_cuenta"] == [] and d["faltantes"]["sin_centro"] == []
    # Y el de al lado, que sí mueve dinero, sigue exigiéndose: esto no relaja nada para los demás.
    sin_cuenta = diagnosticar({"open_accounting": "1.0", "libro": LIBRO,
                               "comprobantes": [fila(**{**LA_VENTA, "cuenta_contable": "", "centro_costo": ""})]},
                              driver="concar")
    assert sin_cuenta["por_que_no"] == ["1 sin cuenta contable"]


# ── Lo que se dice de él ────────────────────────────────────────────────────────────────────────────────────────

def test_el_aviso_de_la_propuesta_cita_el_estado_y_no_lo_traduce():
    """El aviso enseña el dato y no lo interpreta: en ninguna parte dice «anulado», porque la norma no publica la
    tabla de valores del campo 35 y el motor no se la inventa. Si alguien añade la traducción, esto se pone rojo."""
    c = dado_de_baja()
    validar.revisar([c], VENTAS)
    codigos = [o.codigo for o in c.observaciones]
    assert "TOTAL_CERO_EN_LA_PROPUESTA" in codigos and "TOTAL_CERO" not in codigos
    texto = next(o.texto for o in c.observaciones if o.codigo == "TOTAL_CERO_EN_LA_PROPUESTA")
    assert "«2»" in texto                      # cita el valor tal como vino
    assert "anulad" not in texto.lower()       # y no dice lo que significa
    assert all(o.nivel == "aviso" for o in c.observaciones) and not c.tiene_errores


def test_una_nota_en_cero_ya_no_se_calla():
    """El agujero que tenía el aviso: `TOTAL_CERO` llevaba un `and not c.es_nota` desde el commit inicial del núcleo,
    sin test que lo defendiera ni motivo escrito. Por eso, de los cinco comprobantes en cero del mes real, las dos
    notas de crédito salían `estado="ok"` sin una sola palabra."""
    nota = dado_de_baja(tipo_cp="07", serie="FC01", numero="35", ref_tipo_cp="01", ref_serie="F001",
                        ref_numero="83", ref_fecha="2025-12-30")
    validar.revisar([nota], VENTAS)
    assert [o.codigo for o in nota.observaciones if o.codigo.startswith("TOTAL_CERO")] == \
           ["TOTAL_CERO_EN_LA_PROPUESTA"]
    # Y en cualquier otro origen sigue siendo el aviso de siempre, que significa otra cosa: un total por rellenar.
    de_una_foto = dado_de_baja(tipo_cp="07", serie="FC01", numero="35", origen="vision", estado_sunat="",
                               ref_tipo_cp="01", ref_serie="F001", ref_numero="83", ref_fecha="2025-12-30")
    validar.revisar([de_una_foto], VENTAS)
    assert [o.codigo for o in de_una_foto.observaciones if o.codigo.startswith("TOTAL_CERO")] == ["TOTAL_CERO"]


def test_un_mes_con_lo_que_sunat_declara_sale_por_los_cuatro_destinos():
    """La prueba de que las dos mitades funcionan juntas, con las tres formas en las que SUNAT complica un mes: un
    comprobante dado de baja (en cero), una nota de crédito declarada en las columnas de descuento, y una nota con la
    base sin declarar, que es la que bloqueaba el mes entero por los cuatro destinos a la vez.

    Antes de la 3.5.0 esto devolvía `listo_para_exportar: False` con «1 comprobantes con observaciones que bloquean», y
    `pipeline/salida.generar` miraba los errores ANTES de saber el destino: caían el TXT del SIRE, CONCAR, CONTASIS y
    STARSOFT por igual."""
    nota_descuento = fila(tipo_cp="07", serie="FC01", numero="37", base_gravada="7464.75", igv="1343.65",
                          dscto_base="7464.75", dscto_igv="1343.65", total="8808.40", estado_sunat="1",
                          tipo_nota="09", ref_tipo_cp="01", ref_serie="F001", ref_numero="83",
                          ref_fecha="2025-12-30")
    nota_sin_base = fila(tipo_cp="07", serie="E001", numero="222", base_gravada="0", igv="4546.31",
                         total="29803.61", estado_sunat="1", tipo_nota="01", ref_tipo_cp="01", ref_serie="E001",
                         ref_numero="1003", ref_fecha="2026-02-04")
    doc = {"open_accounting": "1.0", "libro": LIBRO,
           "comprobantes": [fila(), fila(**LA_VENTA), nota_descuento, nota_sin_base]}
    d = diagnosticar(doc, driver="sire")
    assert d["listo_para_exportar"] is True and d["por_que_no"] == []
    assert d["totales"]["con_error"] == 0 and d["totales"]["sin_efecto_contable"] == 1
    # Y sale por los cuatro destinos sin forzar nada: el registro los lleva y el asiento se salta el que no mueve dinero.
    for driver in ("sire", "concar", "contasis", "starsoft"):
        r = exportar(doc, driver=driver)
        assert r["comprobantes"] >= 3, driver


def test_el_comparador_reconoce_el_tipo_de_cambio_de_un_comprobante_dado_de_baja():
    """SUNAT escribe `1.000` en el TC de un comprobante normal en soles y **`0.000`** en uno que da de baja; el archivo
    de reemplazo lo manda vacío. Los tres dicen lo mismo, y hasta la 3.5.0 el comparador solo conocía dos: un mes con
    cinco comprobantes dados de baja cantaba cinco diferencias en un campo que rellena la propia Administración."""
    i_tc = comparar_sire.VENTAS.i_tc
    assert comparar_sire._norm(i_tc, "0.000") == comparar_sire._norm(i_tc, "1.000") == comparar_sire._norm(i_tc, "")
    # Y un tipo de cambio de verdad sigue comparándose: esto no anula el campo, reconoce sus formas de «no hay».
    assert comparar_sire._norm(i_tc, "3.755") == "3.755"
