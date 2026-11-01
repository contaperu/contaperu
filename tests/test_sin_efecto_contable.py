"""El comprobante que no mueve dinero: sale en el registro, y desde la 15.0 también en el asiento con sus líneas a cero.

Nace de un mes real declarado ante SUNAT. Cuando un contribuyente da de baja un comprobante, SUNAT **no lo quita del
registro**: lo declara con todos sus importes en cero —hasta el tipo de cambio— para que el correlativo no quede con
huecos. En un registro de ventas de 52 filas eran cinco: tres facturas y dos notas de crédito.

De la 3.5.0 a la 14.x el motor los apartaba del asiento: no pedían cuenta ni centro, no gastaban número de vóucher y no
producían líneas. **Desde la 15.0 se asientan de fábrica** (John, 31-oct-2026): «12 DEBE 0 / 7011 HABER 0 así debe
salir». Un estudio registra en su sistema lo que SUNAT declara en cero, para que su registro cuadre con el de SUNAT, y
traerlo es decisión de quien importa: por eso **se le pide lo que exija su sistema, como a cualquier otro**, y no una
regla aparte. Lo de antes sigue con `asentar_sin_efecto_contable: false`, y sus pruebas lo piden así, explícito.

**Lo que decide es el importe, no lo que SUNAT diga del comprobante.** El «Est. Comp» del SIRE se transporta y se
enseña, pero no manda: la norma no publica su tabla de valores, así que decidir con él sería inventarle un significado.
«No mueve dinero» se comprueba mirando el documento, y además atrapa el comprobante en cero que llegue de un XML, de
una foto o dictado por un ERP, que no trae estado ninguno.
"""
from __future__ import annotations

from datetime import date

import pytest

from contaperu import api, asiento as asi
from contaperu.tributos import validar
from contaperu.tributos import comparar_sire
from contaperu.asiento import comprobante as motor
from contaperu.drivers import concar as driver_concar
from contaperu.modelo import Comprobante, Libro
from contaperu.pipeline import preparacion as prep
from contaperu.modelo.libro import RASGOS
from util import comprobante, con_imputaciones, en_secciones, por_la_fachada

CONTAB = con_imputaciones(prep.config_aplicada(en_secciones(None, "concar"), "concar"))
APAGADO = {**CONTAB, "asentar_sin_efecto_contable": False}      # lo de la 3.5.0 a la 14.x
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


def la_venta_de_al_lado() -> Comprobante:
    return comprobante(tipo_cp="01", serie="F001", numero="118", fecha_emision="2026-02-11",
                       contraparte_doc="20602222226", contraparte_nombre="CLIENTE DE PRUEBA SAC",
                       base_gravada="100", igv="18", total="118", cuenta_contable="701101", centro_costo="CC-64")


def lineas(c: Comprobante, config: dict = CONTAB) -> list:
    return motor.lineas_del_comprobante(c, config, MES, "0001", opciones=driver_concar.OPCIONES, libro=RASGOS["venta"])


def en_texto(ls: list) -> list[tuple[str, str, str]]:
    return [(linea.cuenta, linea.debe_haber, linea.importe) for linea in ls]


# ── De fábrica (15.0): se asienta, con sus líneas a cero ───────────────────────────────────────────────────────────

def test_de_fabrica_un_comprobante_en_cero_sale_en_el_asiento_con_sus_lineas_a_cero():
    """Lo que John pidió al ver que su venta dada de baja faltaba en el Excel de CONCAR: «12 DEBE 0 / 7011 HABER 0 así
    debe salir». Y una clave AUSENTE es el de fábrica: solo un `false` escrito vuelve a lo de antes, así que una
    configuración guardada antes de la 15.0, que no la tiene, también asienta."""
    esperado = [("121201", "D", "0.00"), ("701101", "H", "0.00")]
    assert en_texto(lineas(dado_de_baja())) == esperado
    sin_la_clave = {k: v for k, v in CONTAB.items() if k != "asentar_sin_efecto_contable"}
    assert en_texto(lineas(dado_de_baja(), sin_la_clave)) == esperado
    assert asi.asienta_sin_efecto(None) is True and asi.asienta_sin_efecto({}) is True
    # La clave viaja en la configuración general y está declarada, así que una aplicación la puede pintar y apagar.
    assert api.configuracion_por_defecto()["asentar_sin_efecto_contable"] is True
    assert api.errores_de_configuracion({"asentar_sin_efecto_contable": False}) == []


