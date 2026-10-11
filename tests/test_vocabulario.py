"""El vocabulario del estándar en catálogos publicados: una sola fuente, y lo que degrada y lo que no.

Hasta la 1.0 los roles y los tipos de libro vivían **dos veces** —enum en el esquema y tupla en el código— y ningún
test comparaba las copias: podían separarse sin que nadie se enterara. Ahora hay una sola fuente,
`estandar/catalogos.json`, y estos tests la atan al código y al esquema.
"""
from __future__ import annotations

import json

import pytest

from contaperu import api, vocabulario
from contaperu.asiento import motor
from contaperu.asiento.motor import ROLES
from contaperu.modelo import TIPOS_LIBRO, Comprobante, Libro

# Los valores de la 1.0, escritos a mano, y **congelados para siempre**: lo que se publicó no se quita ni cambia de
# significado ni se mueve de sitio, porque quien ya integró lo lee por su nombre y a veces por su orden.
ROLES_DE_LA_1_0 = ("principal", "igv", "retencion_4ta", "tercero", "detraccion_tercero", "detraccion")
CLASES_DE_LA_1_0 = ("activo", "pasivo", "patrimonio", "ingreso", "gasto")
TIPOS_DE_LIBRO_DE_LA_1_0 = ("venta", "compra")

# Y el catálogo de HOY, que es el de la 1.0 más lo que entró después, en el orden en que entró. Si alguien añade un
# valor, este test se pone rojo y hay que decidirlo a propósito: abrir el catálogo no era para que crezcan
# (John, 18-sep-2026), sino para que un hecho nuevo pueda traer los suyos sin subir la versión del estándar.
#
# `contrapartida` y `tesoreria` entraron el 1-oct-2026 con su caso real —un Libro Diario presentado y aceptado por
# SUNAT— porque nombran dos hechos que el catálogo no sabía nombrar: la otra cara de una depreciación o de un asiento
# de destino, y el dinero moviéndose.
#
# `impuesto`, `retencion` y `recorte` entraron con la 5.0, y **no son valores nuevos sino los mismos tres papeles bien
# nombrados**: los viejos metían el tributo en el nombre del rol. Van AL FINAL porque el orden es el de inserción y los
# seis de la 1.0 tienen que seguir ocupando las seis primeras posiciones; los tres viejos siguen en `codigos` y además
# en `obsoletos`, con su reemplazo.
ROLES_DE_HOY = ROLES_DE_LA_1_0 + ("contrapartida", "tesoreria", "impuesto", "retencion", "recorte")

from contaperu.modelo.libro import RASGOS as RASGOS_DE_LIBRO  # noqa: E402  (al lado de lo que describe)

# Y el tercer tipo de libro, que entró el 10-oct-2026: `tesoreria`, el dinero moviéndose. Es el primer valor que se
# añade a esta tabla desde la 1.0, y por eso la promesa de abajo pasa a comprobarse por PREFIJO, como ya se hacía
# con los roles — que es lo que su propio docstring prometía y para los libros no cumplía.
TIPOS_DE_LIBRO_DE_HOY = TIPOS_DE_LIBRO_DE_LA_1_0 + ("tesoreria",)

# Los efectos sobre el efectivo, que son catálogo propio desde el mismo día. Las palabras son las de la NIC 7
# —«entradas y salidas de efectivo»— y son TRES porque su §9 excluye de los flujos los traspasos entre partidas de
# efectivo: `transferencia` existe para poder dejarlo fuera y no contarlo dos veces, que es lo mismo que hacen Odoo
# (`transfer`) y ERPNext (`Internal Transfer`).
EFECTOS_DE_TESORERIA_DE_HOY = ("entrada", "salida", "transferencia")


