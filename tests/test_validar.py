"""Reglas de negocio deterministas (validar.py) y catálogos."""
from decimal import Decimal

import pytest

from contaperu import catalogos as cat, validar
from contaperu.modelo import Comprobante, Libro

VENTAS = Libro(ruc="20131312955", razon_social="X", periodo="202601", tipo="venta")
COMPRAS = Libro(ruc="20131312955", razon_social="X", periodo="202601", tipo="compra")


def cp(**kw) -> Comprobante:
    base = dict(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-01-15",
                contraparte_doc="20604444447", contraparte_nombre="CLIENTE SAC",
                base_gravada="100", igv="18", total="118")
    base.update(kw)
    return Comprobante(**base)


def codigos(c: Comprobante, libro: Libro = VENTAS) -> list[str]:
    validar.revisar([c], libro)
    return [o.codigo for o in c.observaciones]


@pytest.mark.parametrize("ruc,ok", [
    ("20131312955", True), ("10601111115", True), ("20604444447", True), ("20603333331", True),
    ("20609999999", False), ("20601234567", False), ("2013131295", False), ("30131312955", False), ("", False),
])
def test_ruc_modulo_11(ruc, ok):
    assert cat.ruc_valido(ruc) is ok


def test_comprobante_limpio():
    c = cp()
    assert codigos(c) == [] and c.estado == "ok"


def test_igv_no_cuadra_y_tasa_reducida():
    assert codigos(cp(igv="20", total="120")) == ["IGV_NO_CUADRA"]
    c = cp(igv="10", total="110")                       # 10 % restaurantes
    assert codigos(c) == ["IGV_TASA_REDUCIDA"] and c.estado == "observada" and not c.tiene_errores
    assert codigos(cp(igv="18.04", total="118.04")) == []   # tolerancia ±0.05


def test_total_no_cuadra_y_anticipo():
    assert codigos(cp(total="200")) == ["TOTAL_NO_CUADRA"]
    c = cp(total="98", datos_originales={"anticipo": "20"})
    assert codigos(c) == ["ANTICIPO"]
    assert codigos(cp(exonerado="50", total="168")) == []


def test_fechas():
    assert codigos(cp(fecha_emision="2026-02-01")) == ["FECHA_POSTERIOR"]
    # (el estado de anotación 8/9 era del PLE; murió con él el 30-ago-2026)
    assert codigos(cp(fecha_emision="2025-11-30")) == ["PERIODO_ANTERIOR"]
    assert codigos(cp(fecha_emision="2024-06-30")) == ["PERIODO_ANTERIOR"]
    assert codigos(cp(fecha_emision=None)) == ["FECHA_FALTA"]


def test_compras_el_mes_anterior_no_es_observacion():
    """Ley 29215, art. 2: la compra se anota en el mes de emisión o en los 12 siguientes. Dentro del
    plazo no hay nada que observar (John, 12-sep-2026: el aviso pintaba de ámbar un recibo de luz del
    mes pasado); fuera de él, un aviso que no bloquea. En ventas no hay plazo: sigue PERIODO_ANTERIOR."""
    c = cp(fecha_emision="2025-11-30")
    assert codigos(c, COMPRAS) == [] and c.estado == "ok"
    assert codigos(cp(fecha_emision="2025-01-31"), COMPRAS) == []              # justo 12 meses: dentro
    c = cp(fecha_emision="2024-12-31")                                          # 13: fuera
    assert codigos(c, COMPRAS) == ["CREDITO_FISCAL_FUERA_DE_PLAZO"] and not c.tiene_errores
    assert codigos(cp(fecha_emision="2024-06-30"), COMPRAS) == ["CREDITO_FISCAL_FUERA_DE_PLAZO"]
    # el caso de la pantalla: recibo de luz emitido el mes pasado, que vence en este
    recibo = cp(tipo_cp="14", serie="", numero="123", contraparte_doc="20603333331",
                fecha_emision="2025-12-29", fecha_vencimiento="2026-01-10")
    assert codigos(recibo, COMPRAS) == []
    # en un documento aduanero la referencia es el pago del impuesto («o del pago del Impuesto»)
    dua = cp(tipo_cp="50", serie="118", numero="1", anio_dua="2024",
             fecha_emision="2024-12-15", fecha_vencimiento="2025-01-20")
    assert codigos(dua, COMPRAS) == []
    # en ventas no hay plazo: el código es otro y no depende de la antigüedad
    assert codigos(cp(fecha_emision="2024-06-30"), VENTAS) == ["PERIODO_ANTERIOR"]


