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

import json
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


def test_los_tres_efectos_del_catalogo_tienen_quien_los_emita():
    """**Un valor de catálogo sin productor es un valor que nadie puede emitir**, y es lo que pasaba hasta la
    12.0: el catálogo publicaba tres efectos, `Movimiento.efecto` daba dos y nada en el motor componía el tercero.
    Lo encontró John el 11-oct-2026 preguntando por qué no estaba `transferencia`.

    La respuesta no era añadirlo al movimiento —una línea sola sigue sin poder saberlo, y el test de arriba lo
    fija— sino construir quien lo compone. `efecto_de` toma el movimiento y lo que el ERP **declaró**.

    Este test recorre el catálogo entero: si mañana entra un cuarto efecto y nadie lo produce, se pone rojo."""
    from contaperu import vocabulario

    cargo = mov(sentido="cargo")
    abono = mov(sentido="abono")
    producibles = {
        t.efecto_de(abono),                                          # entrada
        t.efecto_de(cargo),                                          # salida
        t.efecto_de(cargo, {"cuenta_propia": "bbva-dolares"}),       # transferencia, DECLARADA
    }
    assert producibles == set(vocabulario.EFECTOS_DE_TESORERIA), (
        "hay un efecto en el catálogo que nadie sabe emitir")

    # Una imputación que no declara traspaso no cambia nada: el tercero no se deduce de tener contrapartida.
    assert t.efecto_de(cargo, {"cuenta_contable": "4212100"}) == t.SALIDA
    assert t.efecto_de(cargo, None) == t.SALIDA
    # Y el movimiento, por su cuenta, sigue sin poder decirlo. Es la invariante que sostiene el modelo.
    assert cargo.efecto == t.SALIDA


def test_un_libro_de_tesoreria_existe_y_el_motor_lo_origina_por_su_propia_puerta():
    """**Lo que esto decía hasta la 12.8**: el tipo de libro existe y el motor todavía no sabe armar su asiento.
    La segunda mitad dejó de ser cierta, y la forma en que dejó de serlo es la que importa — el motor no aprendió
    a sacar un asiento de tesorería de la puerta de los comprobantes, sino que le abrió la suya.

    Y la guarda que esto probaba **no se fue**: sigue parando cualquier libro del catálogo que el motor no
    origine, que es para lo que se puso (el hito B13, el diario de un ERP)."""
    from contaperu.asiento import comprobante as motor, movimiento
    from contaperu.modelo import POR_OPERACION, Libro

    libro = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202608", tipo="tesoreria")
    assert libro.es_tesoreria and not libro.es_venta and not libro.es_compra
    assert libro.rasgos.origen == "movimientos"
    assert libro.rasgos.sentido_principal == POR_OPERACION

    # La puerta de los comprobantes sigue siendo de comprobantes, y lo dice.
    assert "tesoreria" in motor.TIPOS_DEL_MOTOR
    lineas, rangos, indice = movimiento.lineas_e_indice_de_movimientos(libro, [], {})
    assert (lineas, rangos, indice) == ([], {}, ()), "un mes sin movimientos no es un error, es un mes vacío"


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


# ── El pago, que es un movimiento más: la entrada única (3.0 del estándar) ─

def pago(**extra) -> t.Movimiento:
    """Un movimiento que viene de una constancia y no de un extracto: tiene el número del papel y no tiene saldo.

    Hasta la 2.0 esto era un objeto `Constancia` aparte. La fusión es de John (11-oct-2026): al motor llega un item
    de operación, venga de donde venga, y lo que decía de qué testigo era lo dice su `origen`."""
    datos = {"cuenta": "bbva-soles", "fecha": "2026-08-14", "importe": "4711.00", "sentido": "cargo",
             "moneda": "PEN", "constancia": "00012345678", "medio_pago": "001"}
    return t.Movimiento(**{**datos, **extra})


@pytest.mark.parametrize("clase,datos", [
    ("comprobante", {"tipo_cp": "01", "serie": "F001", "numero": "123", "contraparte_doc": "20602222226"}),
    ("tributo", {"codigo": "1000", "periodo": "202607"}),
    ("cuenta_propia", {"cuenta": "bbva-dolares"}),
    ("libre", {"texto": "Reintegro de caja chica de obra"}),
])
def test_un_pago_cancela_cualquier_cosa(clase, datos):
    """Es lo que John pidió: «todo tipo de pagos, porque puede llamar a otra cuenta que no necesariamente
    proveedor». Las cuatro clases cubren el depósito de detracción, el pago de tributos, el traspaso propio y la
    caja chica **sin que el estándar enumere propósitos de pago**, que es la trampa de un modelo de tesorería."""
    m = pago(referencias=[{"clase": clase, "datos": datos}])
    assert m.referencias[0].clase == clase
    assert m.a_dict()["referencias"][0]["datos"] == {k: str(v) for k, v in datos.items()}


def test_los_dos_numeros_de_una_operacion_conviven_y_son_distintos():
    """El del banco y el del papel que prueba el pago. **Es el caso diario de una detracción**: se paga desde BBVA,
    así que el extracto le da su `N° OPER` y el Banco de la Nación su vóucher, y los dos hacen falta — el primero
    es la llave con la que una relectura no duplica, y el segundo el que se escribe en el comprobante.

    Por eso son dos campos y no uno: fundirlos obligaría a elegir cuál se pierde."""
    m = pago(referencia="123456", constancia="00012345678")
    assert m.referencia == "123456" and m.constancia == "00012345678"
    assert m.clave == ("bbva-soles", "123456"), "la llave de deduplicación es la del banco"


def test_una_referencia_no_lleva_lo_que_no_es_de_su_clase():
    with pytest.raises(t.ReferenciaInvalida) as e:
        t.Referencia(clase="tributo", datos={"codigo": "1000", "serie": "F001"})
    assert "serie" in str(e.value) and "codigo, periodo" in str(e.value)


def test_lo_que_ninguna_referencia_reclama_se_reporta_y_no_se_cierra():
    """Un cargo lleva el ITF dentro, y un pago puede cancelar algo que el papel no nombra. El motor lo dice y no
    decide qué es: eso es del contador, por la imputación."""
    m = pago(importe="4721.50", referencias=[
        {"clase": "comprobante", "datos": {"tipo_cp": "01", "serie": "F001", "numero": "123"},
         "importe": "4711.00"}])
    assert m.repartido == Decimal("4711.00")
    assert m.sin_atribuir == Decimal("10.50")
    # Sin importes por referencia no hay reparto que comprobar: la referencia vale por el total.
    assert pago(referencias=[{"clase": "libre", "datos": {"texto": "x"}}]).sin_atribuir == Decimal("0.00")


