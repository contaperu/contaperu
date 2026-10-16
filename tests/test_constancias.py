"""El primer lector de tesorería: una constancia de pago convertida en movimientos (D2a).

`tesoreria/` llevaba desde la 11.x con el contrato entero y **ningún lector**, por una razón escrita en su propio
módulo: «cada parser entra con su archivo delante y su fixture anonimizado». Éste entró con 80 PDF reales de un
contribuyente peruano de 2026, de dos bancos y cinco formatos, de los que **58 dan texto legible** —los otros 22
traen fuentes sin tabla ToUnicode y salen en glifos, que es por lo que `Movimiento.origen` ya distinguía
`pdf_texto` de `vision`—. Los 58 se leen sin un fallo; lo que entra aquí son seis fixtures anonimizados con su
estructura y sus importes, y los RUC y los nombres de la batería.

Lo que estos casos fijan, y cada uno es una regla que un papel real enseñó:

- **Recibe texto, nunca un PDF.** Misma frontera que `sire_txt.py`, misma razón: el núcleo no toca disco.
- **Devuelve una lista.** De un papel salen hasta tres movimientos, porque la comisión del banco es su propio
  movimiento (enmienda 0028) y el banco la escribe en su propio renglón.
- **Los importes se cuadran, y si no cuadran no sale nada.** Es lo que convierte «leí un PDF» en «lo leí bien».
- **El maestro de cuentas no es opcional**, porque `Movimiento.cuenta` es un `id` y no un número.
- **Lo que el papel no dice, el lector no lo pone**: ni el ITF, ni una sigla de comprobante, ni un banco que no
  reconoció.
"""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from contaperu import api, aplicaciones as ap
from contaperu.modelo import Comprobante
from contaperu.tesoreria import CuentaBancaria, constancias
from contaperu.tesoreria.constancias import ConstanciaIlegible

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "constancias"

#: El maestro del contribuyente: las cuatro cuentas que los seis fixtures cargan, con la 104 que el motor no
#: deriva. Los números son inventados; lo que importa es que el papel los nombra de otra forma que el maestro.
MAESTRO = (CuentaBancaria(id="BCP-SOLES", banco="BCP", numero="191-1111111-0-11", moneda="PEN",
                          cuenta_contable="104101"),
           CuentaBancaria(id="BCP-DOLARES", banco="BCP", numero="191-3333333-1-33", moneda="USD",
                          cuenta_contable="104102"),
           CuentaBancaria(id="BBVA-SOLES", banco="BBVA", numero="0119-9900-0000000100", moneda="PEN",
                          cuenta_contable="104201"),
           CuentaBancaria(id="BBVA-DOLARES", banco="BBVA", numero="01199900000000000300", moneda="USD",
                          cuenta_contable="104202"))


def texto(nombre: str) -> str:
    return (FIXTURES / f"{nombre}.txt").read_text(encoding="utf-8")


def leer(nombre: str, cuentas=MAESTRO) -> list:
    return constancias.leer(texto(nombre), cuentas)


# --- reconocer, que es lo primero que hay que hacer con un montón de PDF ------------------------------------------

def test_los_cinco_formatos_se_reconocen_por_lo_que_el_banco_escribe():
    """La seña de cada formato es un encabezado que ninguno de los otros cuatro escribe: o está o no está."""
    for nombre in ("bcp_terceros", "bcp_cce", "bcp_documentos", "bbva_operacion", "bbva_masivos"):
        assert constancias.reconocer(texto(nombre)) == nombre
    # El de interés es del mismo formato: lo que cambia es lo que trae la tabla, no el papel.
    assert constancias.reconocer(texto("bcp_documentos_con_interes")) == "bcp_documentos"


def test_lo_que_no_es_una_constancia_se_aparta_sin_que_sea_un_error():
    """Quien integra pasa una carpeta entera, y los que salieron en glifos no son un fallo: son otra cosa.

    Por eso `reconocer` devuelve vacío en vez de levantar, y `leer` sí levanta: son dos preguntas distintas."""
    assert constancias.reconocer("/0 /1 /2 /3 glifos sin tabla ToUnicode") == ""
    assert constancias.reconocer("") == ""
    with pytest.raises(ConstanciaIlegible, match="no es de ninguno de los formatos"):
        constancias.leer("una factura cualquiera", MAESTRO)


# --- el BCP -------------------------------------------------------------------------------------------------------