def test_contraparte():
    assert codigos(cp(contraparte_doc="20609999999")) == ["RUC_INVALIDO"]
    assert codigos(cp(contraparte_doc="")) == ["CONTRAPARTE_FALTA"]
    assert codigos(cp(tipo_cp="03", serie="B001", contraparte_doc="", contraparte_nombre="")) == []
    assert codigos(cp(tipo_cp="03", serie="B001", contraparte_doc="", base_gravada="1000", igv="180", total="1180")) == ["BOLETA_SIN_DOC"]
    assert codigos(cp(contraparte_tipo_doc="1", contraparte_doc="1234567")) == ["DNI_INVALIDO"]
    assert codigos(cp(contraparte_nombre="")) == ["NOMBRE_FALTA"]


def test_moneda_y_tc():
    assert codigos(cp(moneda="USD")) == ["TC_FALTA"]
    assert codigos(cp(moneda="USD", tipo_cambio="3.75")) == []
    assert codigos(cp(moneda="S/")) == ["MONEDA_INVALIDA"]


def test_notas():
    assert codigos(cp(tipo_cp="07", serie="FC01")) == ["NOTA_SIN_REFERENCIA", "NOTA_SIN_FECHA_REF"]
    assert codigos(cp(tipo_cp="07", serie="FC01", ref_tipo_cp="01", ref_serie="F001", ref_numero="9", ref_fecha="2026-01-02")) == []


def nota(**kw) -> Comprobante:
    """Una nota con su referencia completa, para que lo único que quede por mirar sea el motivo."""
    base = dict(tipo_cp="07", serie="FC01", ref_tipo_cp="01", ref_serie="F001", ref_numero="9",
                ref_fecha="2026-01-02")
    return cp(**{**base, **kw})


def test_el_motivo_de_una_nota_se_mide_contra_el_catalogo_que_le_toca():
    """Son dos catálogos distintos, así que el mismo código puede valer en uno y no en el otro: el `09` es
    «disminución en el valor» en una nota de crédito y NO EXISTE entre los de débito, que solo tiene tres —mora,
    aumento de valor y penalidades—."""
    assert codigos(nota(tipo_nota="09")) == []
    assert codigos(nota(tipo_cp="08", tipo_nota="03")) == []            # penalidades, del Catálogo 10
    assert codigos(nota(tipo_cp="08", tipo_nota="09")) == ["TIPO_NOTA_DESCONOCIDO"]


def test_un_motivo_que_sunat_no_tiene_avisa_y_no_bloquea():
    """Aviso, y el valor se respeta, igual que el medio de pago: no cambia ningún asiento ni ningún importe, y SUNAT
    amplía estas tablas —al Catálogo 09 le añadió cuatro códigos en 2020—, así que un código que este motor todavía
    no conoce no puede impedirle a nadie cerrar su mes."""
    c = nota(tipo_nota="99")
    assert codigos(c) == ["TIPO_NOTA_DESCONOCIDO"]
    assert [o.nivel for o in c.observaciones] == ["aviso"]
    assert c.tipo_nota == "99" and not c.tiene_errores                  # el valor se respeta y no bloquea


