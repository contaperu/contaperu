"""La forma de la tesorería, sacada de nueve extractos reales de producción.

Los archivos no están aquí —son de una empresa y este repositorio es público: viven en `privado/extractos/`, que
`.gitignore` bloquea—. **Y las cifras de este fichero son inventadas a propósito**, que es lo que la regla 6 exige
y lo que hasta la 9.0.1 no se cumplió: llevaba el CCI, el número de cuenta y el saldo de una cuenta real, más dos
movimientos con sus importes. Un CCI con su número de cuenta es la coordenada para mandarle dinero a esa cuenta, y
un saldo es la posición de caja de la empresa. Nada de eso vuelve aquí.

**Lo que el test prueba no son las cifras, es la aritmética**, y con números inventados se prueba igual: si la
cadena de saldos no reproduce el saldo de la última línea, un lector está leyendo mal. Por eso los números de aquí
son redondos y encadenan a mano —1 000,00 + 500,00 − 200,00 − 0,20 de ITF = 1 299,80—, que además hace el test
legible. Los que vinieron del archivo real y no se pueden escribir se comprobaron en local, de lectura, una vez.

Los **códigos de banco sí son los de verdad** (`011` BBVA, `009` Scotiabank): son norma publicada, no el dato de
nadie, y son justo lo que el test comprueba. Lo que se inventa es la oficina, la cuenta y los dígitos de control
—con el molde del RUC `20601234567`, seguro por no poder ser de ninguna empresa—.

Lo que estos tests NO prueban, y conviene decirlo: no hay lector de ningún banco todavía. Se prueba la forma, la
normalización del signo, la deduplicación y el cuadre. El parser de cada banco entra con su archivo delante.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from contaperu import tesoreria as t

# Inventados, y con la forma del CCI del Perú: 3 de entidad + 3 de oficina + 12 de cuenta + 2 de control. El `011`
# es BBVA de verdad —norma publicada— y el resto no puede ser de nadie: oficina `999` y una cuenta de ceros.
SALDO_ANTERIOR = "1000.00"
CCI_BBVA = "011 999 000000000001 00"
CCI_SCOTIABANK = "009-999-000000000002-00"


def cuenta(**extra) -> t.CuentaBancaria:
    datos = {"id": "bbva-soles", "banco": "BBVA", "numero": "9999999999", "cci": CCI_BBVA,
             "moneda": "PEN", "cuenta_contable": "10411100"}
    return t.CuentaBancaria(**{**datos, **extra})


def mov(**extra) -> t.Movimiento:
    datos = {"cuenta": "bbva-soles", "fecha": "2026-08-03", "descripcion": "ABONO POR TRANSFERENCIA",
             "importe": "500.00", "sentido": "abono", "moneda": "PEN"}
    return t.Movimiento(**{**datos, **extra})


# ── La cuenta, que es un argumento y no una tabla ──────────────────────────

def test_el_cci_se_normaliza_y_dice_su_banco():
    """Cada banco lo imprime a su manera —BBVA con espacios, Scotiabank con guiones— y es el mismo número."""
    c = cuenta()
    assert c.cci == "01199900000000000100" and len(c.cci) == t.LARGO_CCI
    assert c.codigo_de_banco == "011"
    assert t.normalizar_cci(CCI_SCOTIABANK) == "00999900000000000200"
    assert t.banco_del_cci(CCI_SCOTIABANK) == "009"
    # Un CCI que no tiene la forma no se adivina: no hay banco, y se dice con vacío.
    assert t.banco_del_cci("123") == ""


def test_un_cci_corto_no_se_rellena_con_ceros():
    """Es la tentación evidente y sería un error: un CCI corto es un dato mal copiado, no uno al que le faltan
    ceros. Se para y se dice cuántos dígitos tiene."""
    with pytest.raises(t.CuentaInvalida) as e:
        cuenta(cci="0119990000")
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
        t.CuentaBancaria.de_dict({**cuenta().a_dict(), "titular": "CONTRIBUYENTE DE EJEMPLO"})
    assert "titular" in str(e.value)


# ── El movimiento, y el signo que cada banco escribe a su manera ───────────

def test_el_importe_va_siempre_positivo_y_el_signo_lo_dice_el_sentido():
    """BBVA trae una columna con el importe negativo cuando es cargo; Scotiabank y BanBif traen dos columnas. El
    modelo normaliza a una sola forma, que es la que ya usa la línea de diario con su `debe_haber`."""
    cargo = mov(importe="200.00", sentido="cargo", descripcion="CARGO POR TRANSFERENCIA")
    assert cargo.importe == Decimal("200.00") and cargo.es_cargo
    # Y un importe con signo NO se rechaza: se normaliza. `modelo.monto` devuelve el valor absoluto, que es lo que
    # un lector de BBVA necesita — mira el signo de la columna para poner `sentido` y pasa el importe tal cual.
    assert mov(importe="-200.00", sentido="cargo").importe == Decimal("200.00")


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
    a = mov(referencia="000001")
    b = mov(referencia="000002", importe="200.00", sentido="cargo")
    nuevos, repetidos = t.sin_duplicados([a, b, mov(referencia="000001")])
    assert len(nuevos) == 2 and len(repetidos) == 1
    assert repetidos[0].referencia == "000001"


def test_sin_referencia_la_clave_se_cae_a_lo_que_siempre_hay():
    """BanBif no da número de operación. La clave usa entonces cuenta, fecha, sentido, importe y descripción — y
    eso **puede colisionar a propósito**: dos comisiones idénticas el mismo día son dos movimientos y una clave."""
    sin_ref = mov(referencia="")
    assert sin_ref.clave == t.clave_de("bbva-soles", "", date(2026, 8, 3), "abono", Decimal("500.00"),
                                       "ABONO POR TRANSFERENCIA")
    nuevos, repetidos = t.sin_duplicados([sin_ref, mov(referencia="")])
    assert len(nuevos) == 1 and len(repetidos) == 1


def test_el_abono_entra_y_el_cargo_sale_con_las_palabras_de_la_nic_7():
    """El cambio de perspectiva, que es la trampa de todo esto y por eso tiene su test.

    El banco escribe `abono` porque en SUS libros tu depósito es un pasivo que le crece. En los TUYOS esa misma
    plata entra a un activo, así que un abono es una **entrada** y va al debe. Quien lo lea al revés invierte el
    asiento entero sin que falle nada."""
    assert mov(sentido="abono").efecto == t.ENTRADA
    assert mov(sentido="cargo").efecto == t.SALIDA
    # Derivado y no almacenado: no hay forma de que el indicador y el efecto discrepen.
    assert "efecto" not in mov().a_dict()


def test_un_movimiento_nunca_es_una_transferencia():
    """La decisión que sostiene el modelo. El catálogo tiene tres efectos porque la NIC 7 §9 excluye de los flujos
    los traspasos entre partidas de efectivo —hay que poder nombrarlo para dejarlo fuera—, pero **una línea sola no
    puede saber que es la mitad de un traspaso**: eso es una afirmación sobre un par, y el extracto no la hace.

    Se declara (una constancia con una referencia `cuenta_propia`) o se propone (`conciliar`, que nunca confirma).
    Si algún día esto devolviera `transferencia`, un lector de un extracto estaría afirmando lo que no ha visto."""
    assert t.EFECTOS_DE_UN_MOVIMIENTO == (t.ENTRADA, t.SALIDA)
    assert all(mov(sentido=s).efecto in t.EFECTOS_DE_UN_MOVIMIENTO for s in t.SENTIDOS)
    assert "transferencia" not in t.EFECTOS_DE_UN_MOVIMIENTO


def test_los_efectos_son_los_del_catalogo_publicado_y_no_una_copia():
    """Dos listas que dicen lo mismo en dos sitios acaban diciendo cosas distintas. Es el mismo ancla que
    `PROVISIONADO`/`PAGADO` tienen contra el `enum` del esquema.

    El catálogo tiene **tres** y el movimiento solo puede tener **dos**: el tercero existe para el nivel de la
    operación, no para el de la línea, y esa diferencia es a propósito."""
    from contaperu import vocabulario

    assert set(t.EFECTOS_DE_UN_MOVIMIENTO) < set(vocabulario.EFECTOS_DE_TESORERIA)
    assert vocabulario.EFECTOS_DE_TESORERIA == ("entrada", "salida", "transferencia")
    # Y su fuente es la norma, no nuestra opinión: sin ella el cargador del vocabulario no arranca.
    assert "NIC 7" in vocabulario.FUENTES["efectos_de_tesoreria"]


def test_un_libro_de_tesoreria_existe_y_el_motor_no_lo_origina():
    """Las dos mitades de la fase, en un test. El tipo de libro existe —así que el dato puede entrar y validarse—
    y el motor **todavía no sabe armar su asiento**, así que la puerta de la 8.2 lo para diciendo cuáles sabe.

    Es la primera vez que esa guarda sirve de verdad: hasta hoy no había ningún libro del catálogo fuera de
    `TIPOS_DEL_MOTOR`, y su docstring ya avisaba de que el día que lo hubiera, lo que fallaría sería esto."""
    import pytest as _pytest

    from contaperu.asiento import faltas, motor
    from contaperu.modelo import POR_OPERACION, Libro

    libro = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202608", tipo="tesoreria")
    assert libro.es_tesoreria and not libro.es_venta and not libro.es_compra
    assert libro.rasgos.origen == "movimientos"
    assert libro.rasgos.sentido_principal == POR_OPERACION

    with _pytest.raises(faltas.LibroQueElMotorNoOrigina) as e:
        motor.lineas_e_indice_del_libro(libro, [], {}, {})
    assert e.value.tipo == "tesoreria" and e.value.sabe == motor.TIPOS_DEL_MOTOR
    assert "venta" in str(e.value) and "compra" in str(e.value)


# ── El cuadre, que es lo que hace verificable a un lector ──────────────────

def test_la_cadena_de_saldos_reproduce_la_del_banco():
    """La cadena encadena a mano: 1 000,00 + 500,00 = 1 500,00, y − 200,00 − 0,20 de ITF = 1 299,80."""
    movs = [mov(referencia="000001", saldo="1500.00"),
            mov(referencia="000002", importe="200.00", sentido="cargo", itf="0.20",
                descripcion="CARGO POR TRANSFERENCIA", saldo="1299.80")]
    r = t.cuadra(movs, saldo_inicial=SALDO_ANTERIOR)
    assert r.cuadra, str(r)
    assert r.saldo_final == Decimal("1299.80")
    assert (r.cargos, r.abonos) == (Decimal("200.00"), Decimal("500.00"))


def test_el_itf_entra_en_la_cadena_aunque_no_este_en_la_columna_del_importe():
    """Lo enseñó el archivo real y es el tipo de cosa que un lector nuevo descubre tarde: en BBVA el ITF va en su
    propia columna y el saldo corrido lo resta igual. Sin restarlo, la segunda fila del mes ya no cuadra."""
    sin_itf = t.cuadra([mov(importe="200.00", sentido="cargo", saldo="1299.80")],
                       saldo_inicial="1500.00")
    assert not sin_itf.cuadra and sin_itf.diferencia == Decimal("-0.20")
    con_itf = t.cuadra([mov(importe="200.00", sentido="cargo", itf="0.20", saldo="1299.80")],
                       saldo_inicial="1500.00")
    assert con_itf.cuadra


def test_una_linea_mal_leida_se_delata_en_el_acto_y_dice_cual():
    """Es para lo que existe esta función. Un lector de PDF se equivoca callado —se salta una línea, pega dos
    columnas— y el saldo corrido lo descubre sin que haga falta un humano."""
    movs = [mov(saldo="1500.00"), mov(importe="200.00", sentido="cargo", saldo="999999.99")]
    r = t.cuadra(movs, saldo_inicial=SALDO_ANTERIOR)
    assert not r.cuadra and r.rompe_en == 2
    assert "se rompe en el movimiento 2" in str(r)
    with pytest.raises(t.ExtractoNoCuadra):
        t.exigir(movs, saldo_inicial=SALDO_ANTERIOR)


def test_un_movimiento_sin_saldo_propio_no_rompe_nada():
    """Hay extractos que solo dan el saldo al final de cada día. Se le aplica su importe y se sigue."""
    r = t.cuadra([mov(), mov(importe="200.00", sentido="cargo")], saldo_inicial=SALDO_ANTERIOR)
    assert r.cuadra and r.saldo_final == Decimal("1300.00")


def test_el_saldo_final_declarado_se_comprueba_y_el_ausente_no_se_inventa():
    r = t.cuadra([mov()], saldo_inicial=SALDO_ANTERIOR, saldo_final="1500.00")
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
