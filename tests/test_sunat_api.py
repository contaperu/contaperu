"""La API del SIRE como funciones puras: armar la petición, el estado de un ticket y el rechazo de SUNAT.

Todo lo de aquí se comprueba **contra el catálogo** (`contaperu/datos/sunat/sire_api.json`), que cita su manual en
cada operación. Lo que NO se comprueba aquí es la forma de una respuesta real, porque no hay ninguna guardada: ese
test entra el día que haya una captura, y hasta entonces el paquete no trae lectores de respuesta.
"""
from __future__ import annotations

import pytest

from contaperu import sunat
from contaperu.sunat.catalogo import CatalogoDelSireInvalido


def test_el_catalogo_trae_sus_operaciones_y_cada_una_cita_su_manual():
    """Si SUNAT añade una operación, aparece aquí sola. Y ninguna entra sin la fuente de la que sale: la ruta de una
    API ajena es una regla, y si cambia hay que poder ir a mirar de dónde salió. La duodécima, `registro_pedir`,
    entró el 01-nov-2026: bajar lo DECLARADO de un periodo, que no es la propuesta. Y en la 15.4.0 las tres que leen
    lo que SUNAT ve del periodo: las inconsistencias por comprobante, su resumen y el reporte de casillas del 621. Y en
    la 15.6.0, del manual y sin medir, las tres del registro de no domiciliados y el resumen de un periodo."""
    assert len(sunat.OPERACIONES) == 19
    assert set(sunat.OPERACIONES) == {
        "periodos", "propuesta_pedir", "ticket_consultar", "ticket_archivo", "propuesta_reemplazar",
        "propuesta_aceptar", "preliminar_registrar", "preliminar_eliminar", "excluidos", "no_incluidos", "constancia",
        "registro_pedir", "inconsistencias_comprobante", "inconsistencias_resumen", "casillas",
        "no_domiciliados_cargar", "no_domiciliados_eliminar_comprobante", "no_domiciliados_exportar_preliminar",
        "resumen"}
    for nombre, op in sunat.operaciones().items():
        assert op["fuente"].strip(), f"{nombre} no cita su manual"
        assert op["grada"] in sunat.GRADAS, f"{nombre} no declara con qué cuidado se la llama"


def test_las_gradas_reparten_las_diecinueve_en_trece_cuatro_y_dos():
    """La grada no es una anotación: decide si quien envía puede llamarla sola. Trece lecturas que no cambian nada,
    cuatro escrituras que tocan un mes y dos declarativas que declaran de verdad ante SUNAT. Y hace falta porque el
    SIRE **no tiene ambiente de pruebas**: toda prueba es contra producción."""
    por_grada: dict[str, list[str]] = {}
    for nombre in sunat.OPERACIONES:
        por_grada.setdefault(sunat.grada(nombre), []).append(nombre)
    assert {g: len(ns) for g, ns in por_grada.items()} == {"lectura": 13, "escritura": 4, "declarativa": 2}
    assert {"registro_pedir", "inconsistencias_comprobante", "inconsistencias_resumen", "casillas"} <= set(
        por_grada["lectura"])
    assert sorted(por_grada["declarativa"]) == ["preliminar_registrar", "propuesta_aceptar"]
    # Cargar el 080500 y quitar uno de sus comprobantes cambian lo que SUNAT tiene del mes, aunque no declaren.
    assert sorted(por_grada["escritura"]) == ["no_domiciliados_cargar", "no_domiciliados_eliminar_comprobante",
                                              "preliminar_eliminar", "propuesta_reemplazar"]


def test_el_registro_del_estandar_se_traduce_al_cod_libro_de_la_api():
    """Quien integra habla de compras y ventas; la API del SIRE, de 080000 y 140000. La traducción vive una vez."""
    assert sunat.cod_libro_de("compra") == "080000"
    assert sunat.cod_libro_de("venta") == "140000"
    assert sunat.libros()["080000"]["nombre"] == "RCE"
    with pytest.raises(CatalogoDelSireInvalido, match="compra, venta"):
        sunat.cod_libro_de("planilla")