def test_una_transferencia_a_terceros_es_un_cargo_con_su_cuenta_del_maestro():
    """El caso simple, y el más frecuente de los 80: 29 papeles. Un cargo y nada más."""
    movimientos = leer("bcp_terceros")
    assert len(movimientos) == 1
    pago = movimientos[0]
    assert (pago.sentido, pago.importe, pago.moneda) == ("cargo", Decimal("7029.60"), "PEN")
    assert pago.cuenta == "BCP-SOLES", "apunta al id del maestro, no al número del papel"
    assert pago.referencia == "00229545" and pago.origen == "pdf_texto"
    assert pago.contraparte_nombre == "PROVEEDOR UNO SAC"
    assert pago.datos_originales["cuenta_cargo"] == "191-1111111-0-11"


def test_el_tipo_de_la_operacion_sale_entero_y_no_la_etiqueta_de_al_lado():
    """La trampa del texto sin columnas: «Tipo de operación» va en un renglón y «Estado» en el siguiente.

    Admitir el salto de línea devolvía `Estado` como tipo de la operación — un dato falso con pinta de bueno. Por
    eso `junto_a` no cruza el salto, y el renglón se busca por lo que dice."""
    assert leer("bcp_terceros")[0].descripcion == "Transferencia a cuentas de terceros BCP local"
    assert leer("bcp_cce")[0].descripcion == "Transferencia a otros bancos locales - Diferida"


def test_la_comision_del_cce_es_su_propio_movimiento_y_no_un_descuento():
    """La enmienda 0028, escrita por el banco en su propio renglón: `Comisión CCE` aparte del monto.

    Y lo que suman los dos es lo que el papel llama monto total, que es el cuadre."""
    pago, comision = leer("bcp_cce")
    assert (pago.importe, comision.importe) == (Decimal("210150.23"), Decimal("4.30"))
    assert pago.importe + comision.importe == Decimal("210154.53"), "el monto total del papel"
    assert comision.descripcion == "Comisión CCE"
    assert comision.cuenta == pago.cuenta == "BCP-SOLES"
    assert comision.datos_originales["concepto"] == "comision_cce"
    # El beneficiario sí trae RUC en este formato, y se traduce al código 6 de la Tabla 1.
    assert (pago.contraparte_tipo_doc, pago.contraparte_doc) == ("6", "20607777773")
    assert pago.contraparte_nombre == "PROVEEDOR DOS EIRL"


def test_el_titular_del_beneficiario_no_se_confunde_con_el_del_contribuyente():
    """El papel trae dos «Titular» y con el texto desordenado el de arriba sale como etiqueta suelta.

    Preguntar por el primero devolvía «Cuenta». Se busca dentro del bloque del beneficiario y no en todo el
    texto, que es la única forma de no equivocarse de empresa."""
    assert leer("bcp_cce")[0].contraparte_nombre == "PROVEEDOR DOS EIRL"


def test_los_tres_importes_del_cce_se_identifican_por_aritmetica_y_no_por_posicion():
    """La tabla del BCP es de dos columnas y el texto las intercala, así que el orden no se puede confiar.

    Lo que sí: de tres números uno es la suma de los otros dos, y eso no depende de cómo se extrajo el texto.
    Este caso lo demuestra barajándolos: sale lo mismo."""
    original = texto("bcp_cce")
    barajado = original.replace("S/ 4.30\nS/ 210,154.53\nS/ 210,150.23",
                                "S/ 210,150.23\nS/ 4.30\nS/ 210,154.53")
    assert barajado != original
    pago, comision = constancias.leer(barajado, MAESTRO)
    assert (pago.importe, comision.importe) == (Decimal("210150.23"), Decimal("4.30"))


def test_si_los_tres_importes_no_cuadran_no_sale_nada():
    """La comprobación de la lectura. Un pago mal leído entra al libro y nadie lo nota: eso es lo que se evita."""
    roto = texto("bcp_cce").replace("S/ 210,154.53", "S/ 999,999.99")
    with pytest.raises(ConstanciaIlegible, match="no cuadran"):
        constancias.leer(roto, MAESTRO)