def test_un_origen_desconocido_no_pasa_y_es_un_cambio_de_la_3_0():
    """Hasta la 2.0 el `origen` de una constancia se pasaba a minúsculas y se aceptaba cualquier cosa, y el daño
    era silencioso: un `origen: "ocr"` **dejaba de salir en `de_lectura_asistida`**, o sea que lo que leyó un
    modelo dejaba de pedir revisión sin que nada lo dijera.

    Ahora para, que es el trato que `Comprobante` le da al suyo: mejor fallar que inventar. Y la lista es **propia**
    y no la del comprobante: un `xml` o una propuesta del SIRE no son cosas de un banco."""
    with pytest.raises(t.MovimientoInvalido) as e:
        pago(origen="ocr")
    assert "manual" in str(e.value) and "vision" in str(e.value)
    assert "xml" not in t.ORIGENES and "sire" not in t.ORIGENES
    # Y los dos que piden revisión son los dos del comprobante que significan lo mismo.
    assert t.LECTURA_ASISTIDA == ("pdf_texto", "vision")
    assert pago(origen="vision").de_lectura_asistida and not pago(origen="archivo").de_lectura_asistida


def test_un_pago_apunta_a_la_cuenta_por_su_id_y_no_a_una_cuenta_contable():
    """Es la decisión que impide que el motor adivine un 104: el movimiento nombra la cuenta declarada, y la
    contable sale de ahí."""
    m = pago()
    declaradas = {x.id: x for x in t.leer([cuenta().a_dict()])}
    assert m.cuenta in declaradas
    assert declaradas[m.cuenta].cuenta_contable == "10411100"


# ── Y la frontera, dicha en un test ────────────────────────────────────────

def test_la_tesoreria_no_sabe_leer_ningun_banco_todavia():
    """A propósito, y el día que deje de ser cierto este test cae y hay que decirlo en el CHANGELOG. La forma
    salió de nueve extractos reales, pero un parser entra con su archivo delante y su fixture anonimizado."""
    assert not [n for n in t.__all__ if "leer_extracto" in n or "bbva" in n.lower()]
    # Y tampoco concilia: casar un pago con lo que cancela es D3 y necesita dos archivos.
    assert not [n for n in t.__all__ if "conciliar" in n]


# ── Las dos puertas nuevas del núcleo (9.1) ────────────────────────────────

def test_no_se_puede_repartir_mas_de_lo_que_se_pago():
    """Lo que ninguna referencia reclama se informa y no se cierra, porque decidir qué es ese resto es del
    contador. Pero reclamar más de lo pagado no es un juicio contable: es una suma que no cuadra, y para.

    Es la puerta equivalente a la cadena de saldos de un extracto — la que hace verificable lo que leyó una IA."""
    with pytest.raises(t.MovimientoInvalido) as e:
        pago(importe="1000.00", referencias=[
            {"clase": "libre", "datos": {"texto": "una"}, "importe": "600.00"},
            {"clase": "libre", "datos": {"texto": "otra"}, "importe": "600.00"}])
    assert "1200.00" in str(e.value) and "1000.00" in str(e.value)
    # Y justo hasta el importe sí vale: el reparto exacto es lo normal.
    exacta = pago(importe="1000.00", referencias=[
        {"clase": "libre", "datos": {"texto": "una"}, "importe": "400.00"},
        {"clase": "libre", "datos": {"texto": "otra"}, "importe": "600.00"}])
    assert exacta.sin_atribuir == Decimal("0.00")


def test_una_cuenta_que_nadie_declaro_se_dice_y_no_se_adivina():
    """El `id` es la llave con la que el dinero se enlaza con su 104. Si no está en el maestro no hay nada que
    deducir —ni el banco, ni la moneda, ni la cuenta contable—, así que se nombra.

    Hasta la 9.1 pasaba en silencio: un `id` mal escrito daba un movimiento perfectamente válido que no se podía
    casar con ninguna cuenta, y eso no se ve hasta el cierre. Y desde la 3.0 del estándar mira **un solo bloque**:
    la `cuenta_origen` de una constancia era el segundo sitio donde preguntar lo mismo."""
    declaradas = [cuenta().a_dict()]
    huerfanos = t.sin_cuenta_declarada([mov(cuenta="bbva-euros", referencia="000009")], declaradas)
    assert huerfanos == [{"que": "movimiento", "cual": "000009", "cuenta": "bbva-euros"}]
    # Un pago, que es un movimiento más, cae por lo mismo.
    assert t.sin_cuenta_declarada([pago(cuenta="otra")], declaradas) == [
        {"que": "movimiento", "cual": "", "cuenta": "otra"}]
    # Lo que sí está declarado no sale, y sin maestro no se inventa un error: es un argumento opcional.
    assert t.sin_cuenta_declarada([mov(), pago()], declaradas) == []
    assert t.sin_cuenta_declarada([mov(cuenta="cualquiera")], []) == []


# ── El bloque entra por el documento ───────────────────────────────────────

def documento_de_tesoreria(**extra) -> dict:
    return {"open_accounting": "4.0",
            "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202608",
                      "tipo": "tesoreria"}, **extra}


def test_un_bloque_ausente_es_una_lista_vacia_y_no_un_error():
    """Igual que `comprobantes`: la raíz del estándar solo exige `open_accounting` y `libro`, así que un documento
    puede traer el bloque o no traerlo."""
    from contaperu.pipeline import preparacion

    assert preparacion.movimientos_de(documento_de_tesoreria()) == []


def test_el_bloque_de_las_constancias_ya_no_existe():
    """La entrada única de la 3.0, vista por donde la ve quien produce documentos: **no hay `constancias_de`** y la
    raíz del esquema no admite el bloque. Lo que una constancia decía lo dice ahora un movimiento, con su `origen`
    y sus `referencias`."""
    import json
    from pathlib import Path

    from contaperu.pipeline import preparacion

    assert not hasattr(preparacion, "constancias_de")
    esquema = json.loads((Path(__file__).resolve().parents[1] / "estandar" / "open-accounting.schema.json")
                         .read_text(encoding="utf-8"))
    assert "constancias" not in esquema["properties"], "la raíz ya no lo admite"
    assert "constancia" not in esquema["$defs"] and "referencia_de_constancia" not in esquema["$defs"]
    # Y la referencia sigue, con el nombre de lo que es: lo que cancela un PAGO, venga de donde venga.
    assert "referencia_de_pago" in esquema["$defs"]


def test_una_clave_que_no_es_de_un_movimiento_se_dice_por_su_nombre():
    """Lo desconocido se rechaza y no se ignora, que es la lección de la 7.0 con el `libro`: un dato que se cuela
    sin error es un dato que se pierde sin aviso."""
    from contaperu.errores import DocumentoInvalido
    from contaperu.pipeline import preparacion

    doc = documento_de_tesoreria(movimientos=[{**mov().a_dict(), "titular": "quien sea"}])
    with pytest.raises(DocumentoInvalido) as e:
        preparacion.movimientos_de(doc)
    assert "titular" in str(e.value)
    # Y un bloque que no es una lista tampoco se interpreta.
    with pytest.raises(DocumentoInvalido):
        preparacion.movimientos_de(documento_de_tesoreria(movimientos={"cuenta": "bbva-soles"}))


# ── La operación de la api (9.1) ───────────────────────────────────────────

