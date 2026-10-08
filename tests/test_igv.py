"""El IGV se lee del comprobante; nunca se supone (John, 10-sep-2026).

La tasa puede ser 18, 10.5 o 0 y sale de la base y el IGV de cada comprobante. Estos tests vigilan
las dos cosas que eso obliga: que el recálculo no invente ninguna tasa, y que no toque el total.
"""
from decimal import Decimal as D

import pytest

from contaperu import catalogos as cat
from contaperu.tributos import igv
from contaperu.drivers.concar import tasa_igv_entera as tasa_igv
from contaperu.modelo import Comprobante


def cp(**k):
    base = dict(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-08-11", moneda="PEN",
                contraparte_tipo_doc="6", contraparte_doc="20607777773", contraparte_nombre="PROVEEDOR SAC",
                base_gravada="0", igv="0", total="118")
    base.update(k)
    return Comprobante(**base)


def test_escribir_el_igv_de_un_inafecto_lo_vuelve_afecto_sin_tocar_el_total():
    r = igv.aplicar_igv(cp(inafecto="118", total="118"), "18")
    assert (r["base_gravada"], r["igv"], r["inafecto"], r["exonerado"]) == (D("100"), D("18"), 0, 0)


def test_la_tasa_no_esta_escrita_en_ninguna_parte():
    """Un comprobante al 10.5 % se recalcula igual que uno al 18: nadie le impone el 18."""
    r = igv.aplicar_igv(cp(inafecto="110.50", total="110.50"), "10.50")
    assert r["base_gravada"] == D("100.00")
    assert igv.tasa_calculada(r["igv"], r["base_gravada"]) == D("10.5")


def test_quitar_el_igv_lo_manda_a_inafecto():
    r = igv.aplicar_igv(cp(base_gravada="100", igv="18", total="118"), "0")
    assert (r["base_gravada"], r["igv"], r["inafecto"]) == (0, 0, D("118"))


def test_cambiar_el_igv_de_un_mixto_deja_el_exonerado_donde_estaba():
    r = igv.aplicar_igv(cp(base_gravada="100", igv="18", exonerado="50", total="168"), "10")
    assert (r["base_gravada"], r["igv"], r["exonerado"]) == (D("108"), D("10"), D("50"))


def test_los_otros_cargos_se_quedan_fuera_de_la_base():
    """ICBPER y otros cargos forman el total pero no son base: la fórmula es la de `validar.py`."""
    r = igv.aplicar_igv(cp(inafecto="120", icbper="0.50", otros="1.50", total="122"), "18")
    assert r["base_gravada"] == D("102")


def test_un_igv_imposible_no_se_reparte():
    for malo in ("150", "-1", "abc"):
        with pytest.raises(igv.IgvImposible):
            igv.aplicar_igv(cp(inafecto="100", total="100"), malo)


def test_la_columna_ao_es_la_tasa_del_comprobante_redondeada_a_entero():
    """CONCAR solo admite enteros (John): se redondea la tasa del comprobante, sin respaldo ni atajos."""
    assert tasa_igv(D("18"), D("100")) == 18
    assert tasa_igv(D("10.5"), D("100")) == 11
    assert tasa_igv(D("0"), D("100")) == ""
    assert tasa_igv(D("18"), D("0")) == ""       # sin base no hay tasa que leer, y no se inventa


# ── La nota de crédito de descuento global y la celda «Total» (11-sep-2026) ──────────────────────────

def nc_descuento(**k):
    return cp(tipo_cp="07", base_gravada="100", igv="18", dscto_base="100", dscto_igv="18", total="118", **k)


def test_los_descuentos_no_mueven_la_base_al_recalcular():
    """Antes `_cargos` restaba el descuento y la base de una NC de descuento salía casi al doble."""
    assert igv.aplicar_igv(nc_descuento(), "18")["base_gravada"] == D("100")


def test_una_nota_entera_como_descuento_sigue_entera_al_cambiar_el_igv():
    r = igv.aplicar_igv(nc_descuento(), "10")
    assert (r["base_gravada"], r["igv"], r["dscto_base"], r["dscto_igv"]) == (D("108"), D("10"), D("108"), D("10"))


