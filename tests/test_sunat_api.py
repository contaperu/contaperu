"""La API del SIRE como funciones puras: armar la petición, el estado de un ticket y el rechazo de SUNAT.

Todo lo de aquí se comprueba **contra el catálogo** (`contaperu/datos/sunat/sire_api.json`), que cita su manual en
cada operación. Lo que NO se comprueba aquí es la forma de una respuesta real, porque no hay ninguna guardada: ese
test entra el día que haya una captura, y hasta entonces el paquete no trae lectores de respuesta.
"""
from __future__ import annotations

import pytest

from contaperu import sunat
from contaperu.sunat.catalogo import CatalogoDelSireInvalido


def test_el_catalogo_trae_las_doce_operaciones_y_cada_una_cita_su_manual():
    """Si SUNAT añade una operación, aparece aquí sola. Y ninguna entra sin la fuente de la que sale: la ruta de una
    API ajena es una regla, y si cambia hay que poder ir a mirar de dónde salió. La duodécima, `registro_pedir`,
    entró el 01-nov-2026: bajar lo DECLARADO de un periodo, que no es la propuesta."""
    assert len(sunat.OPERACIONES) == 12
    assert set(sunat.OPERACIONES) == {
        "periodos", "propuesta_pedir", "ticket_consultar", "ticket_archivo", "propuesta_reemplazar",
        "propuesta_aceptar", "preliminar_registrar", "preliminar_eliminar", "excluidos", "no_incluidos", "constancia",
        "registro_pedir"}
    for nombre, op in sunat.operaciones().items():
        assert op["fuente"].strip(), f"{nombre} no cita su manual"
        assert op["grada"] in sunat.GRADAS, f"{nombre} no declara con qué cuidado se la llama"


def test_las_gradas_reparten_las_doce_en_ocho_dos_y_dos():
    """La grada no es una anotación: decide si quien envía puede llamarla sola. Ocho lecturas que no cambian nada,
    dos escrituras que tocan un mes y dos declarativas que declaran de verdad ante SUNAT. Y hace falta porque el
    SIRE **no tiene ambiente de pruebas**: toda prueba es contra producción."""
    por_grada: dict[str, list[str]] = {}
    for nombre in sunat.OPERACIONES:
        por_grada.setdefault(sunat.grada(nombre), []).append(nombre)
    assert {g: len(ns) for g, ns in por_grada.items()} == {"lectura": 8, "escritura": 2, "declarativa": 2}
    assert "registro_pedir" in por_grada["lectura"]
    assert sorted(por_grada["declarativa"]) == ["preliminar_registrar", "propuesta_aceptar"]
    assert sorted(por_grada["escritura"]) == ["preliminar_eliminar", "propuesta_reemplazar"]


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


def test_lo_declarado_de_ventas_es_otro_servicio_y_esta_sin_medir():
    """El RVIE tiene su propia descarga del registro (Ventas v29 5.27), y no se parece a la de compras: otra ruta, el
    periodo como `perTributario` en la consulta —su ruta no tiene hueco—, el libro como `codLibro`, sin `codMoneda` ni
    `lisPeriodos`, y el `codProceso` de su ejemplo, el 23 («Generar reporte Libro RVIE»). Todo eso sale del manual y
    **no se ha medido**: en compras el manual se equivocó en dos cosas, así que su libro no está verificado."""
    p = sunat.peticion("registro_pedir", registro="venta", periodo="202609", codTipoArchivo=0)
    assert p["url"].endswith("/rvierce/gestionlibro/web/registroslibros/descarga")
    assert p["params"] == {"codTipoArchivo": 0, "codLibro": "140000", "codOrigenEnvio": "2",
                           "perTributario": "202609", "codProceso": "23"}
    assert p["cod_proceso"] == "23"
    assert sunat.verificado("registro_pedir", registro="venta") == ""
    # Lo de compras no se le contagia: sin `codTipoArchivo` se niega, y no pide lo que solo pide el otro libro.
    with pytest.raises(CatalogoDelSireInvalido, match="exige codTipoArchivo"):
        sunat.peticion("registro_pedir", registro="venta", periodo="202609")


def test_lo_medido_se_pregunta_por_libro():
    """`verificado` es la pregunta de quien automatiza: el catálogo describe muchas operaciones que nadie ha visto
    responder. Medida entera, vale para los dos libros; medida por libro, solo para los que nombra."""
    assert sunat.verificado("periodos", registro="venta") == sunat.verificado("periodos", registro="compra") == "2026-11-01"
    assert sunat.verificado("propuesta_pedir", registro="compra") == ""
    assert sunat.verificado("registro_pedir", cod_libro="080000") == "2026-11-01"


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
    assert not e.idempotente and not e.reintentable


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