def test_la_api_resume_cada_cuenta_y_no_afirma_ningun_cuadre():
    """`totales_por_cuenta` es un RESUMEN y el nombre lo dice: cuánto llegó de cada cuenta. No dice que encaje.

    Hasta la 11.x aquí venía un `cuadre` que recorría la cadena de saldos corridos, y el test de abajo explica
    por qué se fue. El ITF va en su propia columna del resumen porque no es un cargo del titular hacia un
    tercero: es lo que el banco descuenta además."""
    from contaperu import api

    doc = documento_de_tesoreria(movimientos=[
        mov(referencia="000001", saldo="1500.00").a_dict(),
        mov(referencia="000002", importe="200.00", sentido="cargo", itf="0.20", saldo="1299.80").a_dict()])
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])

    assert "cuadre" not in r, "la api dejó de juzgar cómo se leyó el archivo (12.0)"
    assert r["totales_por_cuenta"] == [{"cuenta": "bbva-soles", "movimientos": 2, "cargos": "200.00",
                                        "abonos": "500.00", "itf": "0.20", "cuenta_contable": "10411100"}]
    # Lo único que avisa es que a estos movimientos les falta su contrapartida, que es el `sin_cuenta` del dinero:
    # un extracto recién leído no la trae, y la pone el contador.
    assert {a["codigo"] for a in r["avisos"]} == {"MOVIMIENTO_SIN_IMPUTAR"}
    assert r["imputados"] == 0 and len(r["sin_imputar"]) == 2


def test_la_api_no_puede_afirmar_un_cuadre_que_no_comprobo():
    """**El test que faltaba, y el que encontró todo esto.** Lo midió John el 11-oct-2026: *«el cuadre de saldos
    no garantiza nada, y además no todos tienen eso»*.

    `tesoreria.cuadra` devuelve `cuadra=True` cuando ninguna línea trae `saldo`, porque «cuadra» significa
    «ninguna línea contradijo la cadena» y si ninguna la afirma, ninguna la contradice. Eso está bien en la
    función —y su docstring ya lo dice— pero era veneno en la api: **un ERP que manda operaciones estructuradas
    no trae saldos nunca**, así que recibía un verde en cada llamada mirando nada. Incluso con una línea
    inventada en medio.

    La regla que queda: la respuesta **no afirma nada sobre saldos** salvo cuando hay una cabecera que contrastar,
    y entonces lo dice por `avisos`."""
    from contaperu import api, tesoreria

    # Operaciones estructuradas: ninguna trae `saldo`, que es el caso de cualquier ERP.
    sin_saldos = [mov(referencia="000001", saldo="").a_dict(),
                  mov(referencia="000002", importe="200.00", sentido="cargo", saldo="").a_dict()]
    # La función publicada sigue diciendo `True`, y hace bien: nadie la contradijo.
    assert tesoreria.cuadra(sin_saldos).cuadra

    r = api.revisar_tesoreria(documento_de_tesoreria(movimientos=sin_saldos), [cuenta().a_dict()])
    entero = json.dumps(r, ensure_ascii=False)
    assert "cuadr" not in entero.lower(), "la respuesta no puede insinuar un cuadre que nadie comprobó"
    assert [a["codigo"] for a in r["avisos"]] == ["MOVIMIENTO_SIN_IMPUTAR"] * 2

    # Y con una línea inventada de 999 999, tampoco cambia nada: no había contra qué comprobarla.
    con_falsa = api.revisar_tesoreria(
        documento_de_tesoreria(movimientos=[*sin_saldos,
                                            mov(referencia="000003", importe="999999.00",
                                                sentido="cargo", saldo="").a_dict()]),
        [cuenta().a_dict()])
    assert con_falsa["totales_por_cuenta"][0]["cargos"] == "1000199.00", "se suma, que es lo único que se afirma"


def test_la_api_informa_lo_no_atribuido_y_marca_lo_que_leyo_una_ia():
    """Las dos cosas que hacen usable un pago que salió de un PDF: lo que ninguna referencia reclama se reporta **y
    no se cierra**, y lo que leyó un modelo se marca para que se pueda revisar.

    La confianza no relaja nada: el cuadre es el mismo. Es lo que la investigación de 2026 encuentra que funciona,
    porque la confianza que reporta un modelo no separa de forma fiable lo correcto de lo incorrecto.

    Desde la 3.0 del estándar los dos informes salen del **movimiento**, que es la única entrada, y lo nombran por
    `cual`: el número del papel si lo tiene, y si no el del banco."""
    from contaperu import api

    doc = documento_de_tesoreria(movimientos=[pago(
        importe="4721.50", origen="pdf_texto", confianza="0.92",
        referencias=[{"clase": "comprobante", "importe": "4711.00",
                      "datos": {"tipo_cp": "01", "serie": "F001", "numero": "123"}}]).a_dict()])
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])

    assert r["sin_atribuir"] == [{"cual": "00012345678", "importe": "4721.50",
                                 "repartido": "4711.00", "sin_atribuir": "10.50"}]
    assert r["de_lectura_asistida"] == [{"cual": "00012345678", "origen": "pdf_texto", "confianza": "0.92"}]
    # Y no es un aviso: no hay nada que arreglar, solo algo que mirar.
    assert not [a for a in r["avisos"] if a["codigo"] != "MOVIMIENTO_SIN_IMPUTAR"]
    # Un pago no trae saldo ni cabecera, así que no hay nada que contrastar — y no se afirma que lo haya.
    assert r["totales_por_cuenta"][0]["cargos"] == "4721.50"


def test_un_cargo_del_banco_es_un_movimiento_y_no_necesita_campo_propio():
    """La regla de modelado de la enmienda 0028, que resuelve una asimetría: el ITF tenía campo y una comisión
    no tenía ninguno.

    Dicho al derecho, **no le falta un campo a la comisión: le sobra uno al ITF**. Una comisión, los portes o el
    mantenimiento llegan como un movimiento más, con su propia imputación, que es lo que les da su cuenta de
    gasto. Así nadie tiene que pedir un campo nuevo cada vez que un banco inventa un concepto."""
    from contaperu import api

    doc = documento_de_tesoreria(
        movimientos=[mov(referencia="000010", importe="2000.00", sentido="cargo", id_externo="pago").a_dict(),
                     mov(referencia="000011", importe="15.00", sentido="cargo", id_externo="comision",
                         descripcion="MANTENIMIENTO DE CUENTA").a_dict(),
                     mov(referencia="000012", importe="4.50", sentido="cargo", id_externo="portes",
                         descripcion="PORTES").a_dict()],
        imputaciones_de_movimientos={"pago": {"cuenta_contable": "4212100"},
                                     "comision": {"cuenta_contable": "6391000"},
                                     "portes": {"cuenta_contable": "6391000"}})
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert r["imputados"] == 3 and r["avisos"] == [], "cada cargo es un hecho con su cuenta, sin campo nuevo"
    assert r["totales_por_cuenta"][0]["cargos"] == "2019.50"
    # Y el ITF de esos tres es cero porque ninguno lo lleva: el campo es para el banco que no le da fila.
    assert r["totales_por_cuenta"][0]["itf"] == "0.00"

    # El caso en que la regla NO se puede aplicar, que es el único motivo de que `itf` exista: BBVA lo descuenta
    # del saldo sin darle fila, así que no hay movimiento que lo represente y sintetizarlo sería inventarlo.
    sin_fila = documento_de_tesoreria(movimientos=[mov(importe="2000.00", sentido="cargo", itf="0.50").a_dict()])
    assert api.revisar_tesoreria(sin_fila, [cuenta().a_dict()])["totales_por_cuenta"][0]["itf"] == "0.50"