def test_sin_igv_el_descuento_se_va_con_la_base():
    r = igv.aplicar_igv(nc_descuento(), "0")
    assert (r["inafecto"], r["dscto_base"], r["dscto_igv"]) == (D("118"), 0, 0)


def test_un_descuento_parcial_que_ya_no_cabe_se_dice():
    with pytest.raises(igv.IgvImposible, match="descuento"):
        igv.aplicar_igv(cp(tipo_cp="07", base_gravada="100", igv="18", dscto_base="50", dscto_igv="9",
                           total="118"), "5")


def test_el_total_lo_absorbe_la_base_y_el_igv_se_queda():
    r = igv.aplicar_total(cp(base_gravada="100", igv="18", total="118"), "236")
    assert (r["total"], r["base_gravada"]) == (D("236"), D("218")) and "igv" not in r


def test_el_total_se_recalcula_aunque_la_ia_lo_hubiera_leido_mal():
    """Sumar la diferencia arrastraba el error: 100 + (118 − 1180) daba una base negativa."""
    assert igv.aplicar_total(cp(base_gravada="100", igv="18", total="1180"), "118")["base_gravada"] == D("100")


def test_sin_base_lo_absorbe_el_importe_sin_igv():
    r = igv.aplicar_total(cp(base_gravada="0", igv="0", inafecto="50", total="50"), "80")
    assert r == {"total": D("80"), "inafecto": D("80"), "dscto_base": 0, "dscto_igv": 0}


def test_un_total_que_no_alcanza_o_no_es_numero_se_dice():
    with pytest.raises(igv.TotalImposible, match="menor"):
        igv.aplicar_total(cp(base_gravada="100", igv="18", total="118"), "10")
    with pytest.raises(igv.TotalImposible, match="número"):
        igv.aplicar_total(cp(), "abc")
    with pytest.raises(igv.TotalImposible, match="negativo"):
        igv.aplicar_total(cp(), "-5")


def test_una_nota_entera_como_descuento_sigue_entera_al_cambiar_el_total():
    r = igv.aplicar_total(nc_descuento(), "236")
    assert (r["base_gravada"], r["dscto_base"], r["dscto_igv"]) == (D("218"), D("218"), D("18"))


def test_la_compra_se_divide_por_el_destino_de_la_adquisicion():
    """Base e IGV van enteros a una de las tres parejas del registro de compras —gravadas (DG), gravadas y no
    gravadas (DGNG), no gravadas (DNG)— y las otras dos quedan en cero. El registro de compras del SIRE y la
    plantilla de CONTASIS llevan esas seis columnas: la división vive aquí una vez."""
    pareja, cero = (D("100"), D("18")), (D("0"), D("0"))
    assert igv.por_destino(cp(base_gravada="100", igv="18")) == (pareja, cero, cero)
    assert igv.por_destino(cp(base_gravada="100", igv="18", destino_igv="dgng")) == (cero, pareja, cero)
    assert igv.por_destino(cp(base_gravada="100", igv="18", destino_igv="DNG")) == (cero, cero, pareja)


def test_la_tasa_legal_es_la_que_cuadra_y_no_el_cociente():
    """Lo que declara un registro en «% IGV»: la tasa legal que cuadra con base e IGV, con la tolerancia de
    `validar`. El registro de CONTASIS validado escribe 18 aunque el IGV, redondeado ítem a ítem, dé 17.98."""
    assert igv.tasa_legal("18", "100") == D("18.00")
    assert igv.tasa_legal("9.75", "54.24") == D("18.00")        # el cociente da 17.98
    assert igv.tasa_legal("10.50", "100") == D("10.50")
    assert igv.tasa_legal("10.53", "100") == D("10.50")         # la reducida, no el cociente
    assert igv.tasa_legal("10", "100") == D("10.00")
    assert igv.tasa_legal("8", "100") == D("8.00")
    assert igv.tasa_legal("25", "100") == D("25.00")            # ninguna legal cuadra: el cociente
    assert igv.tasa_legal("0", "100") is None and igv.tasa_legal("18", "0") is None