def test_la_peticion_sale_con_su_metodo_su_url_y_sus_parametros():
    p = sunat.peticion("propuesta_pedir", registro="compra", periodo="202609", codTipoArchivo=0)
    assert p["metodo"] == "GET" and p["grada"] == "lectura" and p["devuelve"] == "ticket"
    assert p["url"].endswith("/rce/propuesta/web/propuesta/202609/exportacioncomprobantepropuesta")
    assert p["url"].startswith("https://api-sire.sunat.gob.pe/")
    assert p["params"] == {"codTipoArchivo": 0}
    # El código de proceso de ESTA operación, con el que luego se pide el archivo de su ticket.
    assert p["cod_proceso"] == "10"


def test_un_cero_es_un_valor_y_no_un_parametro_que_falta():
    """`codTipoArchivo` vale **0** para el TXT (`libros.cod_tipo_archivo`). Un `if not valor` lo trataría como
    ausente y pediría un dato que ya está — pasó al escribir esto, y por eso el test existe."""
    assert sunat.peticion("propuesta_pedir", registro="compra", periodo="202609",
                          codTipoArchivo=0)["params"]["codTipoArchivo"] == 0
    with pytest.raises(CatalogoDelSireInvalido, match="exige codTipoArchivo"):
        sunat.peticion("propuesta_pedir", registro="compra", periodo="202609")


def test_lo_que_se_rellena_solo_sale_del_catalogo_y_nada_mas():
    """Dos cosas se ponen sin pedirlas, y las dos las respalda el catálogo: el `codLibro`, que sale del registro, y
    el `codOrigenEnvio`, que vale 2 («servicio API») desde la v22 — el 1 de los manuales anteriores da 422."""
    p = sunat.peticion("ticket_consultar", registro="venta", perIni="202609", perFin="202609", page=1, perPage=20)
    assert p["params"]["codLibro"] == "140000"
    assert p["params"]["codOrigenEnvio"] == "2"
    # Y lo que no se rellena: `periodos` no exige nada, así que no se le inventa nada.
    assert sunat.peticion("periodos", registro="compra")["params"] == {}


def test_lo_declarado_se_pide_con_lo_que_se_midio_y_lo_demas_lo_pone_quien_llama():
    """`registro_pedir` (Compras v28 5.51) se midió contra producción el 01-nov-2026, y por eso lleva `verificado`. De
    ahí salen las dos cosas que la petición rellena sola —`codOrigen`, que es el `codOrigenEnvio` de las demás con
    otro nombre, y `codProceso` 70, el del ejemplo del manual y el que respondió, aunque su texto describa 00, 01 y
    02— y las dos que NO: `codMoneda`, que SUNAT exige aunque el manual no lo marque, y `lisPeriodos`. Esas las decide
    quien llama, y la petición se niega sin ellas en vez de inventarlas."""
    p = sunat.peticion("registro_pedir", registro="compra", periodo="202609",
                       codTipoArchivo=0, codMoneda="PEN", lisPeriodos="202609")
    assert p["metodo"] == "GET" and p["grada"] == "lectura" and p["devuelve"] == "ticket"
    assert p["url"].endswith("/rce/ajustesposteriores/web/ajustesposteriores/202609/solicitardescarga")
    assert p["params"] == {"codTipoArchivo": 0, "codMoneda": "PEN", "lisPeriodos": "202609",
                           "codOrigen": "2", "codProceso": "70"}
    assert p["cod_proceso"] == "70"
    assert sunat.verificado("registro_pedir", registro="compra") == "2026-11-01"
    with pytest.raises(CatalogoDelSireInvalido, match="exige codMoneda"):
        sunat.peticion("registro_pedir", registro="compra", periodo="202609", codTipoArchivo=0, lisPeriodos="202609")
    # Quien sabe otro código de proceso puede mandarlo: lo que se rellena no pisa lo que llega.
    assert sunat.peticion("registro_pedir", registro="compra", periodo="202609", codTipoArchivo=0, codMoneda="PEN",
                          lisPeriodos="202609", codProceso="02")["params"]["codProceso"] == "02"