def test_la_moneda_de_un_movimiento_se_contrasta_con_la_de_su_cuenta():
    """Hasta la 3.0 no se contrastaba con nada: una cuenta en dólares aceptaba movimientos marcados en soles y
    **nada fallaba**. Es el mismo tipo de error que un `id` mal escrito — no se ve hasta el cierre.

    Y es un aviso y no un rechazo, porque el movimiento por sí solo es válido: lo que está mal es el par."""
    from contaperu import api

    en_dolares = cuenta(id="bbva-dolares", moneda="USD", numero="0011-0999-0000000002").a_dict()
    doc = documento_de_tesoreria(movimientos=[mov(cuenta="bbva-dolares", moneda="PEN").a_dict()])
    r = api.revisar_tesoreria(doc, [en_dolares])
    assert any(a["codigo"] == "MONEDA_DISTINTA_DE_LA_CUENTA" for a in r["avisos"])
    assert any("USD" in a["texto"] and "PEN" in a["texto"] for a in r["avisos"])
    # La misma moneda no avisa, y una cuenta que no declara la suya tampoco: no se inventa el par.
    assert not [a for a in api.revisar_tesoreria(
        documento_de_tesoreria(movimientos=[mov(cuenta="bbva-dolares", moneda="USD").a_dict()]),
        [en_dolares])["avisos"] if a["codigo"] == "MONEDA_DISTINTA_DE_LA_CUENTA"]


def test_la_api_avisa_de_una_relectura_y_de_una_cuenta_que_no_se_declaro():
    from contaperu import api

    doc = documento_de_tesoreria(movimientos=[
        mov(referencia="000001").a_dict(), mov(referencia="000001").a_dict(),
        mov(cuenta="bbva-euros", referencia="000009").a_dict()])
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert r["repetidos"] == 1, "una relectura con solape no duplica, y se dice cuántos se descartaron"
    assert any(a["codigo"] == "CUENTA_NO_DECLARADA" for a in r["avisos"])
    # Y sin maestro, lo dice en vez de callarse.
    assert any(a["codigo"] == "SIN_CUENTAS_DECLARADAS" for a in api.revisar_tesoreria(doc)["avisos"])


# ── Lo que un destino hace con un libro que no lleva (9.1) ─────────────────

def _los_que_no_llevan_tesoreria() -> list[str]:
    """Los drivers de serie que no declaran el libro de tesorería, **con su complemento nombrado**.

    Desde la 12.10 hay uno que sí lo lleva, `asiento_contable`, y por eso este reparto se calcula en vez de
    escribirse: un bucle sobre «todos» dejaría de comprobar lo que comprueba en cuanto entre el siguiente. Y se
    afirma cuál es el que lo lleva, para que el conjunto no se vacíe ni crezca en silencio — un test que deja de
    comprobar es el único que no avisa."""
    from contaperu import drivers

    llevan = sorted(n for n in drivers.DE_SERIE if "tesoreria" in drivers.obtener(n).FORMATOS)
    assert llevan == ["asiento_contable"], (
        "cambió quién lleva el libro de tesorería: decídelo a propósito y mueve este test")
    return sorted(set(drivers.DE_SERIE) - set(llevan))


def test_cada_driver_que_no_lleva_tesoreria_lo_rechaza_nombrando_los_que_si_lleva():
    """La degradación que el estándar promete para un tipo de libro, y que **no estaba ocurriendo**: los ocho
    drivers contestaban «No hay comprobantes que procesar», que es engañoso — la razón verdadera es que ese destino
    no lleva ese libro.

    No era una falta de mensaje, `drivers.formato_de` ya lo tenía bien: era un orden de comprobaciones, y se
    llamaba después de preparar. Nadie lo había notado porque hasta el 10-oct-2026 no existía ningún libro del
    catálogo fuera de los dos que todos los drivers llevan. El tercero lo destapó.

    **Siete de los ocho**, desde la 12.10: el neutral lo lleva, porque su formato es el estándar mismo."""
    from contaperu import api, drivers

    doc = documento_de_tesoreria(movimientos=[mov().a_dict()])
    for nombre in _los_que_no_llevan_tesoreria():
        lleva = sorted(drivers.obtener(nombre).FORMATOS)
        with pytest.raises(drivers.LibroQueElDestinoNoLleva) as e:
            api.exportar(doc, driver=nombre, configuracion={})
        assert e.value.tipo == "tesoreria" and e.value.driver == nombre
        for tipo in lleva:
            assert tipo in str(e.value), "tiene que decir qué libros SÍ lleva"
    # Y sigue siendo un `ValueError`, que es lo que era antes: quien lo atrape por ahí no se rompe.
    assert issubclass(drivers.LibroQueElDestinoNoLleva, ValueError)


def test_generar_asiento_tambien_dice_la_razon_verdadera():
    """La misma corrección en la otra puerta que ACTÚA, y llegaba dos versiones tarde (12.6).

    `exportar` comprueba el tipo de libro antes de preparar desde la 9.1; `generar_asiento` **nunca llamaba a
    `drivers.formato_de`**, así que para un libro de tesorería moría en el único muro que tiene —«No hay
    comprobantes que procesar»— diciendo que faltan comprobantes donde lo que pasa es que ese destino no lleva ese
    libro. Las dos puertas tienen que dar la misma razón para la misma causa."""
    from contaperu import api, drivers

    doc = documento_de_tesoreria(movimientos=[mov().a_dict()])
    for nombre in _los_que_no_llevan_tesoreria():
        if not drivers.contrato.arma_asientos(drivers.obtener(nombre)):
            continue          # ésos se niegan antes, y por otra razón que también es la verdadera
        with pytest.raises(drivers.LibroQueElDestinoNoLleva) as e:
            api.generar_asiento(doc, driver=nombre, configuracion={})
        assert e.value.tipo == "tesoreria" and e.value.driver == nombre


def test_diagnosticar_lo_DICE_en_vez_de_lanzarlo():
    """Y la tercera puerta no lanza, porque pregunta en vez de hacer: su contrato es «no lanza por lo que le falte
    al mes: lo describe». Hasta la 12.6 contestaba «no hay comprobantes que exportar», que es cierto y engañoso a
    la vez — no es que falten, es que ese destino no lleva ese libro."""
    from contaperu import api

    doc = documento_de_tesoreria(movimientos=[mov().a_dict()])
    d = api.diagnosticar(doc, driver="concar", configuracion={})
    assert d["listo_para_exportar"] is False
    assert d["por_que_no"] == ["el destino 'concar' no lleva libros de tipo 'tesoreria'"]
    assert [q["motivo"] for q in d["que_falta"]] == ["libro_que_el_destino_no_lleva"]
    assert d["que_falta"][0]["pedir_a"] == "sistema", "lo que se cambia es el destino, no el mes"
    assert "compra" in d["que_falta"][0]["texto"] and "venta" in d["que_falta"][0]["texto"]
    # La forma de la respuesta no cambia: es la misma degradación que `_sin_configuracion`.
    assert d["totales"]["saldrian"] == 0 and d["saldrian"] == [] and d["errores_de_configuracion"] == []