# ── Las cuatro respuestas a «¿cuál es la tasa del IGV?» ─────────────────────────────────────────────────────────
#
# Son cuatro porque cada formato pide una cosa distinta, y lo que no había era un sitio donde se vieran juntas.
#
# **Y este bloque llegó tarde a su propio trabajo** (08-oct-2026). Existía desde antes y daba por buena la
# respuesta mala: tenía congelado que STARSOFT escribiera `17.98` donde la tasa es 18, con un docstring
# explicando que estaba bien. Sobrevivió a la corrección porque **copiaba** la regla del asiento en vez de
# llamarla —dos líneas con un comentario que decía «la guarda es la de `asiento/motor.py`»—, así que seguir en
# verde no probaba el motor: probaba la copia. Desde hoy `_las_cuatro` arma el asiento DE VERDAD, y por eso un
# cambio en `motor.py` se ve aquí. Un test que reimplementa lo que vigila no vigila nada.
#
# Lo encontró una importación real en STARSOFT, no la batería.

def _las_cuatro(igv_escrito: str, base: str) -> dict[str, object]:
    """Lo que escribe cada uno para el mismo comprobante, cada uno por la función que usa de verdad.

    El núcleo **se lee del asiento armado**, no de una cuenta repetida aquí: es la única forma de que este test
    caiga si `asiento/motor.py` cambia de función."""
    from datetime import date

    from contaperu.asiento import lineas_del_comprobante
    from contaperu.drivers.concar import tasa_igv_entera
    from contaperu.drivers.starsoft.proyeccion import con_dos_decimales
    from contaperu.pipeline import preparacion as prep
    from util import comprobante, con_imputaciones, en_secciones

    c = comprobante(tipo_cp="01", serie="F001", numero="500", fecha_emision=date(2026, 8, 11),
                    contraparte_tipo_doc="6", contraparte_doc="20131312955",
                    contraparte_nombre="PROVEEDOR DE PRUEBA SAC", moneda="PEN",
                    base_gravada=base, igv=igv_escrito, total=str(D(base) + D(igv_escrito)),
                    destino_igv="DG", cuenta_contable="634301")
    config = con_imputaciones(prep.config_aplicada(
        en_secciones({"usa_centros_costo": False, "cuentas": {"igv": "401111"}}, "concar"), "concar"))
    lineas = lineas_del_comprobante(c, config, (date(2026, 8, 1), date(2026, 8, 31)), "080001")
    de_la_linea = next(ln.tasa_igv for ln in lineas if ln.rol == "tercero")
    return {"nucleo": de_la_linea,
            "concar": tasa_igv_entera(D(igv_escrito), D(base)),
            "contasis": igv.tasa_legal(igv_escrito, base),
            "starsoft": con_dos_decimales(de_la_linea)}


@pytest.mark.parametrize("igv_escrito,base,caso", [
    ("4.58", "25.42", "la notaría de S/ 30 del archivo que STARSOFT rechazó: el cociente da 18.0173…"),
    ("7.69", "42.71", "el consumo de S/ 50.40 del mismo archivo: el cociente da 18.0051…"),
    ("0.15", "0.85", "un café de S/ 1.00, donde el redondeo pesa más: el cociente da 17.65"),
    ("9.75", "54.24", "el 17.98 de redondear ítem a ítem, el que cita la plantilla de CONTASIS"),
    ("18", "100", "y el exacto, que es el caso normal"),
])
def test_ninguna_de_las_cuatro_escribe_el_redondeo_del_emisor(igv_escrito, base, caso):
    """La tasa de un comprobante del 18 % es 18, aunque sus importes vengan redondeados al céntimo.

    El cociente `igv / base` devuelve ese redondeo convertido en porcentaje, y **cuanto más pequeño el importe,
    más se nota**: medio céntimo sobre S/ 25 son dos centésimas de punto. Esto es lo que John vio en un TXT de
    producción —`18.02` y `18.01` en el mismo archivo— el 08-oct-2026."""
    assert _las_cuatro(igv_escrito, base) == {"nucleo": "18", "concar": 18,
                                              "contasis": D("18.00"), "starsoft": "18.00"}, caso