def test_el_codigo_de_proceso_de_otra_operacion_no_se_rellena_en_ticket_archivo():
    """`ticket_archivo` también exige `codProceso`, pero el suyo es el de la operación que pidió el ticket, y eso solo lo
    sabe quien lo recuerda. Rellenarlo con cualquier cosa bajaría el archivo de otro proceso, o ninguno."""
    with pytest.raises(CatalogoDelSireInvalido, match="codProceso"):
        sunat.peticion("ticket_archivo", registro="compra", nomArchivoReporte="x.zip", codTipoArchivoReporte="00",
                       perTributario="202609", numTicket="20260300000188")
    # Y la propuesta declara su 10 pero no lo exige como parámetro: tampoco se le añade.
    assert "codProceso" not in sunat.peticion("propuesta_pedir", registro="compra", periodo="202609",
                                              codTipoArchivo=0)["params"]


def test_lo_declarado_de_ventas_es_otro_servicio_y_se_midio():
    """El RVIE tiene su propia descarga del registro (Ventas v29 5.27), y no se parece a la de compras: otra ruta, el
    periodo como `perTributario` en la consulta —su ruta no tiene hueco—, el libro como `codLibro`, sin `codMoneda` ni
    `lisPeriodos`, y el `codProceso` de su ejemplo, el 23 («Generar reporte Libro RVIE»). Entró del manual en la 15.2.0
    y se midió el mismo día (15.2.1): el 23 respondió a la primera y el archivo lo leyó el motor sin un cambio."""
    p = sunat.peticion("registro_pedir", registro="venta", periodo="202609", codTipoArchivo=0)
    assert p["url"].endswith("/rvierce/gestionlibro/web/registroslibros/descarga")
    assert p["params"] == {"codTipoArchivo": 0, "codLibro": "140000", "codOrigenEnvio": "2",
                           "perTributario": "202609", "codProceso": "23"}
    assert p["cod_proceso"] == "23"
    assert sunat.verificado("registro_pedir", registro="venta") == "2026-11-01"
    # Lo de compras no se le contagia: sin `codTipoArchivo` se niega, y no pide lo que solo pide el otro libro.
    with pytest.raises(CatalogoDelSireInvalido, match="exige codTipoArchivo"):
        sunat.peticion("registro_pedir", registro="venta", periodo="202609")


def test_lo_medido_se_pregunta_por_libro():
    """`verificado` es la pregunta de quien automatiza: el catálogo describe muchas operaciones que nadie ha visto
    responder. Medida entera, vale para los dos libros; medida por libro, solo para los que nombra."""
    assert sunat.verificado("periodos", registro="venta") == sunat.verificado("periodos", registro="compra") == "2026-11-01"
    assert sunat.verificado("propuesta_pedir", registro="compra") == ""
    assert sunat.verificado("registro_pedir", cod_libro="080000") == "2026-11-01"
    # Las dos de los tickets, por las que pasó la medición de lo declarado (15.2.1).
    assert sunat.verificado("ticket_consultar", registro="venta") == sunat.verificado("ticket_archivo") == "2026-11-01"


def test_lo_que_falta_en_un_libro_no_cae_al_valor_general():
    """Si una operación declara un campo POR LIBRO, el libro que no aparece no hereda el general: dos libros que no piden
    lo mismo no comparten lo que a uno le falta. Ninguna operación del catálogo tiene hoy los dos, así que se prueba
    con una hecha a mano —el día que alguna los tenga, ésta es la regla—."""
    from contaperu.sunat.peticiones import _del_libro

    op = {"verificado": "2026-01-01", "verificado_por_libro": {"080000": "2026-11-01"}}
    assert _del_libro(op, "verificado", "080000") == "2026-11-01"
    assert _del_libro(op, "verificado", "140000") is None
    assert _del_libro({"verificado": "2026-01-01"}, "verificado", "140000") == "2026-01-01"


def test_lo_que_va_por_libro_solo_habla_de_libros_con_ruta():
    """Un parámetro o una verificación de un libro sin ruta es un dato que nadie va a usar y que alguien va a creer: el
    catálogo no arranca así."""
    import copy

    from contaperu.sunat import catalogo

    tabla = copy.deepcopy(sunat.sire_api())
    tabla["operaciones"]["excluidos"]["verificado_por_libro"] = {"140000": "2026-11-01"}   # excluidos es solo de compras
    with pytest.raises(CatalogoDelSireInvalido, match="verificado_por_libro"):
        catalogo._valido(tabla)