def test_los_valores_de_la_1_0_no_cambian():
    """La promesa de la 1.0: lo publicado sigue ahí, con su mismo nombre y en su mismo sitio. Que el catálogo crezca
    por detrás no la rompe; que algo de esto se moviera, sí."""
    assert vocabulario.ROLES[:len(ROLES_DE_LA_1_0)] == ROLES_DE_LA_1_0
    assert vocabulario.CLASES == CLASES_DE_LA_1_0
    assert vocabulario.TIPOS_LIBRO[:len(TIPOS_DE_LIBRO_DE_LA_1_0)] == TIPOS_DE_LIBRO_DE_LA_1_0


def test_el_catalogo_crece_solo_a_proposito():
    """El otro lado de la promesa: añadir un valor pone esto rojo. Un catálogo que crece sin que nadie lo decida es
    un enum con más pasos (`estandar/LEEME.md`, «Quién gobierna los catálogos»)."""
    assert vocabulario.ROLES == ROLES_DE_HOY
    assert vocabulario.TIPOS_LIBRO == TIPOS_DE_LIBRO_DE_HOY
    assert vocabulario.EFECTOS_DE_TESORERIA == EFECTOS_DE_TESORERIA_DE_HOY


def test_el_motor_no_escribe_todos_los_roles_del_catalogo():
    """La distinción que entra con `contrapartida` y `tesoreria`, y que conviene que un test diga en voz alta: el
    catálogo es lo que un driver tiene que **entender**, y `ROLES_DEL_MOTOR` lo que el motor **emite**.

    Los dos nuevos son vocabulario para quien produce un asiento que el motor no origina. Si algún día el motor
    empieza a emitirlos, este test cae y hay que mover el valor a `ROLES_DEL_MOTOR` a propósito."""
    assert set(motor.ROLES_DEL_MOTOR) < set(vocabulario.ROLES)
    # **Desde la 5.0 ya no es la tupla de la 1.0**, y divergen para siempre: tres de los seis se renombraron. Lo que
    # el motor emite son seis papeles, los mismos de siempre, con tres nombres nuevos.
    # El CONTENIDO, no el orden: la tupla se deriva de los rasgos en el orden del catálogo desde el 10-oct-2026,
    # así que fijar el orden a mano aquí sería congelar un detalle de la derivación en vez de la promesa.
    assert set(motor.ROLES_DEL_MOTOR) == {"principal", "impuesto", "retencion", "tercero", "recorte", "detraccion"}
    # Y que de verdad se derive: es la unión de lo que declaran los libros que el motor origina, sin lista aparte.
    declarados = {r for tipo in motor.TIPOS_DEL_MOTOR for r in RASGOS_DE_LIBRO[tipo].roles}
    assert set(motor.ROLES_DEL_MOTOR) == declarados
    assert len(motor.ROLES_DEL_MOTOR) == len(ROLES_DE_LA_1_0) == 6
    # Lo que el motor NO emite: los dos de vocabulario, y los tres viejos, que están publicados y ya no se escriben.
    obsoletos = set(api.catalogos_del_estandar()["roles"]["obsoletos"])
    assert set(vocabulario.ROLES) - set(motor.ROLES_DEL_MOTOR) == {"contrapartida", "tesoreria"} | obsoletos
    assert obsoletos == {"igv", "retencion_4ta", "detraccion_tercero"}
    assert not (obsoletos & set(motor.ROLES_DEL_MOTOR)), "el motor no escribe un rol marcado como obsoleto"


def test_el_codigo_y_el_catalogo_son_lo_mismo():
    """El hueco que este cambio cierra: `ROLES` y `TIPOS_LIBRO` estaban escritos en el código y otra vez como enum
    del esquema, sin nada que los comparara. Ahora salen del catálogo, así que no pueden separarse."""
    assert ROLES is vocabulario.ROLES
    assert TIPOS_LIBRO is vocabulario.TIPOS_LIBRO


def test_cada_catalogo_trae_su_fuente_y_su_version():
    """Ninguno entra sin las dos cosas: se versionan aparte del documento, así que hay que poder decir cuál se leyó."""
    for nombre in ("roles", "clases", "tipos_de_libro"):
        assert vocabulario.FUENTES[nombre].strip()
        assert vocabulario.VERSIONES[nombre].strip()