def test_el_maestro_indexado_vive_en_un_solo_sitio():
    """`por_id` es la búsqueda que un movimiento hace de su cuenta —y de su 104—, publicada (12.6). Estaba escrita
    a mano dentro de `api.revisar_tesoreria`, y el asiento de tesorería la necesita en otro sitio: dos copias de la
    misma búsqueda es como se separan."""
    from contaperu import tesoreria

    maestro = tesoreria.por_id([cuenta().a_dict()])
    assert set(maestro) == {"bbva-soles"}
    assert maestro["bbva-soles"].cuenta_contable == cuenta().cuenta_contable
    assert tesoreria.por_id(None) == {} and tesoreria.por_id([]) == {}
    # Y hereda la puerta de `leer`: dos cuentas con el mismo `id` no pasan.
    with pytest.raises(tesoreria.CuentaInvalida):
        tesoreria.por_id([cuenta().a_dict(), cuenta().a_dict()])


def test_las_reglas_de_compra_no_corren_por_descarte_en_un_libro_que_no_es_compra():
    """La auditoría de `tributos/validar.py` con un libro que no es ninguno de los dos. Sus reglas están en forma
    positiva —`if libro.es_venta and …`—, así que un libro nuevo se salta las de venta; lo que hay que confirmar es
    que **ninguna regla de compra corre por descarte**, que es el error que la 9.0 vino a cerrar un eje más
    arriba."""
    from contaperu.modelo import Comprobante, Libro
    from contaperu.tributos import validar

    libro = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202608", tipo="tesoreria")
    c = Comprobante.de_dict({"tipo_cp": "01", "serie": "F001", "numero": "123", "fecha_emision": "2026-08-05",
                             "contraparte_doc": "20602222226", "contraparte_nombre": "CONTRAPARTE SAC",
                             "moneda": "PEN", "base_gravada": "1000.00", "igv": "180.00", "total": "1180.00"})
    revisados = validar.revisar([c], libro, [], config={})
    codigos = {o.codigo for cp in revisados for o in cp.observaciones}
    # Nada que hable de crédito fiscal, detracción ni honorarios: son de las compras y este libro no lo es.
    assert not {x for x in codigos if "DETRACCION" in x or "CREDITO" in x or "HONORARIO" in x}, codigos


# ── La cabecera del extracto: el segundo control (3.0 del estándar) ────────

def extracto(**extra) -> dict:
    datos = {"cuenta": "bbva-soles", "desde": "2026-08-01", "hasta": "2026-08-31",
             "saldo_inicial": SALDO_ANTERIOR, "saldo_final": "1299.80",
             "total_cargos": "200.00", "total_abonos": "500.00"}
    return t.Extracto(**{**datos, **extra}).a_dict()


def un_mes() -> list:
    """Dos líneas que cuadran: un abono de 500 y un cargo de 200 con 0,20 de ITF."""
    return [mov(referencia="000001", saldo="1500.00").a_dict(),
            mov(referencia="000002", importe="200.00", sentido="cargo", itf="0.20", saldo="1299.80").a_dict()]


def test_lo_que_el_banco_declaro_se_contrasta_contra_lo_que_llego():
    """La única comprobación de saldos que se queda en la api, y lo que la hace valer: **no puede pasar en
    vacío**. Solo corre si la cabecera declara algo, y entonces compara dos números que existen los dos.

    Es la diferencia con la cadena de saldos corridos, que se fue en la 12.0 porque devolvía verde cuando no
    había nada que mirar."""
    from contaperu import api

    doc = documento_de_tesoreria(movimientos=un_mes(), extractos=[extracto()])
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert {a["codigo"] for a in r["avisos"]} == {"MOVIMIENTO_SIN_IMPUTAR"}, "falta la contrapartida, nada más"
    assert r["totales_por_cuenta"][0] == {"cuenta": "bbva-soles", "movimientos": 2, "cargos": "200.00",
                                          "abonos": "500.00", "itf": "0.20", "cuenta_contable": "10411100"}


def test_el_saldo_final_declarado_delata_la_linea_que_falta():
    """Es aritmética sobre lo que mandaste —lo de antes, más lo que entró, menos lo que salió y menos el ITF—,
    así que **no necesita que ninguna línea traiga su saldo**. Ése es el motivo de que esta comprobación se
    quedara en la api cuando la cadena se fue.

    Y caza el caso que un lector de PDF produce: si se pierde la ÚLTIMA línea del mes, las demás encadenan
    perfectamente entre sí y solo el total declarado lo nota."""
    from contaperu import api

    sin_la_ultima = documento_de_tesoreria(movimientos=un_mes()[:1], extractos=[extracto()])
    r = api.revisar_tesoreria(sin_la_ultima, [cuenta().a_dict()])
    dicho = [a for a in r["avisos"] if a["codigo"] == "SALDO_FINAL_DECLARADO_NO_COINCIDE"]
    assert dicho, "el saldo final declarado delata la línea que falta"
    assert "1299.80" in dicho[0]["texto"] and "1500.00" in dicho[0]["texto"]

    # Sin cabecera no hay contra qué comprobar, y entonces **no se dice nada**: no se inventa un cuadre.
    muda = api.revisar_tesoreria(documento_de_tesoreria(movimientos=un_mes()[:1]), [cuenta().a_dict()])
    assert not [a for a in muda["avisos"] if "SALDO" in a["codigo"] or "TOTAL" in a["codigo"]]

    # Y las líneas sin `saldo` tampoco lo impiden: la cuenta sale igual.
    sin_saldos = [{**m, "saldo": ""} for m in un_mes()[:1]]
    igual = api.revisar_tesoreria(documento_de_tesoreria(movimientos=sin_saldos, extractos=[extracto()]),
                                  [cuenta().a_dict()])
    assert any(a["codigo"] == "SALDO_FINAL_DECLARADO_NO_COINCIDE" for a in igual["avisos"])


def test_los_dos_totales_de_la_cabecera_se_contrastan():
    """La comprobación que caza lo que el saldo final no puede: **un cargo y un abono perdidos por el mismo
    importe dejan el saldo igual**. Los totales no."""
    from contaperu import api

    doc = documento_de_tesoreria(movimientos=un_mes(),
                                 extractos=[extracto(total_cargos="900.00", saldo_final=None)])
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert any(a["codigo"] == "TOTAL_DECLARADO_NO_COINCIDE" for a in r["avisos"])
    assert any("900.00" in a["texto"] and "200.00" in a["texto"] for a in r["avisos"])
    # Y es lo único que se dice: el resumen no opina, solo suma.
    assert r["totales_por_cuenta"][0]["cargos"] == "200.00"


def test_el_saldo_inicial_ya_no_entra_por_dos_vias():
    """`saldos_iniciales` se fue con su único consumidor, la cadena, y con él la regla de «cuál de los dos gana»
    —que solo existía porque había dos caminos para el mismo dato—. Queda `extractos[]`, que es uno."""
    from contaperu import api

    with pytest.raises(TypeError):
        api.revisar_tesoreria(documento_de_tesoreria(movimientos=un_mes()), [cuenta().a_dict()],
                              saldos_iniciales={"bbva-soles": SALDO_ANTERIOR})