def test_el_estado_de_un_periodo_dice_si_hay_algo_declarado_que_bajar():
    """Los códigos de `periodos` no los dice el manual: se midieron el 01-nov-2026 en cuatro ejercicios de un RUC real.
    El 01 y el 02 se llaman los dos «Presentado» y los dos cuentan; el 03 no. Y lo que decide algo es el que NO se
    conoce: cuenta como no presentado, porque lo seguro es seguir con la propuesta y no pedir un registro que quizá no
    existe — lo contrario de un ticket desconocido, que se sigue sondeando."""
    assert sunat.ESTADOS_DE_PERIODO == ("01", "02", "03")
    assert sunat.estado_de_periodo("01") == {"codigo": "01", "nombre": "Presentado", "presentado": True,
                                             "conocido": True}
    assert sunat.estado_de_periodo("02")["presentado"] is True
    assert sunat.estado_de_periodo(" 03 ") == {"codigo": "03", "nombre": "No Presentado", "presentado": False,
                                               "conocido": True}
    assert sunat.estado_de_periodo("09") == {"codigo": "09", "nombre": "", "presentado": False, "conocido": False}
    assert sunat.estado_de_periodo("")["presentado"] is False
    assert sunat.estado_de_periodo("_nota")["conocido"] is False


def test_una_ruta_por_libro_sin_saber_el_libro_se_niega_diciendo_como():
    """Varias de las doce tienen ruta distinta para el RCE y el RVIE, o solo para uno de los dos. Adivinar cuál es
    sería inventarse una llamada."""
    with pytest.raises(CatalogoDelSireInvalido, match='registro="compra"'):
        sunat.peticion("propuesta_pedir", periodo="202609", codTipoArchivo=0)
    with pytest.raises(CatalogoDelSireInvalido, match="necesita 'periodo'"):
        sunat.peticion("propuesta_pedir", registro="compra", codTipoArchivo=0)
    with pytest.raises(CatalogoDelSireInvalido, match="no tiene la operación"):
        sunat.peticion("generar_el_registro", registro="compra")


def test_lo_que_va_en_la_ruta_no_se_repite_en_la_consulta():
    """`indEliminar` es un hueco de la ruta de `preliminar_eliminar`, no un parámetro de la cadena de consulta.
    Mandarlo en los dos sitios es una llamada que SUNAT no reconoce."""
    p = sunat.peticion("preliminar_eliminar", registro="compra", periodo="202609", indEliminar=1)
    assert p["url"].endswith("/202609/1/eliminapreliminar")
    assert "indEliminar" not in p["params"] and p["params"] == {}


def test_el_422_trae_el_codigo_que_importa_DENTRO_de_errors():
    """La trampa del catálogo, y la razón de que esta función exista: «el `cod` de arriba es casi siempre 422 a
    secas y el código que importa vive dentro de `errors`. Mirar solo el de arriba hace que el 1024 no se reconozca
    nunca» — y el 1024 es la única idempotencia que la API ofrece."""
    e = sunat.clasificar_error("422", mensaje="", errores=[{"cod": "1024", "msg": "El archivo ya fue enviado"}],
                               operacion="propuesta_reemplazar")
    assert e.codigo == "1024" and e.idempotente and not e.reintentable
    assert e.codigos == ("422", "1024")
    # Mirar solo el de arriba daría «422», que no dice nada y que un contador no puede buscar en el manual.
    assert sunat.clasificar_error("422", errores=[{"cod": "1024"}]).codigo != "422"


def test_idempotente_y_reintentable_salen_de_la_tabla_del_catalogo():
    """«Esto ya se hizo» no es un fallo: son el 1024 (por nombre de archivo), el 1008 y el 1009. Y el único que el
    manual manda repetir es el 1351. Lo demás es validación de negocio y no se reintenta."""
    assert [sunat.clasificar_error("422", errores=[{"cod": c}]).idempotente for c in ("1024", "1008", "1009")] \
        == [True, True, True]
    assert sunat.clasificar_error("422", errores=[{"cod": "1351"}]).reintentable
    sin_salida = sunat.clasificar_error("422", errores=[{"cod": "1346"}])
    assert not sin_salida.idempotente and not sin_salida.reintentable
    # Y si SUNAT no manda mensaje, el del catálogo: el del 1346 dice el límite de 6 GB.
    assert "6 GB" in sin_salida.mensaje


