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
    return {"open_accounting": "2.0",
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

def test_la_api_cuadra_cada_cuenta_y_deduce_el_saldo_inicial_si_nadie_lo_declara():
    """El saldo inicial está en la cabecera del extracto, así que es de quien lee el archivo. Si no viene, se
    deduce del primer movimiento y la cadena se comprueba de la segunda línea en adelante — **y se dice cuál fue
    cuál**, que es lo que impide creerse un cuadre que solo se comprobó a medias.

    No es un consuelo: el caso real que destapó el ITF rompía justo en la segunda fila del mes."""
    from contaperu import api

    doc = documento_de_tesoreria(movimientos=[
        mov(referencia="000001", saldo="1500.00").a_dict(),
        mov(referencia="000002", importe="200.00", sentido="cargo", itf="0.20", saldo="1299.80").a_dict()])
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])

    assert len(r["cuadre"]) == 1
    uno = r["cuadre"][0]
    assert uno["cuadra"] and uno["cuenta"] == "bbva-soles"
    assert uno["saldo_inicial"] == "1000.00", "se deduce del primer movimiento y su saldo corrido"
    assert uno["saldo_final"] == "1299.80" and not uno["saldo_inicial_declarado"]
    assert uno["cuenta_contable"] == "10411100", "sale de la cuenta declarada, no de una suposición"
    assert r["avisos"] == []

    # Declarándolo, la primera línea también se comprueba — y si está mal, se dice.
    malo = api.revisar_tesoreria(doc, [cuenta().a_dict()], saldos_iniciales={"bbva-soles": "1.00"})
    assert not malo["cuadre"][0]["cuadra"] and malo["cuadre"][0]["saldo_inicial_declarado"]
    assert any(a["codigo"] == "EXTRACTO_NO_CUADRA" for a in malo["avisos"])


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
    assert not any(a["codigo"] == "EXTRACTO_NO_CUADRA" for a in r["avisos"])
    # Un pago no trae saldo, así que su cuadre se mira en relativo y no se rompe por no tenerlo.
    assert r["cuadre"][0]["cuadra"]


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

def test_cada_driver_rechaza_un_libro_de_tesoreria_nombrando_los_que_si_lleva():
    """La degradación que el estándar promete para un tipo de libro, y que **no estaba ocurriendo**: los ocho
    drivers contestaban «No hay comprobantes que procesar», que es engañoso — la razón verdadera es que ese destino
    no lleva ese libro.

    No era una falta de mensaje, `drivers.formato_de` ya lo tenía bien: era un orden de comprobaciones, y se
    llamaba después de preparar. Nadie lo había notado porque hasta el 10-oct-2026 no existía ningún libro del
    catálogo fuera de los dos que todos los drivers llevan. El tercero lo destapó."""
    from contaperu import api, drivers

    doc = documento_de_tesoreria(movimientos=[mov().a_dict()])
    for nombre in sorted(drivers.DE_SERIE):
        with pytest.raises(drivers.LibroQueElDestinoNoLleva) as e:
            api.exportar(doc, driver=nombre, configuracion={})
        assert e.value.tipo == "tesoreria" and e.value.driver == nombre
        assert "compra" in str(e.value) and "venta" in str(e.value), "tiene que decir qué libros SÍ lleva"
    # Y sigue siendo un `ValueError`, que es lo que era antes: quien lo atrape por ahí no se rompe.
    assert issubclass(drivers.LibroQueElDestinoNoLleva, ValueError)


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


def test_el_saldo_declarado_viaja_en_el_documento_y_se_comprueba():
    """Hasta la 2.0 el saldo inicial entraba **solo como argumento**, así que un documento guardado no se podía
    volver a comprobar: su cuadre dependía de un dato que no viajaba con él. Es lo que la enmienda 0008 arregló
    para las imputaciones — «el archivo explica su propio asiento»."""
    from contaperu import api

    doc = documento_de_tesoreria(movimientos=un_mes(), extractos=[extracto()])
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    uno = r["cuadre"][0]
    assert uno["cuadra"] and uno["saldo_inicial_declarado"] and uno["saldo_final_declarado"]
    assert uno["saldo_inicial"] == "1000.00" and uno["saldo_final"] == "1299.80"
    assert r["avisos"] == []