def test_la_tabla_de_documentos_sale_como_referencias_cada_una_con_su_importe():
    """El formato que destraba lo que se pedía: **el banco declarando qué documentos cancela el cargo**.

    Son las `aplicaciones` sin que nadie las teclee. Tres documentos de tres proveedores distintos en un solo
    cargo, y cada fila con su importe — que es N a N y por línea, como la investigación de los ocho sistemas."""
    movimientos = leer("bcp_documentos")
    assert len(movimientos) == 1
    pago = movimientos[0]
    assert (pago.importe, pago.moneda, pago.cuenta) == (Decimal("27006.60"), "USD", "BCP-DOLARES")
    assert len(pago.referencias) == 3
    assert [r.importe for r in pago.referencias] == [Decimal("15579.93"), Decimal("1125.27"), Decimal("10301.40")]
    assert sum(r.importe for r in pago.referencias) == pago.importe
    assert all(r.clase == "libre" for r in pago.referencias), "sin tipo ni serie no es un `comprobante`"
    assert "PROVEEDOR UNO SAC" in pago.referencias[0].datos["texto"]
    assert "484326" in pago.referencias[0].datos["texto"], "el número con el que el banco conoce el papel"
    assert pago.contraparte_nombre == "", "tres proveedores en un cargo: ninguno es la contraparte"


def test_el_cargo_de_un_pago_con_documentos_lleva_el_interes_dentro():
    """Lo que enseñaron los dos únicos papeles con interés de los siete, que no lo declaran igual.

    En una letra el `Monto` de arriba lo incluye; en una factura, no. Con un papel de cada clase no hay regla que
    escribir, así que el lector usa la columna TOTAL —que no es ambigua— y el `Monto` declarado solo le sirve de
    cuadre. Aquí: 76 167,55 de monto más 89,25 de interés salen de la cuenta como 76 256,80."""
    pago = leer("bcp_documentos_con_interes")[0]
    assert pago.importe == Decimal("76256.80")
    assert pago.datos_originales["monto_declarado"] == "76167.55"
    assert pago.referencias[0].importe == Decimal("76256.80")


def test_una_fila_perdida_de_la_tabla_se_delata():
    """La tabla se corta entre páginas, y ahí es donde se pierde una fila. El cuadre contra el `Monto` declarado
    es lo que lo dice; si no, saldría un cargo de menos que cuadra consigo mismo."""
    sin_una = texto("bcp_documentos").replace(
        "PROVEEDOR DOS EIRL F7991345 754_3574_6 19/09/2026 $ 1,125.27 $ 0.00 $ 1,125.27\n", "")
    with pytest.raises(ConstanciaIlegible, match="falta alguna fila"):
        constancias.leer(sin_una, MAESTRO)


def test_la_orden_de_pago_interna_viaja_como_referencia_libre():
    """`OP 12028` no es un documento tributario: es la llave con la que la empresa une el pago a lo que paga.

    No necesita clase propia —`libre` existe para esto— y **es opcional**: de los 38 papeles del BCP solo 7 la
    traen, así que un papel sin ella no es un papel incompleto."""
    assert leer("bcp_terceros")[0].referencias[0].datos["texto"] == "OP 12028"
    assert leer("bcp_documentos")[0].referencias[0].clase == "libre"


# --- el BBVA ------------------------------------------------------------------------------------------------------

def test_una_operacion_suelta_del_bbva_trae_su_beneficiario_con_cuenta_y_nombre():
    pago = leer("bbva_operacion")[0]
    assert (pago.sentido, pago.importe, pago.moneda) == ("cargo", Decimal("873.85"), "USD")
    assert pago.cuenta == "BBVA-DOLARES" and pago.referencia == "000002267"
    assert pago.contraparte_nombre == "PROVEEDOR UNO SAC"
    assert pago.datos_originales["cuenta_destino"] == "01199900000000000400"


def test_una_planilla_es_un_cargo_con_n_abonos_y_sus_comisiones_aparte():
    """El caso que obliga a que un lector devuelva una lista: un papel, dos movimientos y dos abonos dentro.

    `TOTAL CARGADO` es el cuadre que el propio banco pone, y el lector lo exige: los abonos más las comisiones."""
    cargo, comision = leer("bbva_masivos")
    assert (cargo.importe, comision.importe) == (Decimal("3195.00"), Decimal("5.00"))
    assert cargo.importe + comision.importe == Decimal("3200.00"), "el TOTAL CARGADO del papel"
    assert comision.descripcion == "Comisión Interbancaria"
    assert cargo.cuenta == comision.cuenta == "BBVA-SOLES"
    # La comisión por otra plaza es cero en este papel, y un movimiento de cero no se inventa.
    assert len([m for m in leer("bbva_masivos")]) == 2
    abonos = [r for r in cargo.referencias if r.importe]
    assert [r.importe for r in abonos] == [Decimal("2500.00"), Decimal("695.00")]
    assert sum(r.importe for r in abonos) == cargo.importe