def test_un_codigo_que_el_catalogo_no_conoce_se_dice_igual_y_no_se_pierde():
    """Una API ajena devuelve códigos nuevos. Se prefiere el interno sobre el «422» de arriba —es el que se busca en
    el manual— y se conservan todos los que llegaron."""
    e = sunat.clasificar_error("422", mensaje="Algo nuevo", errores=[{"cod": "9999", "msg": "x"}])
    assert e.codigo == "9999" and e.mensaje == "Algo nuevo" and e.codigos == ("422", "9999")
    assert not e.idempotente and not e.reintentable and not e.sin_datos


def test_sin_datos_es_un_vacio_y_no_un_fallo():
    """El 1070 —medido el 01-nov-2026 en un mes sin presentar— y el 1518 dicen que SUNAT no tiene nada de ese periodo:
    la petición estaba bien. Quien lee lo que SUNAT ve de un mes lo trata como una lista vacía. Llega como cualquier
    rechazo, con el código dentro de `errors`, y no se confunde con «ya se hizo» ni con «repítelo»."""
    # Y el 1124, medido el 04-nov-2026: el preliminar de no domiciliados de un mes al que no se cargó ninguno.
    for codigo in ("1070", "1518", "1124"):
        e = sunat.clasificar_error("422", errores=[{"cod": codigo}], operacion="inconsistencias_comprobante")
        assert e.codigo == codigo and e.sin_datos and not e.idempotente and not e.reintentable
    assert "No se ha encontrado información" in sunat.clasificar_error("422", errores=[{"cod": "1070"}]).mensaje
    # Un error de validación, en cambio, no es un vacío: el periodo mal escrito es culpa de quien llama.
    assert not sunat.clasificar_error("422", errores=[{"cod": "1006"}]).sin_datos


@pytest.mark.parametrize("codigo, terminado, descargable", [("01", False, False), ("03", True, True),
                                                            ("04", True, True)])
def test_el_estado_de_un_ticket_sale_del_anexo(codigo, terminado, descargable):
    e = sunat.estado_de_ticket(codigo)
    assert e["conocido"] and e["terminado"] is terminado and e["descargable"] is descargable
    assert e["seguir_sondeando"] is not terminado


def test_un_estado_que_SUNAT_no_documenta_sigue_sondeando_y_no_es_un_fracaso():
    """En producción se han visto 07, 08 y 10, que no figuran en ningún anexo. Darlos por terminados perdería el
    trabajo; darlos por error asustaría sin motivo. El catálogo decide: se sigue preguntando."""
    for codigo in ("07", "08", "10", "99", ""):
        e = sunat.estado_de_ticket(codigo)
        assert not e["conocido"] and e["seguir_sondeando"] and not e["terminado"] and not e["errores"]


def test_el_catalogo_se_copia_al_salir():
    """Quien lo pide puede guardarlo, así que no se le da el de dentro."""
    primero = sunat.sire_api()
    primero["operaciones"]["periodos"]["metodo"] = "DELETE"
    assert sunat.sire_api()["operaciones"]["periodos"]["metodo"] == "GET"
    assert sunat.operaciones()["periodos"]["metodo"] == "GET"


# ── Lo que SUNAT ve del periodo (15.4.0, del manual; medido en parte el 01-nov-2026, 15.4.1) ─────────────────────