def test_de_fabrica_gasta_su_numero_de_voucher():
    """Si sale en el asiento, sale con su vóucher: el correlativo de CONCAR no puede saltarse un asiento que existe, y
    el rango que se recuerda para el mes siguiente cuenta los dos."""
    numeros, rangos = asi.numerar_en_orden([dado_de_baja(), la_venta_de_al_lado()], CONTAB, "202602", {"05": 1},
                                           libro=RASGOS["venta"])
    assert numeros == ["020001", "020002"]
    assert rangos["05"]["comprobantes"] == 2 and rangos["05"]["hasta"] == 2


def test_de_fabrica_sin_cuenta_se_planta_como_cualquier_otro():
    """La cara del paquete que se nota: sin cuenta, el asiento no se arma —igual que el de una factura con importes—,
    porque traerlo fue decisión de quien importa y ponerle lo que su sistema pide también lo es."""
    sin_cuenta = dado_de_baja(cuenta_contable="", centro_costo="")
    with pytest.raises(asi.SinCuenta):
        lineas(sin_cuenta)
    faltan = asi.faltantes_para([sin_cuenta], CONTAB, RASGOS["venta"], exige={"cuenta_contable", "centro_costo"})
    assert faltan["sin_cuenta"] == [sin_cuenta]


# ── Lo que se le pide: lo de su sistema, ni más ni menos ───────────────────────────────────────────────────────────

def fila(**kw) -> dict:
    """El comprobante como lo manda una aplicación, con su cuenta y su centro: `por_la_fachada` los convierte en su
    imputación (open-accounting 0.3)."""
    base = dict(tipo_cp="01", serie="F001", numero="117", fecha_emision="2026-02-10",
                contraparte_doc="20602222226", contraparte_nombre="CLIENTE DE PRUEBA SAC",
                base_gravada="0", igv="0", total="0", origen="sire", estado_sunat="2",
                cuenta_contable="701101", centro_costo="CC-64")
    return {**base, **kw}


LA_VENTA = dict(numero="118", base_gravada="100", igv="18", total="118", estado_sunat="1")

# Cada situación: lo que le falta al comprobante y la configuración del entorno. `70` lleva centro de fábrica
# (`cuentas_con_centro`), así que la tercera lo quita de la lista para que la cuenta NO lo lleve.
SITUACIONES = {
    "sin cuenta": (dict(cuenta_contable="", centro_costo=""), None),
    "sin centro en una cuenta que lo lleva": (dict(centro_costo=""), None),
    "sin centro en una cuenta que no lo lleva": (dict(centro_costo=""), {"cuentas_con_centro": ["62", "63", "65"]}),
    "sin centro con los centros apagados": (dict(centro_costo=""), {"usa_centros_costo": False}),
    "con todo puesto": ({}, None),
}
DESTINOS = ("concar", "contasis", "starsoft", "csv", "asiento_contable", "sire")


def veredicto(driver: str, situacion: str, **importes) -> tuple:
    """Lo que el diagnóstico dice de UN comprobante en esa situación: si está listo, por qué no, y cuántos caen en cada
    falta. Sin el serie-número, para poder compararlo con el de otro comprobante."""
    cambio, config = SITUACIONES[situacion]
    d = diagnosticar({"open_accounting": "4.0", "libro": LIBRO, "comprobantes": [fila(**{**importes, **cambio})]},
                     driver=driver, configuracion=config)
    return d["listo_para_exportar"], d["por_que_no"], {falta: len(cuales) for falta, cuales in d["faltantes"].items()}