def test_el_saldo_final_declarado_es_el_segundo_control_y_antes_era_inalcanzable():
    """**El hueco que esto cierra.** `tesoreria.cuadra` acepta un `saldo_final` desde la 8.2 y `revisar_tesoreria`
    **no se lo pasaba nunca**, así que el segundo control estaba escrito y no se podía alcanzar por la api.

    Y vale por sí mismo: una lectura puede pasar la cadena de saldos corridos y fallar el total. Si se pierde la
    ÚLTIMA línea del mes, las demás encadenan perfectamente entre sí — es justo lo que produce un lector de PDF."""
    from contaperu import api

    sin_la_ultima = documento_de_tesoreria(movimientos=un_mes()[:1], extractos=[extracto()])
    r = api.revisar_tesoreria(sin_la_ultima, [cuenta().a_dict()])
    uno = r["cuadre"][0]
    assert not uno["cuadra"], "el saldo final declarado delata la línea que falta"
    assert uno["saldo_final"] == "1500.00" and uno["saldo_final_declarado"]
    assert any(a["codigo"] == "EXTRACTO_NO_CUADRA" for a in r["avisos"])
    # Y sin cabecera la misma lectura pasa: la cadena de la única línea que queda encadena con ella misma.
    assert api.revisar_tesoreria(documento_de_tesoreria(movimientos=un_mes()[:1]),
                                 [cuenta().a_dict()])["cuadre"][0]["cuadra"]


def test_los_dos_totales_de_la_cabecera_se_contrastan():
    """La tercera comprobación, y la que caza lo que el saldo final no puede: **un cargo y un abono perdidos por el
    mismo importe dejan el saldo igual**. Los totales no."""
    from contaperu import api

    doc = documento_de_tesoreria(movimientos=un_mes(),
                                 extractos=[extracto(total_cargos="900.00", saldo_final=None)])
    r = api.revisar_tesoreria(doc, [cuenta().a_dict()])
    assert any(a["codigo"] == "TOTAL_DECLARADO_NO_COINCIDE" for a in r["avisos"])
    assert any("900.00" in a["texto"] and "200.00" in a["texto"] for a in r["avisos"])
    # Y el cuadre en sí no se rompe por eso: son dos cosas distintas y se dicen aparte.
    assert r["cuadre"][0]["cuadra"]


def test_el_mismo_saldo_por_las_dos_vias_se_rechaza():
    """El precedente exacto es `imputaciones` contra `imputacion`: dos vías para el mismo dato necesitan una regla
    de cuál gana, y la regla honesta es que no haya dos."""
    from contaperu import api
    from contaperu.errores import DocumentoInvalido

    doc = documento_de_tesoreria(movimientos=un_mes(), extractos=[extracto()])
    with pytest.raises(DocumentoInvalido) as e:
        api.revisar_tesoreria(doc, [cuenta().a_dict()], saldos_iniciales={"bbva-soles": "1000.00"})
    assert "bbva-soles" in str(e.value) and "cuál gana" in str(e.value)
    # Una cabecera SIN saldo inicial y el argumento sí conviven: no hay dos datos, hay uno.
    sin_saldo = documento_de_tesoreria(movimientos=un_mes(), extractos=[extracto(saldo_inicial=None)])
    r = api.revisar_tesoreria(sin_saldo, [cuenta().a_dict()], saldos_iniciales={"bbva-soles": SALDO_ANTERIOR})
    assert r["cuadre"][0]["cuadra"] and r["cuadre"][0]["saldo_inicial_declarado"]


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