def test_el_banco_del_abono_se_recorta_con_la_lista_que_el_propio_papel_trae():
    """La fila escribe el banco y el titular pegados —`INTERBANK PERSONA DE PRUEBA UNO`— sin nada en medio.

    No se adivina dónde acaba uno: el documento trae al pie la lista de entidades con las que el BBVA opera, y es
    con ésa con la que se parte. `banco_del_cci` no sirve, porque devuelve el código de tres dígitos y no el
    nombre — el repositorio no traduce ese código, que no tiene catálogo con fuente."""
    cargo = leer("bbva_masivos")[0]
    primero = cargo.referencias[0].datos["texto"]
    assert primero.startswith("PERSONA DE PRUEBA UNO"), "el titular, sin el banco delante"
    assert "INTERBANK" in primero
    assert "aviso" not in cargo.datos_originales, "los dos bancos del papel estaban en su pie"


def test_la_letra_del_documento_se_traduce_con_la_tabla_1_de_sunat():
    """Dos catálogos, cada uno con su fuente: la letra la declara el PDF del BBVA (`R` RUC, `L` DNI, `P`
    pasaporte, `E` carné de extranjería, `M` identidad militar) y el código, la Tabla 1 del Anexo 1 de la
    RS 112-2021, que es la que el comprobante ya usa.

    La identidad militar no existe en la tabla de SUNAT y sale como `0` (Otros): es lo que hay, y es mejor que
    inventar un código."""
    from contaperu.tesoreria.constancias.bbva import DOCUMENTO_POR_LETRA

    assert DOCUMENTO_POR_LETRA == {"R": "6", "L": "1", "P": "7", "E": "4", "M": "0"}
    # El titular del primer abono viene con `L - 41074220`: un DNI.
    assert "L-41074220" in leer("bbva_masivos")[0].referencias[0].datos["texto"]


def test_si_el_total_cargado_no_cuadra_con_los_abonos_mas_las_comisiones_no_sale_nada():
    roto = texto("bbva_masivos").replace("TOTAL CARGADO 3,200.00", "TOTAL CARGADO 9,999.00")
    with pytest.raises(ConstanciaIlegible, match="TOTAL CARGADO"):
        constancias.leer(roto, MAESTRO)


def test_una_planilla_sin_su_tabla_de_abonos_se_lee_igual():
    """En tres de los cuatro papeles reales la tabla no viene: está detrás de un «Ver contenido de la planilla»
    que no se despliega al pasar el PDF a texto. Eso no es un error — el cargo y su comisión están igual, y lo
    que el papel no dice el lector no lo pone."""
    sin_tabla = texto("bbva_masivos")
    for fila in ("1 00399900000000000500   INTERBANK PERSONA DE PRUEBA UNO L - 41074220 2,500.00 0 ABONO ENVIADO",
                 "2 00999900000000000200   Scotiabank PROVEEDOR DOS EIRL R - 20607777773 695.00 0 ABONO ENVIADO"):
        sin_tabla = sin_tabla.replace(fila, "")
    cargo, comision = constancias.leer(sin_tabla, MAESTRO)
    assert cargo.importe == Decimal("3195.00") and comision.importe == Decimal("5.00")
    assert not [r for r in cargo.referencias if r.importe], "sin tabla no hay abonos que referenciar"


def test_la_comision_no_lleva_la_referencia_del_pago_porque_seria_el_mismo_movimiento():
    """Lo cazó armar el asiento de los papeles reales, no leerlos — y por eso este test existe.

    `Movimiento.clave` es `(cuenta, referencia)` cuando hay referencia, porque «la del banco basta y sobra: es
    suya y no se repite dentro de una cuenta». Darle al cobro el número de operación del pago los convertía en
    **el mismo movimiento**, y el motor descartaba el segundo como repetido: de 61 movimientos leídos, tres no
    llegaban al asiento. La clave decía que eran repetidos, y la clave no se equivocaba.

    Tampoco se fabrica un número derivado: el banco no le dio ninguno a este cobro, e inventar una referencia
    bancaria es de la misma familia que inventar una sigla. El número de la operación de la que salió se queda en
    `datos_originales`, donde no miente sobre lo que es."""
    from contaperu.tesoreria import sin_duplicados

    for fixture in ("bcp_cce", "bbva_masivos"):
        pago, comision = leer(fixture)
        assert pago.referencia, "el pago sí lleva el número que le dio el banco"
        assert comision.referencia == "", f"{fixture}: la comisión no tiene número propio y no se le inventa"
        assert comision.datos_originales["operacion"] == pago.referencia
        assert pago.clave != comision.clave, f"{fixture}: dos movimientos, dos claves"
        entran, repetidos = sin_duplicados([pago, comision])
        assert len(entran) == 2 and not repetidos, f"{fixture}: los dos tienen que entrar"