@pytest.mark.parametrize("driver", DESTINOS)
@pytest.mark.parametrize("situacion", list(SITUACIONES))
def test_de_fabrica_se_le_pide_lo_mismo_que_a_una_factura_con_importes(driver, situacion):
    """**El corazón del cambio** (John: «un comprobante en cero sí debe pedir lo que la configuración de cada sistema
    lo diga»). No hay una regla aparte para el cero: cada destino con la configuración del entorno decide, y el
    comprobante en cero recibe exactamente el veredicto de una factura con importes en la misma situación."""
    assert veredicto(driver, situacion) == veredicto(driver, situacion, **LA_VENTA)


def test_lo_que_pide_cada_sistema_es_lo_de_siempre():
    """La comparación de arriba pasaría en verde si el cero y la factura dejaran de pedir lo mismo A LA VEZ; esto ancla
    lo que se le pide al comprobante en cero, destino por destino. CONCAR, la cuenta, y el centro solo si esa cuenta lo
    lleva y los centros están encendidos; CONTASIS, la cuenta y nunca el centro, porque no lo exige; el SIRE, nada,
    porque el registro de SUNAT no lleva cuentas."""
    por_que_no = {
        ("concar", "sin cuenta"): ["1 sin cuenta contable"],
        ("concar", "sin centro en una cuenta que lo lleva"): ["1 sin centro de costo en una cuenta que lo lleva"],
        ("concar", "sin centro en una cuenta que no lo lleva"): [],
        ("concar", "sin centro con los centros apagados"): [],
        ("contasis", "sin cuenta"): ["1 sin cuenta contable"],
        ("contasis", "sin centro en una cuenta que lo lleva"): [],
        ("sire", "sin cuenta"): [],
    }
    for (driver, situacion), esperado in por_que_no.items():
        listo, motivos, _ = veredicto(driver, situacion)
        assert (listo, motivos) == (not esperado, esperado), (driver, situacion)
        # Y al exportar, que es lo que se vive: el archivo sale con él, o se planta con la falta de su sistema. El
        # diagnóstico solo cuenta lo que el destino exige, pero la exportación lo hace cumplir por su lado.
        cambio, config = SITUACIONES[situacion]
        doc = {"open_accounting": "4.0", "libro": LIBRO, "comprobantes": [fila(**cambio)]}
        if esperado:
            with pytest.raises(asi.NoExportable):
                exportar(doc, driver=driver, configuracion=config)
        else:
            assert exportar(doc, driver=driver, configuracion=config)["comprobantes"] == 1, (driver, situacion)


# ── Apagado: lo de la 3.5.0 a la 14.x, con la clave en `false` ─────────────────────────────────────────────────────

def test_apagado_un_comprobante_en_cero_no_produce_asiento():
    """Para quien prefiera no ver en su diario un vóucher con dos líneas a `0.00` que cuadran entre sí."""
    assert lineas(dado_de_baja(), APAGADO) == []


def test_apagado_un_comprobante_en_cero_no_pide_cuenta_ni_centro():
    """Lo que llevó a apagarlo en la 3.5.0: a un comprobante dado de baja no se le ponía cuenta, así que el mes se
    quedaba incompleto para siempre. Se comprueba sin cuenta Y sin centro, que son las dos cosas que se le pedían."""
    c = dado_de_baja(cuenta_contable="", centro_costo="")
    assert lineas(c, APAGADO) == []                                    # encendido: SinCuenta
    assert asi.comprobantes_sin_cuenta([c], APAGADO, RASGOS["venta"]) == [c]   # la regla suelta sigue diciendo la verdad…
    # …y lo que cuenta es que `faltantes_para`, que es por donde pasan los tres caminos (diagnóstico, exportación y
    # `exigir_requisitos`), no lo pide.
    faltan = asi.faltantes_para([c], APAGADO, RASGOS["venta"], exige={"cuenta_contable", "centro_costo"})
    assert faltan["sin_cuenta"] == [] and faltan["sin_centro"] == []


