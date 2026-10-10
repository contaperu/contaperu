"""La forma de la tesorería, contrastada contra nueve extractos reales de producción.

Los archivos no están aquí —son de una empresa y este repositorio es público: viven en `privado/extractos/`, que
`.gitignore` bloquea—, pero **las cifras de los dos primeros movimientos del extracto de BBVA de agosto de 2026 sí
están**, y son el mejor test que esta pieza puede tener: si la cadena de saldos no reproduce el saldo que el banco
imprimió, algo está mal aquí y no en el banco.

Lo que estos tests NO prueban, y conviene decirlo: no hay lector de ningún banco todavía. Se prueba la forma, la
normalización del signo, la deduplicación y el cuadre. El parser de cada banco entra con su archivo delante.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from contaperu import tesoreria as t

# De `BBVA SOLES.pdf`, agosto de 2026: el saldo anterior y los dos primeros movimientos, con su saldo corrido tal
# como los imprime el banco. El CCI es el que el propio extracto publica al pie, y su `011` es la entidad.
SALDO_ANTERIOR = "1069946.05"
CCI_BBVA = "011 307 000100028777 69"


def cuenta(**extra) -> t.CuentaBancaria:
    datos = {"id": "bbva-soles", "banco": "BBVA", "numero": "0100028777", "cci": CCI_BBVA,
             "moneda": "PEN", "cuenta_contable": "10411100"}
    return t.CuentaBancaria(**{**datos, **extra})


def mov(**extra) -> t.Movimiento:
    datos = {"cuenta": "bbva-soles", "fecha": "2026-08-03", "descripcion": "ABONO POR DEVOLUCION - CCE",
             "importe": "921.75", "sentido": "abono", "moneda": "PEN"}
    return t.Movimiento(**{**datos, **extra})


# ── La cuenta, que es un argumento y no una tabla ──────────────────────────

def test_el_cci_se_normaliza_y_dice_su_banco():
    """Cada banco lo imprime a su manera —BBVA con espacios, Scotiabank con guiones— y es el mismo número."""
    c = cuenta()
    assert c.cci == "01130700010002877769" and len(c.cci) == t.LARGO_CCI
    assert c.codigo_de_banco == "011"
    assert t.normalizar_cci("009-202-000003675511-34") == "00920200000367551134"
    assert t.banco_del_cci("009-202-000003675511-34") == "009"
    # Un CCI que no tiene la forma no se adivina: no hay banco, y se dice con vacío.
    assert t.banco_del_cci("123") == ""


def test_un_cci_corto_no_se_rellena_con_ceros():
    """Es la tentación evidente y sería un error: un CCI corto es un dato mal copiado, no uno al que le faltan
    ceros. Se para y se dice cuántos dígitos tiene."""
    with pytest.raises(t.CuentaInvalida) as e:
        cuenta(cci="0113070001")
    assert "20 dígitos" in str(e.value) and "tiene 10" in str(e.value)


def test_la_cuenta_contable_la_pone_el_contribuyente_y_el_motor_no_la_deriva():
    """La 104 es de la empresa, igual que la cuenta de un gasto. El motor no la supone ni cuando conoce el banco."""
    assert cuenta().cuenta_contable == "10411100"
    # Sin declararla, no aparece ninguna: el motor no rellena el hueco.
    assert cuenta(cuenta_contable="").cuenta_contable == ""


def test_dos_cuentas_con_el_mismo_id_no_pasan():
    """El `id` es la llave con la que un movimiento nombra su cuenta: repetirlo rompe el casado en silencio."""
    with pytest.raises(t.CuentaInvalida) as e:
        t.leer([cuenta().a_dict(), cuenta(moneda="USD").a_dict()])
    assert "bbva-soles" in str(e.value)


def test_sin_cuentas_declaradas_no_pasa_nada():
    """Es un argumento opcional, y su ausencia no cambia ningún comportamiento."""
    assert t.leer(None) == () and t.leer([]) == ()


def test_una_clave_que_no_es_de_una_cuenta_se_dice_por_su_nombre():
    with pytest.raises(t.CuentaInvalida) as e:
        t.CuentaBancaria.de_dict({**cuenta().a_dict(), "titular": "C MEJIA"})
    assert "titular" in str(e.value)


# ── El movimiento, y el signo que cada banco escribe a su manera ───────────

def test_el_importe_va_siempre_positivo_y_el_signo_lo_dice_el_sentido():
    """BBVA trae una columna con el importe negativo cuando es cargo; Scotiabank y BanBif traen dos columnas. El
    modelo normaliza a una sola forma, que es la que ya usa la línea de diario con su `debe_haber`."""
    cargo = mov(importe="4960.00", sentido="cargo", descripcion="C/ PROVEEDO.0803001")
    assert cargo.importe == Decimal("4960.00") and cargo.es_cargo
    # Y un importe con signo NO se rechaza: se normaliza. `modelo.monto` devuelve el valor absoluto, que es lo que
    # un lector de BBVA necesita — mira el signo de la columna para poner `sentido` y pasa el importe tal cual.
    assert mov(importe="-4960.00", sentido="cargo").importe == Decimal("4960.00")


def test_un_movimiento_sin_fecha_no_pasa_porque_el_nucleo_no_tiene_reloj():
    """Las líneas de un extracto traen día y mes; el año está en la cabecera y lo baja quien lee el archivo. Aquí
    no se puede adivinar: el núcleo no mira el reloj (`tests/test_frontera.py`)."""
    with pytest.raises(t.MovimientoInvalido) as e:
        mov(fecha="")
    assert "el año lo baja de la cabecera" in str(e.value)


def test_la_fecha_valor_cae_a_la_de_operacion_cuando_no_viene():
    """Los tres bancos la dan y casi siempre coincide; cuando no viene, suponer la de operación es lo que hace
    cualquiera y es mejor que dejarla vacía."""
    assert mov().fecha_valor == date(2026, 8, 3)
    assert mov(fecha_valor="2026-07-31").fecha_valor == date(2026, 7, 31)


def test_el_itf_es_un_dato_del_banco_y_vacio_no_es_cero():
    """BBVA lo trae en una columna de la línea; Scotiabank lo asienta como un movimiento propio. Las dos formas
    caben, y la diferencia entre «el banco no lo dice» y «el banco dice cero» se conserva."""
    assert mov(itf="0.20").itf == Decimal("0.20")
    assert mov().itf is None
    assert mov(itf="0").itf == Decimal("0.00")


def test_una_relectura_con_solape_no_duplica():
    """El criterio de salida del hito D2. Se baja el extracto dos veces y los repetidos se dicen, no se tiran en
    silencio: lo que el que integra necesita saber es cuántos se descartaron."""
    a = mov(referencia="14051")
    b = mov(referencia="14052", importe="4960.00", sentido="cargo")
    nuevos, repetidos = t.sin_duplicados([a, b, mov(referencia="14051")])
    assert len(nuevos) == 2 and len(repetidos) == 1
    assert repetidos[0].referencia == "14051"


def test_sin_referencia_la_clave_se_cae_a_lo_que_siempre_hay():
    """BanBif no da número de operación. La clave usa entonces cuenta, fecha, sentido, importe y descripción — y
    eso **puede colisionar a propósito**: dos comisiones idénticas el mismo día son dos movimientos y una clave."""
    sin_ref = mov(referencia="")
    assert sin_ref.clave == t.clave_de("bbva-soles", "", date(2026, 8, 3), "abono", Decimal("921.75"),
                                       "ABONO POR DEVOLUCION - CCE")
    nuevos, repetidos = t.sin_duplicados([sin_ref, mov(referencia="")])
    assert len(nuevos) == 1 and len(repetidos) == 1


# ── El cuadre, que es lo que hace verificable a un lector ──────────────────

def test_la_cadena_de_saldos_reproduce_la_del_banco():
    """Las cifras son las del extracto real de BBVA de agosto de 2026: 1 069 946,05 + 921,75 − 4 960,00."""
    movs = [mov(referencia="14051", saldo="1070867.80"),
            mov(referencia="14052", importe="4960.00", sentido="cargo", itf="0.20",
                descripcion="C/ PROVEEDO.0803001", saldo="1065907.60")]
    r = t.cuadra(movs, saldo_inicial=SALDO_ANTERIOR)
    assert r.cuadra, str(r)
    assert r.saldo_final == Decimal("1065907.60")
    assert (r.cargos, r.abonos) == (Decimal("4960.00"), Decimal("921.75"))


def test_el_itf_entra_en_la_cadena_aunque_no_este_en_la_columna_del_importe():
    """Lo enseñó el archivo real y es el tipo de cosa que un lector nuevo descubre tarde: en BBVA el ITF va en su
    propia columna y el saldo corrido lo resta igual. Sin restarlo, la segunda fila del mes ya no cuadra."""
    sin_itf = t.cuadra([mov(importe="4960.00", sentido="cargo", saldo="1065907.60")],
                       saldo_inicial="1070867.80")
    assert not sin_itf.cuadra and sin_itf.diferencia == Decimal("-0.20")
    con_itf = t.cuadra([mov(importe="4960.00", sentido="cargo", itf="0.20", saldo="1065907.60")],
                       saldo_inicial="1070867.80")
    assert con_itf.cuadra


def test_una_linea_mal_leida_se_delata_en_el_acto_y_dice_cual():
    """Es para lo que existe esta función. Un lector de PDF se equivoca callado —se salta una línea, pega dos
    columnas— y el saldo corrido lo descubre sin que haga falta un humano."""
    movs = [mov(saldo="1070867.80"), mov(importe="4960.00", sentido="cargo", saldo="999999.99")]
    r = t.cuadra(movs, saldo_inicial=SALDO_ANTERIOR)
    assert not r.cuadra and r.rompe_en == 2
    assert "se rompe en el movimiento 2" in str(r)
    with pytest.raises(t.ExtractoNoCuadra):
        t.exigir(movs, saldo_inicial=SALDO_ANTERIOR)


def test_un_movimiento_sin_saldo_propio_no_rompe_nada():
    """Hay extractos que solo dan el saldo al final de cada día. Se le aplica su importe y se sigue."""
    r = t.cuadra([mov(), mov(importe="4960.00", sentido="cargo")], saldo_inicial=SALDO_ANTERIOR)
    assert r.cuadra and r.saldo_final == Decimal("1065907.80")


def test_el_saldo_final_declarado_se_comprueba_y_el_ausente_no_se_inventa():
    r = t.cuadra([mov()], saldo_inicial=SALDO_ANTERIOR, saldo_final="1070867.80")
    assert r.cuadra
    malo = t.cuadra([mov()], saldo_inicial=SALDO_ANTERIOR, saldo_final="1.00")
    assert not malo.cuadra and malo.rompe_en == 1
    assert t.cuadra([mov()], saldo_inicial=SALDO_ANTERIOR, saldo_final=None).cuadra


# ── La constancia, que vale para cualquier pago ────────────────────────────

def constancia(**extra) -> t.Constancia:
    datos = {"numero": "00012345678", "fecha": "2026-08-14", "importe": "4711.00", "moneda": "PEN",
             "medio_pago": "001", "cuenta_origen": "bbva-soles"}
    return t.Constancia(**{**datos, **extra})


@pytest.mark.parametrize("clase,datos", [
    ("comprobante", {"tipo_cp": "01", "serie": "F001", "numero": "123", "contraparte_doc": "20602222226"}),
    ("tributo", {"codigo": "1000", "periodo": "202607"}),
    ("cuenta_propia", {"cuenta": "bbva-dolares"}),
    ("libre", {"texto": "Reintegro de caja chica de obra"}),
])
def test_una_constancia_cancela_cualquier_cosa(clase, datos):
    """Es lo que John pidió: «todo tipo de pagos, porque puede llamar a otra cuenta que no necesariamente
    proveedor». Las cuatro clases cubren el depósito de detracción, el pago de tributos, el traspaso propio y la
    caja chica **sin que el estándar enumere propósitos de pago**, que es la trampa de un modelo de tesorería."""
    c = constancia(referencias=[{"clase": clase, "datos": datos}])
    assert c.referencias[0].clase == clase
    assert c.a_dict()["referencias"][0]["datos"] == {k: str(v) for k, v in datos.items()}


def test_una_referencia_no_lleva_lo_que_no_es_de_su_clase():
    with pytest.raises(t.ConstanciaInvalida) as e:
        t.Referencia(clase="tributo", datos={"codigo": "1000", "serie": "F001"})
    assert "serie" in str(e.value) and "codigo, periodo" in str(e.value)


def test_lo_que_ninguna_referencia_reclama_se_reporta_y_no_se_cierra():
    """Un cargo lleva el ITF dentro, y un pago puede cancelar algo que el papel no nombra. El motor lo dice y no
    decide qué es: eso es del contador, por la imputación."""
    c = constancia(importe="4721.50", referencias=[
        {"clase": "comprobante", "datos": {"tipo_cp": "01", "serie": "F001", "numero": "123"},
         "importe": "4711.00"}])
    assert c.repartido == Decimal("4711.00")
    assert c.sin_atribuir == Decimal("10.50")
    # Sin importes por referencia no hay reparto que comprobar: la referencia vale por el total.
    assert constancia(referencias=[{"clase": "libre", "datos": {"texto": "x"}}]).sin_atribuir == Decimal("0.00")


def test_una_constancia_sin_numero_o_sin_fecha_no_pasa():
    """El número es lo único que no se puede inventar, y la fecha del pago no es la de la factura: se paga días
    después, a veces el mes siguiente."""
    with pytest.raises(t.ConstanciaInvalida):
        constancia(numero="")
    with pytest.raises(t.ConstanciaInvalida) as e:
        constancia(fecha="")
    assert "no es el de la factura" in str(e.value)


def test_la_constancia_apunta_a_la_cuenta_por_su_id_y_no_a_una_cuenta_contable():
    """Es la decisión que impide que el motor adivine un 104: la constancia nombra la cuenta declarada, y la
    contable sale de ahí."""
    c = constancia()
    declaradas = {x.id: x for x in t.leer([cuenta().a_dict()])}
    assert c.cuenta_origen in declaradas
    assert declaradas[c.cuenta_origen].cuenta_contable == "10411100"


# ── Y la frontera, dicha en un test ────────────────────────────────────────

def test_la_tesoreria_no_sabe_leer_ningun_banco_todavia():
    """A propósito, y el día que deje de ser cierto este test cae y hay que decirlo en el CHANGELOG. La forma
    salió de nueve extractos reales, pero un parser entra con su archivo delante y su fixture anonimizado."""
    assert not [n for n in t.__all__ if "leer_extracto" in n or "bbva" in n.lower()]
    # Y tampoco concilia: casar un pago con lo que cancela es D3 y necesita dos archivos.
    assert not [n for n in t.__all__ if "conciliar" in n]