def test_cada_tabla_puede_marcar_un_valor_como_obsoleto():
    """El mecanismo con que un catálogo abierto corrige un valor equivocado sin quitarlo (5.0).

    La regla existía escrita desde la 1.0 —«un valor publicado no se quita ni cambia de significado; si resulta
    equivocado, se marca como obsoleto y entra otro al lado»— y no existía como dato, así que quien integraba no tenía
    forma de enterarse. Y hay un precedente de eso mismo saliendo mal: el `hacia_donde_va` del catálogo de roles
    anunciaba tres renombrados desde la 1.1 y **nunca llegó a la api**, porque `catalogos()` no lo propagaba y el
    esquema de salida lo habría rechazado."""
    servidos = api.catalogos_del_estandar()
    for nombre, tabla in servidos.items():
        assert "obsoletos" in tabla, f"{nombre}: la clave viaja siempre, vacía si no hay ninguno"
        for viejo, marca in tabla["obsoletos"].items():
            assert set(marca) == {"usar", "desde", "por_que"}
            # Lo que lo hace útil: el reemplazo existe, y el viejo NO se ha quitado.
            assert marca["usar"] in tabla["codigos"], f"{nombre}/{viejo}: `usar` apunta a un valor que no existe"
            assert viejo in tabla["codigos"], f"{nombre}/{viejo}: un valor publicado no se quita, se marca"
            assert marca["usar"] != viejo and marca["por_que"].strip()


def test_un_valor_obsoleto_sigue_siendo_valido_al_leerlo():
    """Marcarlo dice «no lo escribas más», no «esto ya no vale». Si invalidara, cada corrección del catálogo rompería
    los documentos guardados, que es justo lo que la regla viene a evitar."""
    import jsonschema

    from contaperu.asiento.lineas import LineaDiario

    roles = api.catalogos_del_estandar()["roles"]
    for viejo in roles["obsoletos"]:
        linea = LineaDiario.de_dict({"cuenta": "401111", "debe_haber": "D", "importe": "18.00",
                                     "clase": "pasivo", "rol": viejo})
        assert linea.rol == viejo
        doc = {"open_accounting": api.OPEN_ACCOUNTING,
               "libro": {"ruc": "20601234567", "periodo": "202601", "tipo": "compra"},
               "asiento": [linea.a_dict()]}
        assert list(jsonschema.Draft202012Validator(api.esquema_open_accounting()).iter_errors(doc)) == []


def test_cada_valor_esta_descrito():
    """Un catálogo publicado sin decir qué significa cada valor obliga a preguntar, que es lo que viene a evitar."""
    for tabla in vocabulario.catalogos().values():
        assert tabla["codigos"] and all(texto.strip() for texto in tabla["codigos"].values())


def test_el_esquema_ya_no_los_enumera():
    """Es el cambio de fondo: el día que entre un hecho nuevo, sus roles no cuestan una versión del estándar."""
    esquema = api.esquema_open_accounting()
    assert "enum" not in esquema["$defs"]["linea"]["properties"]["rol"]
    assert "enum" not in esquema["$defs"]["libro"]["properties"]["tipo"]
    # Y el catálogo se cita en la descripción, para que quien lea el esquema sepa dónde están los valores.
    assert "catalogos.json" in esquema["$defs"]["linea"]["properties"]["rol"]["description"]


def test_la_api_los_sirve_con_su_fuente():
    servidos = api.catalogos_del_estandar()
    assert set(servidos) == set(vocabulario.FUENTES), "la api sirve los catalogos que hay, no una lista a mano"
    assert list(servidos["roles"]["codigos"]) == list(ROLES_DE_HOY)
    assert servidos["clases"]["fuente"] == vocabulario.FUENTES["clases"]


def test_van_aparte_de_los_de_sunat():
    """Los de SUNAT se copian de la norma; estos se gobiernan. Mezclarlos borraría esa frontera — y además
    `tests/test_catalogos.py` exige que el archivo de SUNAT tenga exactamente sus tres tablas."""
    assert set(api.catalogos_sunat()) & set(api.catalogos_del_estandar()) == set()