def test_apagado_un_comprobante_en_cero_no_gasta_un_numero_de_voucher():
    """Si consumiera uno, el asiento tendría un vóucher sin líneas y el rango que se recuerda para el mes siguiente
    contaría comprobantes que nunca se escribieron."""
    numeros, rangos = asi.numerar_en_orden([dado_de_baja(), la_venta_de_al_lado()], APAGADO, "202602", {"05": 1},
                                           libro=RASGOS["venta"])
    assert numeros == ["", "020001"]                              # el suyo en blanco; el 1 se lo lleva la venta
    assert rangos["05"]["comprobantes"] == 1 and rangos["05"]["hasta"] == 1


def test_apagado_el_diagnostico_los_cuenta_aparte_y_el_mes_esta_listo():
    """No cuentan como faltantes ni impiden exportar, y tienen su propia casilla: `fuera_del_destino` significa otra
    cosa —«este destino no lleva ese tipo de comprobante»— y mezclarlos borraría la diferencia."""
    apagado = {"asentar_sin_efecto_contable": False}
    doc = {"open_accounting": "4.0", "libro": LIBRO,
           "comprobantes": [fila(cuenta_contable="", centro_costo=""), fila(**LA_VENTA)]}
    d = diagnosticar(doc, driver="concar", configuracion=apagado)
    assert d["listo_para_exportar"] is True and d["por_que_no"] == []
    assert d["totales"]["sin_efecto_contable"] == 1
    assert d["totales"]["fuera_del_destino"] == 0
    assert d["faltantes"]["sin_cuenta"] == [] and d["faltantes"]["sin_centro"] == []
    # Y el de al lado, que sí mueve dinero, sigue exigiéndose: esto no relaja nada para los demás.
    sin_cuenta = diagnosticar({"open_accounting": "4.0", "libro": LIBRO,
                               "comprobantes": [fila(**{**LA_VENTA, "cuenta_contable": "", "centro_costo": ""})]},
                              driver="concar", configuracion=apagado)
    assert sin_cuenta["por_que_no"] == ["1 sin cuenta contable"]
    # Encendido, el mismo mes se planta en el comprobante en cero, y la casilla se queda en 0: ya no se apartan.
    encendido = diagnosticar(doc, driver="concar")
    assert encendido["por_que_no"] == ["1 sin cuenta contable"] and encendido["totales"]["sin_efecto_contable"] == 0


# ── Con los dos ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_lo_que_mueve_dinero_se_asienta_siempre():
    """Los tres casos que NUNCA se apartan, con la clave encendida o apagada, y el segundo es el que más importa: total
    cero con IGV distinto de cero existe de verdad —una nota de crédito que SUNAT tiene con la base sin declarar— y
    ahí sí hay algo que mirar."""
    for config in (CONTAB, APAGADO):
        normal = dado_de_baja(base_gravada="100", igv="18", total="118")
        assert len(lineas(normal, config)) == 3
        con_igv = dado_de_baja(igv="18")                              # total 0 pero IGV 18
        assert len(lineas(con_igv, config)) == 3
        con_detraccion = dado_de_baja(detraccion={"codigo": "022", "porcentaje": "12", "monto": "0"})
        assert lineas(con_detraccion, config) != []
    con_retencion = dado_de_baja(tipo_cp="02", serie="R001", retencion_4ta="10")
    assert asi.sin_efecto_contable(con_retencion) is False


def test_el_predicado_no_mira_el_estado_de_sunat():
    """**El test que impide que esto se apoye en un código sin tabla publicada.** El mismo comprobante en cero se
    trata igual con estado «2», con «1», con uno inventado o sin estado —asentado de fábrica, apartado con la clave
    apagada— y uno que mueve dinero se asienta igual aunque SUNAT lo marque con «2»."""
    for estado in ("2", "1", "", "9", "a1"):
        assert asi.sin_efecto_contable(dado_de_baja(estado_sunat=estado)) is True
        assert len(lineas(dado_de_baja(estado_sunat=estado))) == 2
        assert lineas(dado_de_baja(estado_sunat=estado), APAGADO) == []
    # Y al revés: el estado no aparta a quien sí mueve dinero.
    assert lineas(dado_de_baja(estado_sunat="2", base_gravada="100", igv="18", total="118"), APAGADO) != []