def test_lo_que_todavia_separa_a_las_cuatro_es_el_formato_y_no_la_tasa():
    """Con una tasa reducida del 10.5 % las cuatro coinciden en la TASA y difieren en cómo la escriben.

    - **El núcleo** la lleva como texto, sin ceros de más: `10.5`. Es lo que va en `linea.tasa_igv`.
    - **CONCAR** la redondea a entero —**11**— porque su columna AO solo admite entero, y lo hace desde los
      importes del comprobante: redondear dos veces puede dar otro entero. Su plantilla describe la columna con
      «valores validos 0,10,18», así que este 11 sigue pendiente de una importación real.
    - **CONTASIS** la declara con dos decimales, que es como su plantilla pide el «porcentaje del IGV».
    - **STARSOFT** se queda con la de la línea y le pone dos decimales: es el único que no vuelve a leer el
      comprobante, y por eso era el único al que le llegaba el cociente.

    Si alguna deja de ser la que es, esto lo dice — y dice cuál."""
    assert _las_cuatro("10.53", "100") == {"nucleo": "10.5", "concar": 11,
                                           "contasis": D("10.50"), "starsoft": "10.50"}


def test_cuando_ninguna_tasa_legal_cuadra_se_escribe_el_cociente_y_no_un_18_inventado():
    """El borde que se conserva a propósito: un IGV que no es ninguna tasa legal no se maquilla.

    Ese comprobante ya lleva su `IGV_NO_CUADRA`, que bloquea la exportación salvo cuando viene de la propuesta
    del SIRE —ahí es aviso (`validar`), y entonces sí llega al archivo—. Escribir `18.00` en esa celda sería
    tapar en el archivo lo que la pantalla está diciendo."""
    assert _las_cuatro("25", "100") == {"nucleo": "25", "concar": 25,
                                        "contasis": D("25.00"), "starsoft": "25.00"}


def test_la_tolerancia_de_la_tasa_es_LA_MISMA_con_la_que_validar_acepta_un_igv():
    """No son dos umbrales: es `catalogos.TOLERANCIA_IGV`, y de ahí sale el borde exacto.

    El peor desvío al redondear un importe al céntimo es medio céntimo, así que la tolerancia (5 céntimos) cubre
    un redondeo único con holgura de 10× y el redondeo ítem a ítem hasta **diez ítems** en el peor caso
    imaginable —que todos se desvíen hacia el mismo lado—; en la práctica se cancelan entre sí.

    **Pasado ese borde se escribe el cociente, y es correcto que se escriba:** ensanchar la tolerancia para
    cubrir más redondeo haría que `validar` aceptase más descuadres, porque el número es uno solo. Quien venga a
    tocarlo lee esto antes."""
    assert cat.TOLERANCIA_IGV == D("0.05")
    # Diez ítems, cada uno desviado medio céntimo hacia arriba: el desvío es 0.05 justo, y entra.
    assert _las_cuatro("180.05", "1000")["starsoft"] == "18.00"
    # Once: 0.06, se sale. La celda dice 18.01 y el comprobante lleva su observación.
    assert _las_cuatro("198.06", "1100")["starsoft"] == "18.01"


def test_sin_igv_ninguna_se_inventa_una_tasa():
    """Una boleta sin crédito fiscal, una compra exonerada: no hay tasa que leer y ninguna supone el 18 %. CONCAR
    tuvo un 18 de respaldo hasta el 10-sep-2026 y se quitó por eso.

    STARSOFT es el único que escribe algo, `0.00`, porque sus ejemplos oficiales llevan dos decimales en todas
    las columnas numéricas incluso donde no aplican."""
    assert igv.tasa_calculada("0", D("100")) is None
    assert igv.tasa_legal("0", "100") is None
    assert _las_cuatro("0", "100") == {"nucleo": "", "concar": "", "contasis": None, "starsoft": "0.00"}