def test_dos_cabeceras_de_la_misma_cuenta_no_pasan():
    """No es un mes partido en dos hojas: es un documento que declara dos saldos iniciales para lo mismo."""
    from contaperu.errores import DocumentoInvalido
    from contaperu.pipeline import preparacion

    with pytest.raises(DocumentoInvalido) as e:
        preparacion.extractos_de(documento_de_tesoreria(extractos=[extracto(), extracto(saldo_inicial="9.00")]))
    assert "bbva-soles" in str(e.value) and "dos documentos" in str(e.value)


def test_el_periodo_de_la_cabecera_se_reporta_y_no_filtra():
    """Un extracto de agosto con una línea de julio dentro es un error de quien leyó el archivo, no algo que el
    motor deba arreglar escondiendo la línea. Se cuadra lo que llega, entero."""
    from contaperu import api

    de_julio = mov(referencia="000003", fecha="2026-07-20", saldo="1500.00").a_dict()
    r = api.revisar_tesoreria(documento_de_tesoreria(movimientos=[de_julio], extractos=[extracto(saldo_final=None)]),
                              [cuenta().a_dict()])
    assert r["movimientos"] == 1, "la línea de julio no se filtra"


def test_una_cabecera_que_acaba_antes_de_empezar_no_pasa():
    with pytest.raises(t.ExtractoInvalido):
        t.Extracto(cuenta="bbva-soles", desde="2026-08-31", hasta="2026-08-01")
    with pytest.raises(t.ExtractoInvalido):
        t.Extracto(cuenta="")


# ── La imputación de un movimiento: lo que el ERP pone (3.0 del estándar) ──

def test_el_erp_imputa_la_contrapartida_y_el_motor_no_adivina_ninguna():
    """La decisión de John (11-oct-2026): la contrapartida la pone su ERP, como ya hace con una compra. Y es la
    misma doctrina que rige desde la 3.0 del paquete — **el motor no elige ninguna cuenta, la recibe**.

    La 104 **no** sale de aquí: sale de la cuenta bancaria del maestro. Esto pone la otra cara."""
    from contaperu import api

    doc = documento_de_tesoreria(
        movimientos=[mov(referencia="000002", importe="200.00", sentido="cargo", id_externo="mov-881").a_dict()],
        imputaciones_de_movimientos={"mov-881": {"cuenta_contable": "4212100",
                                                 "contraparte_doc": "20602222226", "centro_costo": "OBRA01"}})
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert r["imputados"] == 1 and r["sin_imputar"] == []
    assert not [a for a in r["avisos"] if a["codigo"] == "MOVIMIENTO_SIN_IMPUTAR"]
    # Y la 104 sigue saliendo del maestro, no de la imputación.
    assert r["totales_por_cuenta"][0]["cuenta_contable"] == "10411100"


def test_un_movimiento_sin_contrapartida_se_dice_y_es_el_sin_cuenta_del_dinero():
    """El mismo trato que un comprobante sin cuenta: el motor no la adivina y dice a quién pedirla. Es lo que hace
    usable el circuito «el ERP sube el extracto → el motor dice qué falta → el contador imputa»."""
    from contaperu import api

    r = api.revisar_tesoreria(documento_de_tesoreria(movimientos=[mov(id_externo="mov-881").a_dict()]),
                              [cuenta().a_dict()])
    # `mov()` no trae número del banco ni del papel, así que se nombra por su `id_externo`: es lo que hay.
    assert r["imputados"] == 0 and r["sin_imputar"] == ["mov-881"]
    falta = next(a for a in r["avisos"] if a["codigo"] == "MOVIMIENTO_SIN_IMPUTAR")
    assert falta["pedir_a"] == "contador" and "la otra cara se imputa" in falta["texto"]


def test_un_cargo_que_paga_tres_facturas_son_tres_partes():
    """Es la cardinalidad que la 2.0 usó para justificar dos bloques, resuelta donde le toca: **dentro del item**,
    igual que el reparto de una compra. Y cada parte lleva su propio tercero, porque un cargo puede pagar facturas
    de tres proveedores distintos."""
    from contaperu import api

    doc = documento_de_tesoreria(
        movimientos=[mov(importe="5000.00", sentido="cargo", id_externo="mov-882").a_dict()],
        imputaciones_de_movimientos={"mov-882": {"reparto": [
            {"importe": "3000.00", "cuenta_contable": "4212100", "contraparte_doc": "20602222226"},
            {"importe": "1500.00", "cuenta_contable": "4212100", "contraparte_doc": "20607777773"},
            {"importe": "500.00", "cuenta_contable": "6391000", "centro_costo": "ADMIN"}]}})
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert r["imputados"] == 1 and r["sin_imputar"] == []


def test_un_reparto_que_no_suma_el_importe_para_y_no_se_reporta():
    """**Aquí bloquea**, al revés que `sin_atribuir`. Ese informe existe porque «qué es ese resto lo decide el
    contador por la imputación»; y esto YA es la imputación, así que un reparto que no cuadra no es un dato que
    falte sino una decisión mal hecha.

    Y el ITF queda fuera de la suma: son sus dos líneas propias, que esperan su norma (D6)."""
    from contaperu import api
    from contaperu.errores import DocumentoInvalido

    doc = documento_de_tesoreria(
        movimientos=[mov(importe="5000.00", sentido="cargo", itf="0.50", id_externo="mov-882").a_dict()],
        imputaciones_de_movimientos={"mov-882": {"reparto": [
            {"importe": "3000.00", "cuenta_contable": "4212100"}]}})
    with pytest.raises(DocumentoInvalido) as e:
        api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert "3000.00" in str(e.value) and "5000.00" in str(e.value) and "exacto" in str(e.value)
    # Justo el importe, sin contar el ITF, sí pasa.
    doc["imputaciones_de_movimientos"]["mov-882"]["reparto"][0]["importe"] = "5000.00"
    assert api.revisar_tesoreria(doc, [cuenta().a_dict()])["imputados"] == 1


def test_el_traspaso_entre_cuentas_propias_se_declara_y_es_la_unica_via():
    """El efecto `transferencia` del catálogo existe porque la **NIC 7 §9** excluye de los flujos los traspasos
    entre partidas de efectivo, así que hay que poder nombrarlo para dejarlo fuera y no contarlo dos veces.

    `Movimiento.efecto` **nunca** lo devuelve, y eso no cambia: una línea sola no puede saber que es la mitad de un
    par. Lo que entra es la vía para declararlo — y la otra, `conciliar`, propone y nunca confirma (D3)."""
    from contaperu import api

    otra = cuenta(id="bbva-dolares", moneda="USD", numero="0011-0999-0000000002").a_dict()
    doc = documento_de_tesoreria(
        movimientos=[mov(importe="1000.00", sentido="cargo", id_externo="mov-883").a_dict()],
        imputaciones_de_movimientos={"mov-883": {"cuenta_propia": "bbva-dolares"}})
    r = api.revisar_tesoreria(doc, [cuenta().a_dict(), otra])
    assert r["transferencias_declaradas"] == [
        {"cual": "mov-883", "cuenta": "bbva-soles", "cuenta_propia": "bbva-dolares"}]
    # El movimiento sigue sin poder decirlo por su cuenta: eso es lo que sostiene el modelo.
    assert t.Movimiento.de_dict(doc["movimientos"][0]).efecto == "salida"
    assert "transferencia" not in t.EFECTOS_DE_UN_MOVIMIENTO

    # Y la otra cuenta tiene que existir: un traspaso es entre dos cuentas propias.
    solo_una = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert any(a["codigo"] == "CUENTA_PROPIA_NO_DECLARADA" for a in solo_una["avisos"])


