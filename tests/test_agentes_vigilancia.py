"""El kit de vigilantes de la base MCP: cada uno muerde una lista mala y calla con una buena.

Un vigilante que no muerde pasa en verde sin mirar nada, así que aquí cada uno se ve morder antes de darlo por bueno,
con herramientas escritas a mano en la forma en que viajan por el protocolo.
"""
from __future__ import annotations

from contaperu.agentes import Catalogo, Ficha, Riesgo, vigilancia

ESCRIBE = Riesgo(escribe=True, huella=True)
CATALOGO = Catalogo([
    Ficha("informe", "informe", modo="resumen"),
    Ficha("por_cuenta", "informe", modo="cuentas"),
    Ficha("guardar", "guardar", riesgo=ESCRIBE),
])


def herramienta(nombre: str, descripcion: str = "Hace algo.", **propiedades) -> dict:
    return {"name": nombre, "title": None, "description": descripcion,
            "inputSchema": {"type": "object", "properties": propiedades}, "outputSchema": None,
            "annotations": CATALOGO.herramientas[nombre].anotaciones() if nombre in CATALOGO.herramientas else None}


QUE = {"type": "string", "enum": ["resumen", "cuentas"]}
BUENAS = [herramienta("informe", que=QUE), herramienta("guardar", confirmo={"type": "boolean"},
                                                       huella={"type": "string"})]


def test_la_foto_lleva_el_orden_y_los_modos():
    f = vigilancia.foto(BUENAS, [{"uri": "x://a", "name": "a", "title": None, "description": "d", "mimeType": "text/plain"}],
                        servidor={"nombre": "s"})
    assert f["orden"] == {"herramientas": ["informe", "guardar"], "recursos": ["x://a"]}
    assert f["herramientas"]["informe"]["modos"] == ["resumen", "cuentas"]
    assert "modos" not in f["herramientas"]["guardar"], "sin `que`, la foto no inventa modos"
    assert f["servidor"] == {"nombre": "s"} and f["recursos"]["x://a"]["mime"] == "text/plain"
    assert "servidor" not in vigilancia.foto(BUENAS), "sin presentación, no la inventa"


def test_las_diferencias_dicen_que_cambio():
    antes = vigilancia.foto(BUENAS)
    ahora = vigilancia.foto([herramienta("informe", "Otra cosa.", que=QUE)])
    assert vigilancia.diferencias(antes, antes) == []
    cambios = vigilancia.diferencias(antes, ahora)
    assert "herramientas: faltan guardar" in cambios and "herramientas: en `informe` cambió descripcion" in cambios
    assert "cambió «orden»" in cambios


def test_el_peso_es_nombre_descripcion_y_esquema():
    h = herramienta("guardar", "abc")
    assert vigilancia.peso(h) == len("guardar") + 3 + len('{"type":"object","properties":{}}')


def test_el_presupuesto_es_un_trinquete_en_los_dos_sentidos():
    pesa = sum(vigilancia.peso(h) for h in BUENAS)
    assert vigilancia.fuera_de_presupuesto(BUENAS, {"": pesa}) == []
    assert "pesa" in vigilancia.fuera_de_presupuesto(BUENAS, {"": pesa - 1})[0]
    assert "bájalo" in vigilancia.fuera_de_presupuesto(BUENAS, {"": pesa + 1001})[0]
    assert vigilancia.fuera_de_presupuesto(BUENAS, {"": pesa + 1000}) == []
    por_grupo = vigilancia.fuera_de_presupuesto(BUENAS, {"lectura": 10_000}, grupo_de={"informe": "lectura"})
    assert por_grupo[0] == "el grupo «» no tiene presupuesto", "una herramienta sin grupo no se escapa del presupuesto"


def test_el_tope_de_la_descripcion_tambien_baja():
    larga = [herramienta("informe", "x" * 500)]
    assert vigilancia.descripciones_largas(larga, 500) == []
    assert "mide 500" in vigilancia.descripciones_largas(larga, 499)[0]
    assert "bájalo" in vigilancia.descripciones_largas(larga, 701)[0]


def test_el_numero_y_los_nombres():
    assert vigilancia.numero_distinto(BUENAS, 2) == [] and vigilancia.numero_distinto(BUENAS, 3)
    assert vigilancia.nombres_invalidos(BUENAS) == []
    assert vigilancia.nombres_invalidos([herramienta("servidor.informe")]) == [
        "`servidor.informe` no vale como nombre de herramienta para Claude"]


def test_lo_que_anuncia_el_servidor_es_lo_del_catalogo():
    assert vigilancia.anotaciones_distintas(BUENAS, CATALOGO) == []
    mintiendo = [{**BUENAS[1], "annotations": {**BUENAS[1]["annotations"], "readOnlyHint": True}}]
    assert vigilancia.anotaciones_distintas(mintiendo, CATALOGO) == ["`guardar` anuncia readOnlyHint distinto de su riesgo"]
    assert vigilancia.anotaciones_distintas([herramienta("otra")], CATALOGO) == ["`otra` no está en el catálogo"]
    # Lo que viaja por el cable no lleva las claves nulas: vale lo mismo que `null`.
    sin_nulos = [{**BUENAS[0], "annotations": {"readOnlyHint": True, "openWorldHint": False}}]
    assert vigilancia.anotaciones_distintas(sin_nulos, CATALOGO) == []
    con_prefijo = [{**BUENAS[0], "name": "p_informe"}]
    assert vigilancia.anotaciones_distintas(con_prefijo, CATALOGO, prefijo="p_") == []


TITULADO = Catalogo([Ficha("informe", "informe", modo="resumen"), Ficha("por_cuenta", "informe", modo="cuentas"),
                     Ficha("guardar", "guardar", riesgo=ESCRIBE)], titulos={"informe": "Un informe del mes"})