def test_un_papel_con_comision_arma_dos_asientos_y_los_dos_cuadran():
    """El circuito entero sobre el formato que más piezas mueve: leer, imputar y asentar.

    Son dos asientos y no uno con cuatro líneas, porque son dos hechos: lo que se pagó y lo que el banco cobró.
    Y el efectivo que sale de la cuenta tiene que ser lo que dice el papel, comisión incluida."""
    movimientos = leer("bcp_cce")
    for i, m in enumerate(movimientos):
        m.id_externo = f"mov-{i}"

    mes = {"open_accounting": api.OPEN_ACCOUNTING,
           "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
                     "periodo": "202608", "tipo": "tesoreria"},
           "movimientos": [m.a_dict() for m in movimientos],
           "imputaciones_de_movimientos": {m.id_externo: {"cuenta_contable": "4212100", "glosa": "PAGO"}
                                           for m in movimientos}}
    configuracion = {"cuentas_bancarias": [{"id": "BCP-SOLES", "banco": "BCP", "numero": "191-1111111-0-11",
                                            "moneda": "PEN", "cuenta_contable": "104101"}]}
    respuesta = api.generar_asiento(mes, driver="asiento_contable", configuracion=configuracion)

    assert respuesta["_asiento"]["cuadre"]["cuadra"] is True
    assert respuesta["_asiento"]["lineas"] == 4, "dos hechos, dos asientos de dos líneas"
    del_efectivo = [ln for ln in respuesta["asiento"] if ln["cuenta"] == "104101"]
    assert sum(Decimal(ln["importe"]) for ln in del_efectivo) == Decimal("210154.53"), "el monto total del papel"
    assert all(ln["debe_haber"] == "H" for ln in del_efectivo), "de una cuenta de efectivo, un pago sale"


# --- el maestro de cuentas, que no es opcional --------------------------------------------------------------------

def test_sin_el_maestro_no_sale_un_movimiento_y_se_dice_qué_cuenta_falta():
    """`Movimiento.cuenta` es el `id` del maestro y el motor lo exige; hace bien, porque así lo que entra al libro
    apunta a una cuenta declarada con su 104 y su moneda, y no a unos dígitos que nadie reconoce.

    El mensaje dice el número tal cual salió del papel: es lo único que hace falta para declararla."""
    with pytest.raises(ConstanciaIlegible, match=r"191-1111111-0-11"):
        leer("bcp_terceros", cuentas=())


def test_la_misma_cuenta_escrita_de_dos_formas_es_la_misma_cuenta():
    """Lo enseñó el BBVA: la planilla escribe `0119-9900-0000000100` y la operación suelta mete dos dígitos de
    control en medio, `01199900000000000100`. Ninguna contiene a la otra, pero las dos acaban en el número de
    cuenta, que es lo que identifica. Ocho de los dieciséis papeles del BBVA venían así."""
    otra_forma = texto("bbva_masivos").replace("0119-9900-0000000100", "01199900000000000100")
    assert constancias.leer(otra_forma, MAESTRO)[0].cuenta == "BBVA-SOLES"


def test_una_cuenta_de_otro_contribuyente_no_casa_por_casualidad():
    """La regla de la cola no puede ser laxa: dos cuentas distintas no se declaran la misma por coincidir en
    unos pocos dígitos."""
    ajeno = (CuentaBancaria(id="OTRA", banco="BCP", numero="191-9999999-0-99", moneda="PEN",
                            cuenta_contable="104109"),)
    with pytest.raises(ConstanciaIlegible, match="no es ninguna de las que declara el maestro"):
        leer("bcp_terceros", cuentas=ajeno)


# --- de los comprobantes al pago, que es el circuito entero ------------------------------------------------------