def test_las_inconsistencias_por_comprobante_piden_lo_suyo_en_cada_libro():
    """Estuvo fuera del motor hasta la 15.3, en la aplicación que la usaba. En compras se exige `codOrigenEnvio` y en
    ventas no (5.44 y 5.25), y las dos producen el código 13 del Anexo I, con el que se baja el archivo del ticket."""
    compras = sunat.peticion("inconsistencias_comprobante", registro="compra", periodo="202610", codTipoArchivo=0)
    assert compras["url"].endswith(
        "/rce/inconsistencias/web/periodoinconsistencias/202610/080000/exportarinconsistenciasporcomprobantes")
    assert compras["params"] == {"codTipoArchivo": 0, "codOrigenEnvio": "2"} and compras["cod_proceso"] == "13"
    ventas = sunat.peticion("inconsistencias_comprobante", registro="venta", periodo="202610", codTipoArchivo=0)
    assert ventas["url"].endswith("/rvie/inconsistencias/web/periodoinconsistencias/202610/exporta")
    assert ventas["params"] == {"codTipoArchivo": 0} and ventas["devuelve"] == "ticket"
    # Medida en compras el 01-nov-2026 (15.4.1); en ventas SUNAT respondió 1070 y su forma sigue sin verse.
    assert sunat.verificado("inconsistencias_comprobante", registro="compra")
    assert not sunat.verificado("inconsistencias_comprobante", registro="venta")


def test_el_resumen_de_inconsistencias_es_get_en_los_dos_libros_aunque_compras_diga_post():
    """El manual de compras (5.36) lo documenta POST y el de ventas (5.21) GET. La 15.4.0 le creyó a cada uno, y al
    medir (01-nov-2026) el POST de compras respondió 405 y el GET respondió en los dos libros: es GET en los dos, y está
    verificado en los dos. Lo demás es igual —la misma ruta, el libro en `codLibro`, que se rellena solo— y devuelve un
    JSON, no un ticket."""
    compras = sunat.peticion("inconsistencias_resumen", registro="compra", periodo="202610", codTipoResumen=1)
    ventas = sunat.peticion("inconsistencias_resumen", registro="venta", periodo="202610", codTipoResumen=1)
    assert (compras["metodo"], ventas["metodo"]) == ("GET", "GET")
    assert sunat.verificado("inconsistencias_resumen", registro="venta") == "2026-11-01"
    assert sunat.verificado("inconsistencias_resumen", registro="compra") == "2026-11-01"
    assert compras["url"].endswith("/rvierce/resumen/web/resumeninconsistencias/202610")
    assert compras["params"] == {"codTipoResumen": 1, "codLibro": "080000"}
    assert ventas["params"] == {"codTipoResumen": 1, "codLibro": "140000"} and ventas["devuelve"] == "json"
    with pytest.raises(CatalogoDelSireInvalido, match="exige codTipoResumen"):
        sunat.peticion("inconsistencias_resumen", registro="compra", periodo="202610")


def test_las_casillas_son_del_periodo_y_no_de_un_libro():
    """El reporte de casillas del 621 (5.41 y 5.23) no nombra libro: los dos manuales describen la misma URL. El tipo de
    reporte y el de descarga van en la ruta y se pasan como lleguen: los manuales no coincidían en el de descarga, y al
    medirlo (01-nov-2026) solo `txt` en letras trajo algo; los códigos 0, 1 y 2 respondieron 204."""
    p = sunat.peticion("casillas", periodo="202609", tipoReporte=2, tipoDescarga="txt")
    assert p["url"].endswith("/rvierce/casillas/e/casillaspropuestas/202609/reporte/2/txt")
    assert p["params"] == {} and p["metodo"] == "GET" and p["devuelve"] == "binario"
    assert sunat.verificado("casillas") == "2026-11-01"
    with pytest.raises(CatalogoDelSireInvalido, match="necesita 'tipoReporte'"):
        sunat.peticion("casillas", periodo="202610", tipoDescarga=0)


def test_excluidos_y_no_incluidos_producen_el_codigo_del_anexo_i():
    """El 97 «Exportar comprobantes excluidos» y el 11 «Generar archivo exportar no incluidos». El 12 que se usaba fuera
    del motor es «Generar archivo exportar preliminar»."""
    assert sunat.peticion("excluidos", registro="compra", periodo="202610", codTipoArchivo=0)["cod_proceso"] == "97"
    # Los excluidos se midieron sobre un mes presentado (15.4.2); los no incluidos, solo con un 1070.
    assert sunat.verificado("excluidos", registro="compra") == "2026-11-01"
    assert not sunat.verificado("no_incluidos", registro="venta")
    assert sunat.peticion("no_incluidos", registro="venta", periodo="202610", codTipoArchivo=0)["cod_proceso"] == "11"