def test_una_nota_sin_motivo_no_es_un_defecto():
    """**No existe `TIPO_NOTA_FALTA`, y es a propósito.** La norma dice que ese campo «no es considerado para la
    construcción del archivo de texto», y el propio TXT que este motor genera lo manda vacío: avisar de su ausencia
    observaría el mes entero por un dato que el archivo no pide."""
    assert codigos(nota(tipo_nota="")) == []
    # Y no existe como código: `PEDIR_A` es la lista cerrada de todo lo que el motor puede observar, y un `ast.walk`
    # sobre `validar.py` comprueba que no falte ninguno (`test_diagnosticar.py`). Si alguien añadiera el aviso,
    # tendría que aparecer ahí, y esto se pondría rojo.
    from contaperu.pipeline.diagnostico import PEDIR_A
    assert "TIPO_NOTA_FALTA" not in PEDIR_A


def test_solo_una_nota_lleva_motivo():
    """Una factura con motivo de nota es un dato mal puesto: se avisa, no se borra."""
    c = cp(tipo_cp="01", tipo_nota="09")
    assert codigos(c) == ["TIPO_NOTA_NO_APLICA"]
    assert c.tipo_nota == "09"
    # Y el 87 y el 88 SÍ llevan motivo, que es el agujero que cierra `catalogos.motivos_de_nota`: con `TIPOS_NOTA`
    # —que es `("07", "08")`— se habrían quedado fuera en silencio y su código se avisaría como desconocido siempre.
    assert codigos(nota(tipo_cp="87", tipo_nota="09")) == []
    assert codigos(nota(tipo_cp="88", tipo_nota="01")) == []


def test_reglas_de_compras():
    recibo = cp(tipo_cp="14", serie="", numero="123", contraparte_doc="20603333331", fecha_vencimiento=None)
    assert codigos(recibo, COMPRAS) == ["VENCIMIENTO_FALTA"]
    recibo.fecha_vencimiento = "2026-02-10"
    assert codigos(recibo, COMPRAS) == []
    assert codigos(recibo, VENTAS) == []                  # en ventas no aplica
    assert codigos(cp(tipo_cp="50", serie="118", numero="1", fecha_vencimiento="2026-01-20"), COMPRAS) == ["ANIO_DUA_FALTA"]


def test_confianza_ia():
    # La confianza NO genera observacion (el contador, 29-ago-2026): el semaforo por fila y
    # el filtro "Baja confianza" del portal la muestran leyendo `confianza` directo.
    assert codigos(cp(origen="vision", confianza="0.60")) == []
    assert codigos(cp(origen="pdf_texto", confianza="0.80")) == []
    assert codigos(cp(origen="pdf_texto", confianza="0.95")) == []


def test_duplicados_en_el_lote_y_contra_periodos_anteriores():
    a, b, c = cp(numero="7"), cp(numero="0007"), cp(numero="8")
    validar.revisar([a, b, c], VENTAS, claves_previas={("01", "F001", "8", "20604444447")})
    assert (a.estado, b.estado, c.estado) == ("ok", "duplicada", "duplicada")
    assert b.observaciones[0].codigo == "DUPLICADO" and c.observaciones[0].codigo == "DUPLICADO_PERIODO_ANTERIOR"
    # una fila excluida no cuenta como duplicada ni bloquea a la otra
    a.excluida = True
    validar.revisar([a, b], VENTAS)
    assert b.estado == "ok"


def test_revisar_es_idempotente():
    c = cp(igv="20", total="120")
    validar.revisar([c], VENTAS)
    validar.revisar([c], VENTAS)
    assert [o.codigo for o in c.observaciones] == ["IGV_NO_CUADRA"] and c.estado == "observada"
    c.igv, c.total = Decimal("18.00"), Decimal("118.00")
    validar.revisar([c], VENTAS)
    assert c.observaciones == [] and c.estado == "ok"


def test_compras_boleta_y_aviso_700_solo_en_ventas():
    boleta = cp(tipo_cp="03", serie="B001", contraparte_doc="", contraparte_nombre="", base_gravada="1000", igv="180", total="1180")
    assert codigos(boleta, VENTAS) == ["BOLETA_SIN_DOC"]
    assert codigos(boleta, COMPRAS) == ["COMPRA_BOLETA"]
    boleta.destino_igv = "DNG"
    assert codigos(boleta, COMPRAS) == []