def test_las_tres_formas_de_imputar_se_excluyen():
    """Las tres contestan la misma pregunta —cuál es la contrapartida— de tres maneras, así que dos a la vez no
    tienen respuesta. Es el precedente exacto de la imputación de un comprobante: «¿cuál mandaría?»."""
    with pytest.raises(t.ImputacionInvalida) as e:
        t.ImputacionDeMovimiento.de({"cuenta_contable": "4212100",
                                     "reparto": [{"importe": "1.00", "cuenta_contable": "42"}]})
    assert "cuál mandaría" in str(e.value)
    with pytest.raises(t.ImputacionInvalida) as e:
        t.ImputacionDeMovimiento.de({"cuenta_propia": "otra", "centro_costo": "OBRA01"})
    assert "no lleva nada más" in str(e.value)
    # Una parte sin importe o sin cuenta tampoco: son lo único para lo que existe una parte.
    with pytest.raises(t.ImputacionInvalida):
        t.Parte(cuenta_contable="4212100")
    with pytest.raises(t.ImputacionInvalida):
        t.Parte(importe="100.00")


def test_una_llave_que_no_es_de_ningun_movimiento_se_rechaza():
    """Una llave mal escrita dejaría ese movimiento sin su cuenta **y sin aviso**, que es la clase de error que no
    se ve hasta el cierre. Es la misma puerta que `con_imputacion` pone para los comprobantes."""
    from contaperu import api
    from contaperu.errores import DocumentoInvalido

    doc = documento_de_tesoreria(movimientos=[mov(id_externo="mov-881").a_dict()],
                                 imputaciones_de_movimientos={"mov-888": {"cuenta_contable": "4212100"}})
    with pytest.raises(DocumentoInvalido) as e:
        api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert "mov-888" in str(e.value)


def test_una_clave_que_no_es_de_una_imputacion_se_dice_por_su_nombre():
    """Lo desconocido se rechaza y no se ignora: la lección de la 7.0 con el `libro`. Y aquí importa más, porque
    los campos de la imputación de un comprobante **no** son los de la de un movimiento."""
    with pytest.raises(t.ImputacionInvalida) as e:
        t.ImputacionDeMovimiento.de({"anulada_por_nota": True})
    assert "anulada_por_nota" in str(e.value) and "cuenta_propia" in str(e.value)
    with pytest.raises(t.ImputacionInvalida):
        t.ImputacionDeMovimiento.de({"cuenta_tercero": "4212100"})


def test_sin_imputaciones_la_respuesta_es_la_de_siempre_mas_las_tres_claves():
    """Lo que hace que esto sea aditivo de verdad: un documento sin el bloque se revisa igual, y las tres claves
    nuevas dicen lo que hay —ninguno imputado— en vez de faltar."""
    from contaperu import api

    r = api.revisar_tesoreria(documento_de_tesoreria(movimientos=[mov().a_dict()]), [cuenta().a_dict()])
    assert r["imputados"] == 0 and r["transferencias_declaradas"] == []
    assert r["totales_por_cuenta"][0]["movimientos"] == 1


def test_la_glosa_recorre_su_cadena_de_respaldo_entera():
    """La glosa que se escribe en el libro, que el contrato **no tenía** hasta la 12.0 — y lo encontró John
    integrando (11-oct-2026): *«en movimiento no existe la variable glosa, y esto es importante para los
    libros»*. La piden los cuatro destinos: campo 16 del Diario 5.1 del PLE, las dos de CONCAR, y las suyas
    CONTASIS y STARSOFT.

    Vive en la imputación porque **es una decisión y no un hecho del papel**: `descripcion` es el texto del
    banco, que además entra en la clave de deduplicación. La cadena se recorre hasta que algo diga algo, para que
    ninguna línea salga sin glosa — la misma forma que `asiento.glosa_de` tiene para un comprobante."""
    m = t.Movimiento(cuenta="bbva-soles", fecha="2026-03-14", importe="12282.60", sentido="cargo",
                     descripcion="Transferencia a cuentas de terceros", contraparte_nombre="Proveedor SAC")
    i = t.ImputacionDeMovimiento(cuenta_contable="4212100", glosa="Pago fact F001-123")
    parte = t.Parte(importe="100.00", cuenta_contable="4212100", glosa="Su parte")

    assert t.glosa_de_movimiento(m, i, parte) == "SU PARTE", "la de la parte manda sobre todo"
    assert t.glosa_de_movimiento(m, i) == "PAGO FACT F001-123", "y la de la imputación sobre el banco"
    assert t.glosa_de_movimiento(m) == "TRANSFERENCIA A CUENTAS DE TERCEROS", "el texto del banco, si no hay más"
    sin_texto = t.Movimiento(cuenta="bbva-soles", fecha="2026-03-14", importe="1.00", sentido="cargo",
                             contraparte_nombre="Proveedor SAC")
    assert t.glosa_de_movimiento(sin_texto) == "PROVEEDOR SAC", "y el tercero antes que una celda vacía"

    # **Sin cortar**: el largo lo decide cada destino (CONCAR corta a 40 y a 30, STARSOFT tiene su `LARGO_GLOSA`).
    larga = t.ImputacionDeMovimiento(cuenta_contable="4212100", glosa="x" * 200)
    assert len(t.glosa_de_movimiento(m, larga)) == 200


def test_la_glosa_y_el_efecto_leen_un_diccionario_igual_que_un_objeto():
    """**Las dos formas circulan, y aquí no circulaban.** Un ERP manda diccionarios de JSON; dentro del motor
    viajan objetos. `cuadre.cuadra`, `cuentas.sin_cuenta_declarada` y `extractos.por_cuenta` ya aceptaban las
    dos, y estas tres funciones **no** — leían con `getattr`, que sobre un dict no encuentra nada y devuelve el
    valor por defecto sin levantar nada.

    Lo que eso producía era lo contrario exacto de para lo que existe la glosa (revisión de consistencia que
    pidió John, 11-oct-2026): con una imputación en forma de dict, **la glosa que el contador decidió se perdía
    y salía al libro el texto crudo del banco** — literalmente el «TRANSFERENCIA A CUENTAS DE TERCEROS» que la
    enmienda 0029 existe para evitar—, y con un movimiento en forma de dict salía **vacío**, rompiendo la
    promesa de que ninguna línea sale sin glosa. En silencio las dos veces.

    Lo que lo mantuvo vivo: los casos de arriba construyen objetos en todas sus ramas. Por eso éste no los
    construye en ninguna.
    """
    m = {"cuenta": "bbva-soles", "fecha": "2026-03-14", "importe": "12282.60", "sentido": "cargo",
         "descripcion": "Transferencia a cuentas de terceros", "contraparte_nombre": "Proveedor SAC"}

    assert t.glosa_de_movimiento(m, {"glosa": "Pago fact F001-123"}) == "PAGO FACT F001-123", (
        "la decisión del contador manda sobre el texto del banco, venga como venga")
    assert t.glosa_de_movimiento(m) == "TRANSFERENCIA A CUENTAS DE TERCEROS", "y el respaldo sigue siendo el banco"
    assert t.glosa_de_movimiento(m, {"glosa": "De la imputación"},
                                 {"glosa": "De la parte", "importe": "1.00", "cuenta_contable": "6312"}) ==         "DE LA PARTE"

    # `efecto` es una propiedad DERIVADA, así que aquí no basta leer un campo: el movimiento se normaliza. Antes
    # daba `AttributeError` —sin `clave`, o sea fuera del contrato de errores— mientras su imputación sí se
    # normalizaba dos líneas más arriba, en la misma función.
    assert t.efecto_de(m) == "salida"
    assert t.efecto_de(m, {"cuenta_propia": "bbva-dolares"}) == "transferencia"


