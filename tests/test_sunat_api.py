"""La API del SIRE como funciones puras: armar la petición, el estado de un ticket y el rechazo de SUNAT.

Todo lo de aquí se comprueba **contra el catálogo** (`contaperu/datos/sunat/sire_api.json`), que cita su manual en
cada operación. Lo que NO se comprueba aquí es la forma de una respuesta real, porque no hay ninguna guardada: ese
test entra el día que haya una captura, y hasta entonces el paquete no trae lectores de respuesta.
"""
from __future__ import annotations

import pytest

from contaperu import sunat
from contaperu.sunat.catalogo import CatalogoDelSireInvalido


def test_el_catalogo_trae_las_once_operaciones_y_cada_una_cita_su_manual():
    """Si SUNAT añade una operación, aparece aquí sola. Y ninguna entra sin la fuente de la que sale: la ruta de una
    API ajena es una regla, y si cambia hay que poder ir a mirar de dónde salió."""
    assert len(sunat.OPERACIONES) == 11
    assert set(sunat.OPERACIONES) == {
        "periodos", "propuesta_pedir", "ticket_consultar", "ticket_archivo", "propuesta_reemplazar",
        "propuesta_aceptar", "preliminar_registrar", "preliminar_eliminar", "excluidos", "no_incluidos", "constancia"}
    for nombre, op in sunat.operaciones().items():
        assert op["fuente"].strip(), f"{nombre} no cita su manual"
        assert op["grada"] in sunat.GRADAS, f"{nombre} no declara con qué cuidado se la llama"


def test_las_gradas_reparten_las_once_en_siete_dos_y_dos():
    """La grada no es una anotación: decide si quien envía puede llamarla sola. Siete lecturas que no cambian nada,
    dos escrituras que tocan un mes y dos declarativas que declaran de verdad ante SUNAT. Y hace falta porque el
    SIRE **no tiene ambiente de pruebas**: toda prueba es contra producción."""
    por_grada: dict[str, list[str]] = {}
    for nombre in sunat.OPERACIONES:
        por_grada.setdefault(sunat.grada(nombre), []).append(nombre)
    assert {g: len(ns) for g, ns in por_grada.items()} == {"lectura": 7, "escritura": 2, "declarativa": 2}
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


def test_una_ruta_por_libro_sin_saber_el_libro_se_niega_diciendo_como():
    """Ocho de las once tienen ruta distinta para el RCE y el RVIE. Adivinar cuál es sería inventarse una llamada."""
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