def test_el_metodo_por_libro_cubre_cada_libro_con_ruta_y_ninguno_mas():
    """Con `metodo_por_libro`, un libro con ruta y sin método no se podría llamar, y un método para un libro sin ruta es
    un dato que alguien va a creer. Las dos cosas paran el catálogo."""
    import copy

    from contaperu.sunat import catalogo

    sin_ventas = copy.deepcopy(sunat.sire_api())
    sin_ventas["operaciones"]["inconsistencias_resumen"]["metodo_por_libro"] = {"080000": "POST"}
    with pytest.raises(CatalogoDelSireInvalido, match="le falta el de 140000"):
        catalogo._valido(sin_ventas)
    de_mas = copy.deepcopy(sunat.sire_api())
    de_mas["operaciones"]["excluidos"]["metodo_por_libro"] = {"080000": "GET", "140000": "GET"}
    with pytest.raises(CatalogoDelSireInvalido, match="metodo_por_libro"):
        catalogo._valido(de_mas)


# ── El registro de no domiciliados (15.6.0, del manual; sin medir) ───────────────────────────────────────────────
def test_las_del_registro_de_no_domiciliados_solo_existen_en_compras():
    for nombre in ("no_domiciliados_cargar", "no_domiciliados_eliminar_comprobante",
                   "no_domiciliados_exportar_preliminar"):
        with pytest.raises(CatalogoDelSireInvalido, match="080000"):
            sunat.peticion(nombre, registro="venta", periodo="202609", codTipoArchivo=0)
    # Exportar el preliminar se midió el 04-nov-2026 (15.6.1); cargar y quitar son escrituras y no se han visto
    # responder: quien automatiza tiene que saberlo antes de llamarlas.
    assert sunat.verificado("no_domiciliados_exportar_preliminar", registro="compra") == "2026-11-04"
    for nombre in ("no_domiciliados_cargar", "no_domiciliados_eliminar_comprobante"):
        assert sunat.verificado(nombre, registro="compra") == ""


def test_exportar_el_preliminar_de_no_domiciliados_pide_un_ticket_del_proceso_96():
    p = sunat.peticion("no_domiciliados_exportar_preliminar", registro="compra", periodo="202609", codTipoArchivo=0)
    assert p["metodo"] == "GET" and p["grada"] == "lectura" and p["devuelve"] == "ticket"
    assert p["url"].endswith("/rce/preliminar/web/nodomiciliados/202609/exportapreliminarnd")
    assert p["params"] == {"codTipoArchivo": 0, "codOrigenEnvio": "2"}
    # El 96, «Generar archivo exportar preliminar - RCE No Domiciliados» del Anexo I: con él se baja el archivo.
    assert p["cod_proceso"] == "96"


def test_cargar_el_080500_es_una_escritura_por_tus_con_el_proceso_56():
    p = sunat.peticion("no_domiciliados_cargar", registro="compra", periodo="202609")
    assert p["metodo"] == "POST" and p["grada"] == "escritura" and p["devuelve"] == "ticket"
    assert p["url"].endswith("/rvierce/receptorpreliminar/web/preliminar/upload")
    assert p["cod_proceso"] == "56"
    assert sunat.operaciones()["no_domiciliados_cargar"]["protocolo"] == "TUS 1.0.0"


def test_quitar_un_comprobante_no_domiciliado_es_un_put_con_el_periodo_en_la_ruta():
    p = sunat.peticion("no_domiciliados_eliminar_comprobante", registro="compra", periodo="202609")
    assert p["metodo"] == "PUT" and p["grada"] == "escritura"
    assert p["url"].endswith("/rce/libronodomiciliado/web/nodomiciliados/202609/eliminarcomprobantepreliminarnd")