# ── La degradación, que no es igual para los dos ───────────────────────────────────────────────────────────────

def test_un_rol_desconocido_no_rompe_la_linea():
    """La regla que hace escalable el estándar: quien recibe contabiliza con `clase`, `debe_haber` e `importe` aunque
    no conozca el rol. Un rol nuevo —la percepción, el anticipo— entra sin romper a ningún ERP ya integrado."""
    from contaperu.asiento.lineas import LineaDiario

    linea = LineaDiario.de_dict({"cuenta": "421201", "debe_haber": "H", "importe": "100.00",
                                 "clase": "pasivo", "rol": "percepcion"})
    assert linea.rol == "percepcion" and linea.clase == "pasivo"
    doc = {"open_accounting": api.OPEN_ACCOUNTING,
           "libro": {"ruc": "20601234567", "periodo": "202601", "tipo": "compra"},
           "asiento": [linea.a_dict()]}
    import jsonschema
    assert list(jsonschema.Draft202012Validator(api.esquema_open_accounting()).iter_errors(doc)) == []


def test_un_tipo_de_libro_desconocido_si_rompe_y_es_a_proposito():
    """`libro.tipo` no degrada como el rol: quien recibe un registro que no conoce no puede adivinar qué hacer con
    él. Abrir el catálogo significa que crece sin subir versión, no que valga cualquier cosa."""
    from contaperu.modelo import Libro

    with pytest.raises(ValueError, match="Tipo de libro inválido"):
        Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202601", tipo="banco")


def test_el_destino_que_no_declara_un_libro_lo_rechaza_limpio():
    """La otra mitad de esa degradación: no la hace el documento, la hace el driver, diciendo qué libros lleva."""
    from contaperu.drivers import asiento_contable, formato_de, sire

    assert set(sire.FORMATOS) == set(TIPOS_DE_LIBRO_DE_LA_1_0)
    assert formato_de("asiento_contable", "compra") == "asiento_contable_json"
    assert asiento_contable.FORMATOS.get("banco") is None