def test_el_titulo_va_en_la_herramienta_y_no_hace_falta_en_las_anotaciones():
    """Un servidor que pone el título en la herramienta y no en sus anotaciones —lo que el protocolo pide— no tiene
    pistas distintas de su riesgo (16.2: hasta entonces se marcaba entero)."""
    en_la_herramienta = [{**herramienta("informe", que=QUE), "title": "Un informe del mes",
                          "annotations": {"readOnlyHint": True, "openWorldHint": False}}]
    assert vigilancia.anotaciones_distintas(en_la_herramienta, TITULADO) == []
    assert vigilancia.titulos_distintos(en_la_herramienta, TITULADO) == []
    repetido = [{**en_la_herramienta[0], "annotations": {**en_la_herramienta[0]["annotations"],
                                                          "title": "Un informe del mes"}}]
    assert vigilancia.titulos_distintos(repetido, TITULADO) == [], "repetirlo en las anotaciones también vale"


def test_un_titulo_que_no_es_el_del_catalogo_se_dice():
    otro = [{**herramienta("informe", que=QUE), "title": "Informes"}]
    assert vigilancia.titulos_distintos(otro, TITULADO) == [
        "`informe` se titula «Informes» y el catálogo dice «Un informe del mes»"]
    mal_repetido = [{**herramienta("informe", que=QUE), "title": "Un informe del mes",
                     "annotations": {"readOnlyHint": True, "title": "Otro"}}]
    assert vigilancia.titulos_distintos(mal_repetido, TITULADO) == [
        "`informe` repite en sus anotaciones el título «Otro», que no es el suyo"]
    sin_titulo = [{**herramienta("guardar", confirmo={}, huella={}), "title": "Guardar"}]
    assert vigilancia.titulos_distintos(sin_titulo, TITULADO), "un catálogo sin título espera que no haya ninguno"


def test_que_ofrece_los_modos_del_catalogo_y_nada_mas():
    assert vigilancia.que_distinto_de_la_tabla(BUENAS, CATALOGO) == []
    otro_orden = [herramienta("informe", que={"type": "string", "enum": ["cuentas", "resumen"]})]
    assert vigilancia.que_distinto_de_la_tabla(otro_orden, CATALOGO)
    opcional = [herramienta("informe", que={"anyOf": [{"type": "string", "enum": ["resumen", "cuentas"]},
                                                      {"type": "null"}]})]
    assert vigilancia.que_distinto_de_la_tabla(opcional, CATALOGO) == [], "el enum dentro de un anyOf también cuenta"
    sobra = [herramienta("guardar", que=QUE, confirmo={}, huella={})]
    assert vigilancia.que_distinto_de_la_tabla(sobra, CATALOGO) == ["`guardar` tiene una sola operación y publica `que`"]


def test_la_huella_va_con_sus_dos_parametros():
    assert vigilancia.huella_sin_confirmo(BUENAS, CATALOGO) == []
    a_medias = [herramienta("guardar", confirmo={"type": "boolean"})]
    assert vigilancia.huella_sin_confirmo(a_medias, CATALOGO) == [
        "`guardar` pide huella y no tiene `confirmo` y `huella`"]
    sobra = [herramienta("informe", que=QUE, huella={"type": "string"})]
    assert vigilancia.huella_sin_confirmo(sobra, CATALOGO)


def test_una_regla_cortada_no_existe_para_el_modelo():
    reglas = {"primera": "Los importes van en positivo.", "segunda": "La cuenta no se inventa."}
    dentro = "Reglas: " + " ".join(reglas.values())
    assert vigilancia.reglas_cortadas(dentro, reglas) == []
    cortada = "x" * 2040 + dentro
    faltas = vigilancia.reglas_cortadas(cortada, reglas)
    assert len(faltas) == 2 and "detrás del carácter 2048" in faltas[0]
    assert vigilancia.reglas_cortadas(cortada, reglas, fuera_del_recorte={"primera", "segunda"}) == []
    assert "ya cabe" in vigilancia.reglas_cortadas(dentro, reglas, fuera_del_recorte={"primera"})[0]
    assert "ya no dicen" in vigilancia.reglas_cortadas("nada", reglas)[0]


def test_el_recorte_cuenta_en_utf16():
    """Una letra fuera del plano básico son dos unidades: el recorte no la parte ni la cuenta como una."""
    assert vigilancia.lo_que_lee_el_cliente("ab𝔸c", 3) == "ab"
    assert vigilancia.lo_que_lee_el_cliente("abc", 3) == "abc"


def test_una_regla_vive_donde_se_aplica():
    donde = {"positivos": ("van en positivo", ["informe"])}
    # Sin negritas: «van **en positivo**» dice lo mismo para el modelo.
    assert vigilancia.reglas_ausentes([herramienta("informe", "Los importes Van **en positivo**.")], donde) == []
    assert vigilancia.reglas_ausentes(BUENAS, donde) == ["`informe` no dice «van en positivo» (positivos)"]


def test_un_texto_que_manda_a_una_herramienta_que_no_existe():
    textos = {"instrucciones": "Llama a `informe` y luego a `por_cuenta`; el campo `tipo_cp` no es una herramienta.",
              "guardar": "Antes, `que: resumen` en `informe`; y `por_cuenta` otra vez."}
    sospechoso = set(CATALOGO.por_operacion).__contains__
    faltas = vigilancia.fantasmas(textos, ["informe", "guardar"], sospechoso)
    assert faltas == ["`por_cuenta` no es una herramienta y se cita en guardar, instrucciones"]
    assert vigilancia.fantasmas(textos, ["informe", "guardar"], sospechoso, exentos={"por_cuenta"}) == []