def test_un_comprobante_y_su_constancia_dejan_el_pendiente_en_cero():
    """El extremo a extremo, y la pregunta que lo abrió: seleccionar comprobantes —que pueden venir del SIRE— y
    pasarlos a pago.

    Las tres piezas ya existían por separado y aquí se ven juntas: el comprobante entra por su camino de siempre,
    la constancia se lee del papel del banco, y lo que los une es una `aplicacion` con su importe. El pendiente
    **se deriva de la suma y no se guarda** (enmienda 0031), así que no hay ningún estado que mantener.

    Y el `origen` de la aplicación es `declarado` y no `manual` porque **lo afirma el papel**: el formato de
    documentos del BCP trae la tabla de lo que cancela. Para los otros cuatro formatos sería `manual` o
    `propuesto`, y una `propuesto` no movería este saldo."""
    pago = leer("bcp_documentos")[0]
    pago.id_externo = "mov-bcp-939049"

    # El primero de los tres documentos de la tabla: una factura de ese proveedor por su importe exacto.
    factura = {"tipo_cp": "01", "serie": "F001", "numero": "484326", "contraparte_doc": "20602222226",
               "contraparte_nombre": "PROVEEDOR UNO SAC", "fecha_emision": "2026-09-01",
               "fecha_vencimiento": "2026-09-17", "moneda": "USD", "base_gravada": "13203.33",
               "igv": "2376.60", "total": "15579.93"}
    aplicacion = {"de": {"clase": "movimiento", "datos": {"id_externo": pago.id_externo}},
                  "a": {"clase": "comprobante", "datos": {k: factura[k] for k in
                                                          ("tipo_cp", "serie", "numero", "contraparte_doc")}},
                  "importe": str(pago.referencias[0].importe), "moneda": "USD",
                  "fecha": "2026-09-17", "origen": "declarado"}

    ficha = ap.pendiente_de(Comprobante(**factura), ap.leer([aplicacion]))
    assert ficha["total"] == Decimal("15579.93")
    assert ficha["aplicado"] == Decimal("15579.93"), "lo que la constancia del banco dice que se le pagó"
    assert ficha["pendiente"] == Decimal("0.00")

    # Y por la puerta pública, que es la que usa quien integra.
    documento = {"open_accounting": api.OPEN_ACCOUNTING,
                 "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
                           "periodo": "202609", "tipo": "compra"},
                 "comprobantes": [factura], "aplicaciones": [aplicacion]}
    estado = api.estado_de_cuenta(documento)
    assert estado["documentos"][0]["pendiente"] == "0.00"
    assert estado["por_contraparte"][0]["contraparte_doc"] == "20602222226"
    assert estado["por_contraparte"][0]["pendiente"] == "0.00"
    assert not estado["avisos"], "nada que avisar: el comprobante y su pago viajan en el mismo documento"


def test_un_pago_parcial_deja_el_pendiente_que_falta_y_no_un_estado():
    """La otra mitad de la misma regla: lo que no se pagó entero no cambia de estado, cambia de número."""
    factura = {"tipo_cp": "01", "serie": "F001", "numero": "123", "contraparte_doc": "20602222226",
               "moneda": "PEN", "fecha_emision": "2026-05-02", "base_gravada": "5957.29", "igv": "1072.31",
               "total": "7029.60"}
    pago = leer("bcp_terceros")[0]
    pago.id_externo = "mov-bcp-00229545"
    mitad = {"de": {"clase": "movimiento", "datos": {"id_externo": pago.id_externo}},
             "a": {"clase": "comprobante", "datos": {k: factura[k] for k in
                                                     ("tipo_cp", "serie", "numero", "contraparte_doc")}},
             "importe": "4000.00", "moneda": "PEN", "fecha": "2026-05-15", "origen": "manual"}
    ficha = ap.pendiente_de(Comprobante(**factura), ap.leer([mitad]))
    assert ficha["pendiente"] == Decimal("3029.60")
    assert "estado" not in ficha


def test_el_lector_no_abre_ningun_archivo_ni_sale_a_la_red():
    """La frontera, dicha aquí además de en `test_frontera.py`: la firma recibe **texto**.

    Sacar el texto del PDF es de quien integra —con una librería o con un modelo—, y por eso 22 de los 80 papeles
    reales necesitan OCR y el motor no tiene nada que opinar sobre eso. Lo que sí: `origen` dice de dónde salió."""
    import inspect

    for funcion in (constancias.leer, constancias.reconocer):
        primero = list(inspect.signature(funcion).parameters)[0]
        assert primero == "texto"
    fuente = pathlib.Path(constancias.__file__).parent
    for modulo in fuente.glob("*.py"):
        codigo = modulo.read_text(encoding="utf-8")
        for prohibido in ("open(", "pathlib", "requests", "urllib", "datetime.now", "date.today"):
            assert prohibido not in codigo, f"{modulo.name} usa {prohibido}"
    assert all(m.origen == "pdf_texto" for m in leer("bcp_cce"))