def test_el_catalogo_viaja_donde_el_esquema():
    """Vive junto al esquema para citarse por la URL del tag del estándar, y por tanto necesita su propia línea de
    `force-include`: si falta, la rueda instalada no lo encuentra y el motor no arranca."""
    from pathlib import Path

    from contaperu import _datos

    assert json.loads(_datos.del_estandar(_datos.CATALOGOS_DEL_ESTANDAR).decode("utf-8"))
    pyproject = (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
    assert '"estandar/catalogos.json"' in pyproject


def test_el_motor_no_origina_todos_los_libros_del_catalogo():
    """La pareja del test de arriba, en el otro eje, y entra **antes** de que haga falta: hoy los dos conjuntos
    coinciden y por eso parece de adorno.

    Deja de serlo el día que el catálogo crezca —el hito B13, para recibir el diario de un ERP—, y ahí está el
    motivo de ponerlo ya: el motor decide casi todo por `libro.es_venta`, y **lo que no es venta lo trata como
    compra**. Sin la puerta, un libro nuevo saldría con el debe y el haber invertidos y la contraparte en la
    cuenta equivocada, sin un solo error. Si algún día el motor aprende a originar un libro más, este test cae y
    el valor se mueve a `TIPOS_DEL_MOTOR` a propósito."""
    assert set(motor.TIPOS_DEL_MOTOR) <= set(vocabulario.TIPOS_LIBRO)
    assert motor.TIPOS_DEL_MOTOR == ("venta", "compra")


def test_un_libro_que_el_motor_no_origina_se_para_en_la_puerta():
    """La puerta, probada con un libro que hoy no se puede construir: `Libro.__post_init__` rechaza cualquier tipo
    que no esté en el catálogo, así que el tercero se finge.

    Es el único sitio del motor que calcula `es_venta` desde un `Libro`, y por eso una sola guarda protege el medio
    centenar de `not es_venta` que hay detrás."""
    from dataclasses import dataclass

    from contaperu.asiento import faltas

    @dataclass
    class LibroDeManana:
        """Lo que `Libro` será cuando el catálogo crezca: aquí solo hace falta que tenga `tipo`."""

        tipo: str = "diario"
        ruc: str = "20601234567"
        periodo: str = "202608"

    with pytest.raises(faltas.LibroQueElMotorNoOrigina) as e:
        motor.lineas_e_indice_del_libro(LibroDeManana(), [], {}, {})
    assert "diario" in str(e.value) and "venta" in str(e.value) and "compra" in str(e.value)
    assert e.value.tipo == "diario" and e.value.sabe == motor.TIPOS_DEL_MOTOR


def test_es_venta_y_es_compra_son_dos_preguntas_y_no_una():
    """Hoy son complementarias y mañana no: un tipo nuevo da `False` a las dos, que es justo lo que obliga a cada
    rama a decidir en vez de heredar «compra»."""
    from contaperu.modelo import Libro

    venta = Libro(ruc="20601234567", razon_social="MI EMPRESA SAC", periodo="202608", tipo="venta")
    compra = Libro(ruc="20601234567", razon_social="MI EMPRESA SAC", periodo="202608", tipo="compra")
    assert (venta.es_venta, venta.es_compra) == (True, False)
    assert (compra.es_venta, compra.es_compra) == (False, True)


# ── El eje del libro, que la 9.0 pasó de un booleano a una tabla ───────────

def test_cada_libro_que_el_motor_origina_tiene_sus_rasgos():
    """Las dos tuplas tienen que decir lo mismo: `TIPOS_DEL_MOTOR` dice cuáles sabe armar y `RASGOS` en qué se
    diferencian. Si alguien añade uno a una y no a la otra, el motor se queda a medias sin avisar."""
    from contaperu.modelo.libro import RASGOS

    # Lo que el nombre promete es una inclusión, no una igualdad: todo libro que el motor origina tiene su fila.
    # Al revés NO, y desde el 10-oct-2026 ya no es teórico — `tesoreria` tiene rasgos y no se origina.
    assert set(motor.TIPOS_DEL_MOTOR) <= set(RASGOS)
    # Y la invariante que lo ata por el CONTENIDO y no por una lista paralela: **un libro ninguno de cuyos roles
    # el motor emite es un libro que el motor no puede originar.** Venta y compra declaran roles que están todos en
    # `ROLES_DEL_MOTOR` —de hecho lo definen—; tesorería declara `tesoreria` y `contrapartida`, que el catálogo
    # publica desde el 1-oct-2026 y esa tupla deja fuera a propósito. El día que el motor aprenda a emitirlos, las
    # dos cosas se mueven juntas o esto cae.
    no_origina = set(RASGOS) - set(motor.TIPOS_DEL_MOTOR)
    assert {k for k, r in RASGOS.items() if not set(r.roles) & set(motor.ROLES_DEL_MOTOR)} == no_origina
    # Todo libro declara al menos un rol: una fila sin roles no dice nada de su asiento.
    assert all(r.roles for r in RASGOS.values())
    # La misma frontera vista por el sub-diario, que es su consecuencia: sin sub-diario no hay asiento que escribir.
    assert {k for k, r in RASGOS.items() if not r.sub_diario} == no_origina
    for tipo, r in RASGOS.items():
        assert r.tipo == tipo, "la clave de la tabla y el tipo de la fila tienen que ser el mismo"

    # Lo que es cierto solo de los que el motor SÍ origina. Estaba escrito para todas las filas porque todas lo
    # eran, y `tesoreria` es la que separa las dos cosas: lo que una fila promete y lo que promete un asiento.
    for tipo in motor.TIPOS_DEL_MOTOR:
        r = RASGOS[tipo]
        assert r.sentido_principal in ("D", "H")
        assert r.sentido_contraparte != r.sentido_principal, "la partida doble: el otro lado es el otro"
        assert r.sub_diario and r.cuenta_contraparte, "sin estos dos no se puede armar un asiento"

    # Y de los que no: el lado no lo fija el libro, y pedírselo **para** en vez de contestar de más. Hasta la
    # 9.0 ese `sentido_contraparte` era `"D" if sentido_principal == "H" else "H"`, que con un tercer valor
    # habría devuelto «haber» callado y mal — el mismo fallo que la mayor vino a cerrar, una capa más abajo.
    from contaperu.modelo import POR_OPERACION, SentidoNoLoDiceElLibro

    for tipo in set(RASGOS) - set(motor.TIPOS_DEL_MOTOR):
        r = RASGOS[tipo]
        assert r.sentido_principal == POR_OPERACION and r.decide_la_operacion
        with pytest.raises(SentidoNoLoDiceElLibro):
            r.sentido_contraparte


def test_los_dos_libros_se_diferencian_en_lo_que_se_diferencian():
    """El contenido de la tabla, anclado. Es lo que antes estaba repartido en medio centenar de `if es_venta`, y
    tenerlo aquí junto es lo que hace que añadir un libro sea rellenar una fila y no auditar el núcleo."""
    from contaperu.modelo.libro import RASGOS

    venta, compra = RASGOS["venta"], RASGOS["compra"]
    assert (venta.sentido_principal, venta.sentido_contraparte) == ("H", "D")
    assert (compra.sentido_principal, compra.sentido_contraparte) == ("D", "H")
    assert (venta.cuenta_contraparte, compra.cuenta_contraparte) == ("clientes", "cxp")
    # Los roles que caben en cada uno, MEDIDOS ejecutando el motor y no deducidos. Lo que los separa son los tres
    # de las compras: la retención de 4ta de un recibo por honorarios, y las dos líneas de la detracción.
    assert set(venta.roles) == {"principal", "impuesto", "tercero"}
    assert set(compra.roles) - set(venta.roles) == {"retencion", "recorte", "detraccion"}
    # El IGV de una compra es crédito fiscal; el de una venta es lo que se recauda, y por eso no lo es.
    assert compra.da_credito_fiscal and not venta.da_credito_fiscal
    # La detracción y los honorarios solo existen del lado de las compras.
    assert compra.lleva_detraccion and compra.lleva_honorarios
    assert not venta.lleva_detraccion and not venta.lleva_honorarios


def test_omitir_el_libro_ya_no_significa_compra_en_silencio():
    """**Es la razón de ser de la 9.0.** Hasta la 8.x estas funciones tenían `es_venta: bool = False`, así que
    llamarlas sin decir el libro significaba «compra» sin que nadie lo hubiera dicho. Ahora para."""
    from contaperu.asiento import cuenta_tercero
    from contaperu.modelo.libro import LibroSinRasgos

    c = Comprobante(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-08-01", total="118.00")
    with pytest.raises(LibroSinRasgos) as e:
        cuenta_tercero(c, {})
    assert "no conoce" in str(e.value) and "compra, tesoreria, venta" in str(e.value)


def test_un_booleano_de_antes_de_la_9_0_dice_como_migrar():
    """Un `True` que se cuele elegiría la rama equivocada en silencio, que es justo lo que esto viene a quitar.
    Así que no se interpreta: se para, y el mensaje dice qué escribir en su lugar."""
    from contaperu.modelo.libro import RASGOS, LibroSinRasgos, rasgos_de

    with pytest.raises(LibroSinRasgos) as e:
        rasgos_de(True)
    assert "`libro.rasgos`" in str(e.value) and "RASGOS['venta']" in str(e.value)
    # Y lo que sí acepta: unos rasgos, un libro o el tipo por su nombre.
    libro = Libro(ruc="20601234567", razon_social="MI EMPRESA SAC", periodo="202608", tipo="venta")
    assert rasgos_de(libro) is rasgos_de("venta") is libro.rasgos is RASGOS["venta"]