def test_un_comprobante_en_cero_sigue_en_el_registro_del_sire():
    """**El hecho central**: el asiento es una cosa y el registro es otra. SUNAT declara lo que se da de baja en cero
    precisamente para no dejar huecos en el correlativo, así que quitarlo del TXT sería romper lo que se declara —con
    la clave encendida o apagada—."""
    for config in (None, {"asentar_sin_efecto_contable": False}):
        r = exportar({"open_accounting": "4.0", "libro": LIBRO, "comprobantes": [fila(), fila(**LA_VENTA)]},
                     driver="sire", configuracion=config)
        assert r["comprobantes"] == 2
        filas = r["texto"].splitlines()
        assert len(filas) == 2
        assert filas[0].split("|")[8] == "117"      # el dado de baja tiene su fila, con su número…
        assert filas[0].split("|")[25] == "0.00"    # …y su total en cero, como lo tiene SUNAT


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
    STARSOFT por igual. Desde la 15.0 el comprobante en cero entra también en el asiento: salen los cuatro."""
    nota_descuento = fila(tipo_cp="07", serie="FC01", numero="37", base_gravada="7464.75", igv="1343.65",
                          dscto_base="7464.75", dscto_igv="1343.65", total="8808.40", estado_sunat="1",
                          tipo_nota="09", ref_tipo_cp="01", ref_serie="F001", ref_numero="83",
                          ref_fecha="2025-12-30")
    nota_sin_base = fila(tipo_cp="07", serie="E001", numero="222", base_gravada="0", igv="4546.31",
                         total="29803.61", estado_sunat="1", tipo_nota="01", ref_tipo_cp="01", ref_serie="E001",
                         ref_numero="1003", ref_fecha="2026-02-04")
    doc = {"open_accounting": "4.0", "libro": LIBRO,
           "comprobantes": [fila(), fila(**LA_VENTA), nota_descuento, nota_sin_base]}
    d = diagnosticar(doc, driver="sire")
    assert d["listo_para_exportar"] is True and d["por_que_no"] == []
    assert d["totales"]["con_error"] == 0 and d["totales"]["sin_efecto_contable"] == 0
    for driver in ("sire", "concar", "contasis", "starsoft"):
        assert exportar(doc, driver=driver)["comprobantes"] == 4, driver
    # Con la clave apagada sale igual por los cuatro, y el asiento se salta el que no mueve dinero.
    apagado = {"asentar_sin_efecto_contable": False}
    assert diagnosticar(doc, driver="sire", configuracion=apagado)["totales"]["sin_efecto_contable"] == 1
    for driver in ("sire", "concar", "contasis", "starsoft"):
        assert exportar(doc, driver=driver, configuracion=apagado)["comprobantes"] >= 3, driver


def test_el_comparador_reconoce_el_tipo_de_cambio_de_un_comprobante_dado_de_baja():
    """SUNAT escribe `1.000` en el TC de un comprobante normal en soles y **`0.000`** en uno que da de baja; el archivo
    de reemplazo lo manda vacío. Los tres dicen lo mismo, y hasta la 3.5.0 el comparador solo conocía dos: un mes con
    cinco comprobantes dados de baja cantaba cinco diferencias en un campo que rellena la propia Administración."""
    i_tc = comparar_sire.VENTAS.i_tc
    assert comparar_sire._norm(i_tc, "0.000") == comparar_sire._norm(i_tc, "1.000") == comparar_sire._norm(i_tc, "")
    # Y un tipo de cambio de verdad sigue comparándose: esto no anula el campo, reconoce sus formas de «no hay».
    assert comparar_sire._norm(i_tc, "3.755") == "3.755"