def test_editar_una_compra_no_gravada_no_pierde_el_importe_ni_lo_duplica():
    """Corregir el IGV o el total de una compra del RCE tiene que dejar el comprobante cuadrado.

    Lo no gravado de una compra vive en `valor_no_gravado` (campo 21 del RCE), no en `exonerado`/`inafecto`,
    que en ese archivo no existen. Mover importes sin mirarlo dejaba dos verdades: el campo declarado por un
    lado y el desglose por otro. Con la suma de `validar` arreglada (3.5.1) eso ya no pasa desapercibido, así
    que los dos recálculos tienen que llevar el importe al campo que el libro usa.
    """
    from contaperu.tributos import validar
    from contaperu.modelo import Libro
    compras = Libro(ruc="20131312955", razon_social="X", periodo="202608", tipo="compra")

    def cuadra(c, cambios):
        for k, v in cambios.items():
            setattr(c, k, v)
        c.__post_init__()
        validar.revisar([c], compras)
        return [o.codigo for o in c.observaciones]

    # Quitarle el IGV a una compra mixta: los 168 enteros pasan a lo NO GRAVADO, no a `inafecto`.
    mixta = cp(base_gravada="100", igv="18", valor_no_gravado="50", total="168")
    r = igv.aplicar_igv(mixta, "0")
    assert r["valor_no_gravado"] == D("168") and r["inafecto"] == 0
    assert cuadra(cp(base_gravada="100", igv="18", valor_no_gravado="50", total="168"), r) == []

    # Ponerle IGV a una no gravada la vuelve afecta y SUELTA el campo (None, no cero: un cero declarado
    # ganaría sobre el desglose que alguien escriba luego).
    r = igv.aplicar_igv(cp(valor_no_gravado="150", total="150"), "22.88")
    assert r["base_gravada"] == D("127.12") and r["valor_no_gravado"] is None
    assert cuadra(cp(valor_no_gravado="150", total="150"), r) == []

    # Corregir el TOTAL de una no gravada lo absorbe el campo 21, no la base: si cayera en `base_gravada`
    # la compra pasaría a ser gravada sin IGV y el importe se contaría dos veces.
    r = igv.aplicar_total(cp(valor_no_gravado="150", total="150"), "160")
    assert r["valor_no_gravado"] == D("160") and "base_gravada" not in r
    assert cuadra(cp(valor_no_gravado="150", total="150"), r) == []

    # Y en una mixta el total lo absorbe la base, descontando lo no gravado: 178 - 18 - 50 = 110.
    r = igv.aplicar_total(cp(base_gravada="100", igv="18", valor_no_gravado="50", total="168"), "178")
    assert r["base_gravada"] == D("110")
    # El total cuadra, que es lo de esta tanda. El IGV queda fuera de tasa (18 no es el 18 % de 110) y
    # `validar` lo dice: `aplicar_total` NO toca el IGV a propósito, porque se escribe del papel en su propia
    # celda. Lo promete su docstring desde el 11-sep-2026 y aquí queda anclado.
    assert cuadra(cp(base_gravada="100", igv="18", valor_no_gravado="50", total="168"), r) == ["IGV_NO_CUADRA"]


def clase(c, es_venta=False):
    return igv.clase_de_igv(c, es_venta)


def test_la_clase_del_igv_sale_de_los_importes_y_no_del_destino():
    """Qué le cobraron de IGV al comprobante, deducido de sus importes.

    **No es `destino_igv`**, y ese es el fallo que esto viene a cerrar: el modelo pone `DG` por defecto a TODO
    comprobante, también a una compra que no tiene IGV que destinar, así que leer el destino para responder a esta
    pregunta contesta «gravada» a media contabilidad. Lo sabía `drivers/starsoft/proyeccion.destino_de` desde la 2.x,
    dentro de un driver; aquí sube al núcleo, que es donde puede mirarlo también la pantalla.
    """
    # Una compra sin IGV con el destino por defecto: la clase NO se deja engañar.
    no_gravada = cp(valor_no_gravado="150", total="150", destino_igv="DG")
    assert no_gravada.destino_igv == "DG" and clase(no_gravada) == "no_gravada"

    assert clase(cp(base_gravada="100", igv="18", total="118")) == "gravada"
    assert clase(cp(base_gravada="100", igv="18", valor_no_gravado="50", total="168")) == "mixto"
    # La importación se reconoce por la DUA, no por un importe, y solo existe en compras.
    assert clase(cp(base_gravada="100", igv="18", total="118", anio_dua="2026")) == "importacion"
    assert clase(cp(base_gravada="100", igv="18", total="118", cod_dep_aduanera="235")) == "importacion"