def test_la_imputacion_encuentra_un_movimiento_que_llega_como_diccionario():
    """El tercero de la misma familia: `leer` buscaba el `id_externo` con `getattr`, así que con movimientos en
    forma de dict **no encontraba ninguno** y rechazaba las llaves con un mensaje que decía lo contrario de lo
    que pasaba: «habla de movimientos que no están», y estaban.

    Un diagnóstico que acusa en falso es peor que uno que calla: manda a buscar el error donde no está."""
    movimientos = [{"cuenta": "bbva-soles", "fecha": "2026-03-14", "importe": "500.00", "sentido": "cargo",
                    "id_externo": "mov-1"}]
    leidas = t.leer_imputaciones({"mov-1": {"cuenta_contable": "6312"}}, movimientos)
    assert leidas["mov-1"].cuenta_contable == "6312"

    # Y la puerta sigue cerrada para lo que de verdad no está: una llave mal escrita deja ese movimiento sin su
    # cuenta y sin aviso, que es la clase de error que no se ve hasta el cierre.
    with pytest.raises(t.ImputacionInvalida, match="mov-2"):
        t.leer_imputaciones({"mov-2": {"cuenta_contable": "6312"}}, movimientos)

    # El reparto se sigue exigiendo exacto aunque el movimiento llegue como dict: su importe también se leía
    # con `getattr`, así que el tope que esto defiende viajaba en `None`.
    with pytest.raises(t.ImputacionInvalida, match="tiene que ser exacto"):
        t.leer_imputaciones({"mov-1": {"reparto": [{"importe": "499.00", "cuenta_contable": "6312"}]}}, movimientos)


def test_un_reparto_lleva_una_glosa_por_parte():
    """**El argumento que decide dónde vive la glosa.** Un cargo que paga tres facturas se reparte en tres
    partes, y cada una va a su cuenta con su propio texto: eso es la «Glosa Detalle» de CONCAR, mientras la de
    la imputación es su «Glosa Principal». En el movimiento no cabrían tres."""
    from contaperu import api

    doc = documento_de_tesoreria(
        movimientos=[mov(importe="4500.00", sentido="cargo", id_externo="mov-882").a_dict()],
        imputaciones_de_movimientos={"mov-882": {"reparto": [
            {"importe": "3000.00", "cuenta_contable": "4212100", "glosa": "Pago F001-123"},
            {"importe": "1500.00", "cuenta_contable": "4212100", "glosa": "Pago F001-124"}]}})
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert r["imputados"] == 1 and r["avisos"] == []

    suya = t.ImputacionDeMovimiento.de(doc["imputaciones_de_movimientos"]["mov-882"])
    el_mov = t.Movimiento.de_dict(doc["movimientos"][0])
    assert [t.glosa_de_movimiento(el_mov, suya, p) for p in suya.reparto] == ["PAGO F001-123", "PAGO F001-124"]
    # Y la glosa NO compite con el reparto: no contesta «cuál es la contrapartida», así que conviven.
    con_las_dos = t.ImputacionDeMovimiento(glosa="Pago a proveedores", reparto=[
        {"importe": "3000.00", "cuenta_contable": "4212100"}])
    assert con_las_dos.glosa == "Pago a proveedores" and len(con_las_dos.reparto) == 1


def test_una_cuenta_sin_numero_ni_CCI_VALE_para_registrar_y_lo_dice():
    """Lo destapó John integrando (11-oct-2026), y lo delataba esta misma clase.

    El docstring de `CuentaBancaria` dice que lo mínimo es «de quién es la cuenta, en qué moneda, y con qué
    cuenta contable se asienta» — y el código exigía ADEMÁS un número o un CCI, así que era más estricto que
    lo que él mismo declara. Nadie lo probaba, y por eso la contradicción sobrevivió.

    Los dos son ciertos, para cosas distintas. Para **registrar** un pago y **asentarlo** basta lo del
    docstring: la 104 sale de la cuenta y la contrapartida de la imputación. El número y el CCI hacen falta
    para **casar** la cuenta con un archivo del banco, que es conciliar — el hito D3, que no existe todavía.
    Rechazar por adelantado un dato que solo necesita un paso que nadie puede dar aún obligaba a inventarse un
    número para poder declarar una cuenta, que es exactamente lo que un contrato no debe forzar.

    Así que avisa y no para, con el mismo trato que la cuenta contable que falta: **lo que impide un paso
    POSTERIOR se dice, no se para**.
    """
    from contaperu import api

    cuenta = t.CuentaBancaria(id="bbva-pen", banco="BBVA", moneda="PEN", cuenta_contable="104101")
    assert (cuenta.numero, cuenta.cci) == ("", ""), "se acepta sin identificador"

    r = api.validar_cuentas_bancarias([{"id": "bbva-pen", "banco": "BBVA", "moneda": "PEN",
                                        "cuenta_contable": "104101"}])
    codigos = [a["codigo"] for a in r["avisos"]]
    assert codigos == ["CUENTA_BANCARIA_SIN_IDENTIFICADOR"], codigos
    assert "casarla" in r["avisos"][0]["texto"].lower(), "y dice qué es lo que NO se podrá hacer"
    assert r["cuantas"] == 1, "pero la cuenta entra en el maestro"

    # Con su número, ni aviso: lo que faltaba era el identificador, no otra cosa.
    con_numero = api.validar_cuentas_bancarias([{"id": "bbva-pen", "banco": "BBVA", "moneda": "PEN",
                                                 "cuenta_contable": "104101", "numero": "0119-9900-0000000100"}])
    assert con_numero["avisos"] == []


def test_lo_que_SIGUE_parando_una_cuenta_bancaria():
    """El aviso nuevo no abre la puerta a todo: sin `id` no hay con qué nombrarla, un CCI de diecinueve
    dígitos es uno mal copiado y una moneda fuera del catálogo no se puede asentar en ninguna parte."""
    for mal, porque in (
        ({"banco": "BBVA", "moneda": "PEN"}, "necesita un `id`"),
        ({"id": "x", "moneda": "PEN", "cci": "0" * 19}, "CCI inválido"),
        ({"id": "x", "moneda": "XXX", "numero": "123"}, "Moneda inválida"),
    ):
        with pytest.raises(t.CuentaInvalida):
            t.CuentaBancaria(**mal)