def test_el_resumen_lleva_su_tipo_y_su_archivo_en_la_ruta_y_el_libro_en_la_consulta():
    p = sunat.peticion("resumen", registro="compra", periodo="202609", codTipoResumen=7, codTipoArchivo=0)
    assert p["devuelve"] == "binario" and p["grada"] == "lectura"
    assert p["url"].endswith("/rvierce/resumen/web/resumencomprobantes/202609/7/0/exporta")
    assert p["params"] == {"codLibro": "080000"}
    assert sunat.operaciones()["resumen"]["tipos_de_resumen"]["7"] == "no domiciliados"
    # La misma ruta en ventas, con su libro.
    assert sunat.peticion("resumen", registro="venta", periodo="202609", codTipoResumen=1,
                          codTipoArchivo=0)["params"] == {"codLibro": "140000"}
    with pytest.raises(CatalogoDelSireInvalido, match="codTipoResumen"):
        sunat.peticion("resumen", registro="compra", periodo="202609", codTipoArchivo=0)


# ── 15.7.0: deshacer el preliminar y quitar un no domiciliado ───────────────────────────────────────────────────────

def test_eliminar_el_preliminar_es_un_put_en_los_dos_libros_como_dicen_los_manuales():
    """Compras v28 5.17 y Ventas v30 5.15 dicen PUT, sin cuerpo. Hasta la 15.6 decía POST, y en ventas tenía la ruta de
    «eliminar preliminar REGISTRADO» (5.36), que es otra operación y pide un cuerpo con el id del registro."""
    compras = sunat.peticion("preliminar_eliminar", registro="compra", periodo="202609", indEliminar=2)
    assert compras["metodo"] == "PUT" and compras["grada"] == "escritura"
    assert compras["url"].endswith("/rce/preliminar/web/registroslibros/202609/2/eliminapreliminar")
    assert compras["params"] == {}
    ventas = sunat.peticion("preliminar_eliminar", registro="venta", periodo="202609")
    assert ventas["metodo"] == "PUT"
    assert ventas["url"].endswith("/rvierce/gestionlibro/web/registroslibros/202609/eliminarreemplazo")
    assert ventas["params"] == {"codLibro": "140000"}, "el libro va en la consulta, como en el ejemplo del manual"
    with pytest.raises(CatalogoDelSireInvalido, match="indEliminar"):
        sunat.peticion("preliminar_eliminar", registro="compra", periodo="202609")


CAR = "ABC1234567890ABCD1234567890"          # 27 letras y dígitos, con la forma de los medidos


def test_el_cuerpo_para_quitar_no_domiciliados_es_el_de_la_5_38():
    cuerpo = sunat.cuerpo_para_quitar_no_domiciliados([
        {"car": CAR, "tipo_cp": "91", "serie": "8ABCDEFG", "numero": "0007"},
        {"car": CAR.lower(), "tipo_cp": "97", "serie": "NC01", "numero": "1"}])
    assert cuerpo == {"noDomiciliados": [
        {"codCar": CAR, "codTipoCDP": "91", "numSerieCDP": "8ABCDEFG", "numCDP": "0007"},
        {"codCar": CAR.lower(), "codTipoCDP": "97", "numSerieCDP": "NC01", "numCDP": "1"}]}, \
        "la serie y el número van como los tiene SUNAT: sin quitar ceros"


@pytest.mark.parametrize("comprobante,dice", [
    ({"car": "1234567890123456789012345678", "tipo_cp": "91", "serie": "A", "numero": "1"}, "CAR"),   # 28
    ({"car": "1234567890123", "tipo_cp": "91", "serie": "A", "numero": "1"}, "CAR"),                  # el corto
    ({"car": "ABC1234567890ABCD123456789-", "tipo_cp": "91", "serie": "A", "numero": "1"}, "CAR"),
    ({"car": CAR, "tipo_cp": "01", "serie": "F001", "numero": "1"}, "91, 97, 98"),
    ({"car": CAR, "tipo_cp": "91", "serie": "", "numero": "1"}, "serie o el número"),
    ({"car": CAR, "tipo_cp": "91", "serie": "A", "numero": " "}, "serie o el número"),
])
def test_un_cuerpo_a_medias_no_se_arma(comprobante, dice):
    """Es una escritura sobre producción: un CAR equivocado quitaría otro comprobante o ninguno, y SUNAT no lo diría."""
    with pytest.raises(sunat.CuerpoInvalido, match=dice):
        sunat.cuerpo_para_quitar_no_domiciliados([comprobante])
    with pytest.raises(sunat.CuerpoInvalido, match="ningún comprobante"):
        sunat.cuerpo_para_quitar_no_domiciliados([])