def test_los_dos_libros_no_dan_las_mismas_clases():
    """El RVIE separa exonerado (19) de inafecto (20); el RCE tiene UNA columna que no dice cuál de los dos es.

    Por eso en compras se dice «no gravada» y no se inventa el desglose, y por eso las dos tablas del catálogo están
    separadas. Con el mismo importe en `inafecto`, una venta dice «inafecto» y una compra, «no gravada».
    """
    from contaperu import catalogos as cat
    assert clase(cp(inafecto="150", total="150"), es_venta=True) == "inafecto"
    assert clase(cp(inafecto="150", total="150")) == "no_gravada"
    assert clase(cp(exonerado="50", total="50"), es_venta=True) == "exonerado"
    # «Importación» solo existe en compras: una venta con DUA es una exportación, y esa tiene su propia columna.
    assert clase(cp(exportacion="100", total="100", anio_dua="2026"), es_venta=True) == "exportacion"
    # Y cada clase que se devuelve tiene su nombre en castellano, sin que la pantalla lo escriba a mano.
    for c, es_venta, tabla in ((cp(base_gravada="100", igv="18", total="118"), False, cat.CLASES_IGV_COMPRA),
                               (cp(inafecto="150", total="150"), True, cat.CLASES_IGV_VENTA)):
        assert clase(c, es_venta) in tabla


def test_un_comprobante_sin_importes_no_tiene_clase():
    """Así declara SUNAT lo que se da de baja: todo en cero. No es gravado ni no gravado, y decir cualquiera de las
    dos cosas sería inventar — la pantalla caía en «inafecto» por descarte y lo enseñaba con `0.00` al lado."""
    assert clase(cp(total="0")) == "" and clase(cp(total="0"), es_venta=True) == ""


def test_poner_el_importe_no_gravado_recalcula_la_base_sin_tocar_el_total():
    """El (+) del portal: la persona escribe UN importe y el motor recoloca el resto.

    Existe porque una compra mixta no se podía corregir: el formulario ofrecía `exonerado` e `inafecto`, que en el
    RCE no existen, y escondía `valor_no_gravado`, que es el único que sí.
    """
    from contaperu.tributos import validar
    from contaperu.modelo import Libro
    compras = Libro(ruc="20131312955", razon_social="X", periodo="202608", tipo="compra")   # `cp()` emite en agosto

    r = igv.aplicar_no_gravado(cp(base_gravada="150", igv="18", total="168"), "50")
    assert r == {"valor_no_gravado": D("50"), "base_gravada": D("100")}
    # Y el comprobante resultante cuadra y pasa a ser mixto.
    c = cp(base_gravada="100", igv="18", valor_no_gravado="50", total="168")
    validar.revisar([c], compras)
    assert [o.codigo for o in c.observaciones] == [] and clase(c) == "mixto"

    # Cero SUELTA el campo declarado (None, no cero): un cero declarado ganaría sobre el desglose.
    assert igv.aplicar_no_gravado(cp(base_gravada="100", igv="18", valor_no_gravado="50", total="168"),
                                  "0")["valor_no_gravado"] is None
    # En ventas se elige la columna, porque el RVIE sí las separa.
    assert igv.aplicar_no_gravado(cp(base_gravada="150", igv="18", total="168"), "50", "exonerado") == {
        "exonerado": D("50"), "base_gravada": D("100")}
    # Lo que no cabe, no entra.
    with pytest.raises(igv.NoGravadoImposible):
        igv.aplicar_no_gravado(cp(base_gravada="100", igv="18", total="118"), "500")
    with pytest.raises(igv.NoGravadoImposible):
        igv.aplicar_no_gravado(cp(total="118"), "50", "base_gravada")
