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

# Los valores de la 1.0, escritos a mano, y congelados **mientras dure la mayor**: lo que se publicó no se quita ni
# cambia de significado ni se mueve de sitio, porque quien ya integró lo lee por su nombre y a veces por su orden.
#
# **La 2.0 los movió, y es lo único que puede moverlos.** Los roles son el caso: `igv`, `retencion_4ta` y
# `detraccion_tercero` —los tres que la 5.0 renombró y dejó en `obsoletos`— se fueron con el campo `rol`, que salió
# de la línea. Las clases y los tipos de libro no se tocaron. Así que lo congelado de los roles es ahora el suelo de
# la 2.0, y lo de la 1.0 queda escrito al lado para que el movimiento se vea.
ROLES_DE_LA_1_0 = ("principal", "igv", "retencion_4ta", "tercero", "detraccion_tercero", "detraccion")
ROLES_DE_LA_2_0 = ("principal", "tercero", "detraccion", "contrapartida", "tesoreria", "impuesto", "retencion",
                   "recorte")
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
# nombrados**: los viejos metían el tributo en el nombre del rol. Van AL FINAL porque el orden es el de inserción.
#
# Y desde la 2.0 del estándar **el catálogo ya no describe un campo del documento**: describe el vocabulario del papel
# que la regla DERIVA de cada línea (`drivers.kit.rol`). De los ocho, **siete se derivan desde la 12.8** —entró
# `tesoreria`, cuando el motor emitió su primera línea de ese libro— y queda uno reservado, `contrapartida`, para el
# diario que produce un ERP (B13). Hasta entonces eran seis y dos: la nota decía que los dos reservados eran «para el
# libro de tesorería», y era un error que el 11-oct-2026 corrigió — el 42 de un pago es `tercero`.
ROLES_DE_HOY = ROLES_DE_LA_2_0

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


def test_los_valores_publicados_no_cambian_dentro_de_su_mayor():
    """Lo publicado sigue ahí, con su mismo nombre y en su mismo sitio. Que el catálogo crezca por detrás no la
    rompe; que algo de esto se moviera, sí. **Solo una mayor del estándar puede moverlo**, y la 2.0 lo hizo en un
    catálogo y en ninguno más.

    Las clases y los tipos de libro siguen midiéndose contra la 1.0 —no se tocaron—, y los roles contra la 2.0, que
    es su suelo desde que el campo `rol` salió de la línea. Lo de la 1.0 se guarda arriba para que el movimiento se
    pueda leer: tres de sus seis roles eran los `obsoletos` de la 5.0 y se fueron con el campo."""
    assert vocabulario.ROLES[:len(ROLES_DE_LA_2_0)] == ROLES_DE_LA_2_0
    assert vocabulario.CLASES == CLASES_DE_LA_1_0
    assert vocabulario.TIPOS_LIBRO[:len(TIPOS_DE_LIBRO_DE_LA_1_0)] == TIPOS_DE_LIBRO_DE_LA_1_0
    # Y los tres que se fueron, nombrados: si alguno volviera, volvería con otro significado.
    assert set(ROLES_DE_LA_1_0) - set(vocabulario.ROLES) == {"igv", "retencion_4ta", "detraccion_tercero"}


def test_el_catalogo_crece_solo_a_proposito():
    """El otro lado de la promesa: añadir un valor pone esto rojo. Un catálogo que crece sin que nadie lo decida es
    un enum con más pasos (`estandar/LEEME.md`, «Quién gobierna los catálogos»)."""
    assert vocabulario.ROLES == ROLES_DE_HOY
    assert vocabulario.TIPOS_LIBRO == TIPOS_DE_LIBRO_DE_HOY
    assert vocabulario.EFECTOS_DE_TESORERIA == EFECTOS_DE_TESORERIA_DE_HOY


def test_la_regla_no_deriva_todos_los_roles_del_catalogo():
    """La distinción que entró con `contrapartida` y `tesoreria`, y que conviene que un test diga en voz alta: el
    catálogo es el vocabulario entero, y `ROLES_DEL_MOTOR` lo que la regla sabe **derivar** hoy.

    **`tesoreria` dejó de estar reservado en la 12.8**, cuando el motor emitió su primera línea de ese libro y la
    regla aprendió a derivarla —por el elemento 10 del PCGE, que es la fuente publicada de qué cuenta es dinero—.
    Queda uno, `contrapartida`, para el diario que produce un ERP (B13). Si algún día la regla empieza a
    producirlo, este test cae y hay que mover el valor a propósito, que es justo lo que acaba de pasar con el otro.

    Hasta la 10.0 la frase era «lo que el motor **emite**», porque el motor escribía el `rol` en cada línea. Ya no
    lo escribe: el papel se deriva de lo que la línea trae."""
    assert set(motor.ROLES_DEL_MOTOR) < set(vocabulario.ROLES)
    # El CONTENIDO, no el orden: la tupla se deriva de los rasgos en el orden del catálogo desde el 10-oct-2026,
    # así que fijar el orden a mano aquí sería congelar un detalle de la derivación en vez de la promesa.
    assert set(motor.ROLES_DEL_MOTOR) == {"principal", "impuesto", "retencion", "tercero", "recorte", "detraccion",
                                          "tesoreria"}
    # Y que de verdad se derive: es la unión de lo que declaran los libros que el motor origina, sin lista aparte.
    declarados = {r for tipo in motor.TIPOS_DEL_MOTOR for r in RASGOS_DE_LIBRO[tipo].roles}
    assert set(motor.ROLES_DEL_MOTOR) == declarados
    assert len(motor.ROLES_DEL_MOTOR) == 7
    # Lo que la regla NO produce es exactamente el reservado que queda. Antes de la 2.0 eran cinco: estaban además
    # los tres `obsoletos` de la 5.0, que se fueron del catálogo con el campo que los llevaba.
    assert set(vocabulario.ROLES) - set(motor.ROLES_DEL_MOTOR) == {"contrapartida"}

    # Y que la regla no los devuelva por accidente, que es lo que «reservado» tiene que significar.
    from contaperu.drivers.kit.rol import ROLES_QUE_DERIVA
    assert ROLES_QUE_DERIVA == frozenset(motor.ROLES_DEL_MOTOR)


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
    # **Hoy ningún catálogo tiene ninguno, y es una afirmación y no un hueco**: los tres que había eran del `rol` y
    # se fueron con el campo en la 2.0. El bucle de abajo no itera nada, así que lo que vigila esto hoy es la forma
    # —la clave viaja siempre— y que el día que entre uno cumpla las cuatro reglas.
    assert all(not tabla["obsoletos"] for tabla in servidos.values()), \
        "entró un obsoleto nuevo: es una decisión, y se anuncia en el CHANGELOG"
    for nombre, tabla in servidos.items():
        assert "obsoletos" in tabla, f"{nombre}: la clave viaja siempre, vacía si no hay ninguno"
        for viejo, marca in tabla["obsoletos"].items():
            assert set(marca) == {"usar", "desde", "por_que"}
            # Lo que lo hace útil: el reemplazo existe, y el viejo NO se ha quitado.
            assert marca["usar"] in tabla["codigos"], f"{nombre}/{viejo}: `usar` apunta a un valor que no existe"
            assert viejo in tabla["codigos"], f"{nombre}/{viejo}: un valor publicado no se quita, se marca"
            assert marca["usar"] != viejo and marca["por_que"].strip()


def test_un_valor_obsoleto_sobrevive_mientras_exista_la_clave_donde_se_guardaba():
    """La regla, con la excepción que la 2.0 hizo — y la razón importa más que el caso.

    Marcar un valor como obsoleto dice «no lo escribas más», no «esto ya no vale»: si invalidara, cada corrección
    del catálogo rompería los documentos guardados. Por eso un valor obsoleto **no desaparece nunca**… mientras
    exista la clave donde se guardaba. Los tres del `rol` se fueron con el campo: una línea no puede llevarlo, así
    que describir su reemplazo no le sirve a nadie.

    Lo que esto comprueba es que no quedó un cabo: ninguno de los tres sigue en el catálogo, y el campo tampoco."""
    import jsonschema

    from contaperu.asiento.lineas import LineaDiario

    roles = api.catalogos_del_estandar()["roles"]
    for viejo in ("igv", "retencion_4ta", "detraccion_tercero"):
        assert viejo not in roles["codigos"] and viejo not in roles["obsoletos"]

    # Y la clave tampoco: una línea con `rol` no se lee ni valida, y el rechazo dice por dónde se migra.
    with pytest.raises(ValueError, match="rol_de"):
        LineaDiario.de_dict({"cuenta": "401111", "debe_haber": "D", "importe": "18.00",
                             "clase": "pasivo", "rol": "impuesto"})
    doc = {"open_accounting": api.OPEN_ACCOUNTING,
           "libro": {"ruc": "20601234567", "periodo": "202601", "tipo": "compra"},
           "asiento": [{"cuenta": "401111", "debe_haber": "D", "importe": "18.00", "clase": "pasivo",
                        "rol": "impuesto"}]}
    assert list(jsonschema.Draft202012Validator(api.esquema_open_accounting()).iter_errors(doc)), \
        "el esquema de la 2.0 no admite la clave"


def test_cada_valor_esta_descrito():
    """Un catálogo publicado sin decir qué significa cada valor obliga a preguntar, que es lo que viene a evitar."""
    for tabla in vocabulario.catalogos().values():
        assert tabla["codigos"] and all(texto.strip() for texto in tabla["codigos"].values())


def test_el_esquema_ya_no_los_enumera():
    """Es el cambio de fondo: el día que entre un hecho nuevo, sus valores no cuestan una versión del estándar.

    Lo probaba sobre el `rol` y sobre `libro.tipo`; el `rol` salió del esquema en la 2.0, así que queda el tipo de
    libro — que además es el que lo ha demostrado de verdad: `tesoreria` entró el 10-oct-2026 **sin subir la
    versión del estándar**, que es exactamente lo que esta promesa decía."""
    esquema = api.esquema_open_accounting()
    assert "rol" not in esquema["$defs"]["linea"]["properties"], "el `rol` salió de la línea en la 2.0"
    assert "enum" not in esquema["$defs"]["libro"]["properties"]["tipo"]
    # Y el catálogo se cita en la descripción, para que quien lea el esquema sepa dónde están los valores.
    assert "catalogos.json" in esquema["$defs"]["libro"]["properties"]["tipo"]["description"]


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

def test_una_linea_se_contabiliza_con_los_cuatro_que_el_estandar_exige():
    """La regla que hace escalable el estándar, y lo que la 2.0 le hizo.

    Decía: quien recibe contabiliza con `clase`, `debe_haber` e `importe` aunque no conozca el `rol`, así que un rol
    nuevo entra sin romper a nadie. **La 2.0 llevó esa regla hasta el final**: si la línea se contabiliza sin el
    rol, el rol no es parte de la línea. Salió, y lo que queda es lo que siempre bastaba — los cuatro obligatorios,
    que son los que un ERP de fuera entiende sin conocer el PCGE.

    Lo que sustituye a la degradación es la **derivación**: quien quiera el papel lo calcula de lo que la línea
    trae (`drivers.kit.rol`), y por eso un papel nuevo sigue sin costar una versión del documento."""
    import jsonschema

    from contaperu.asiento.lineas import LineaDiario

    linea = LineaDiario.de_dict({"cuenta": "421201", "debe_haber": "H", "importe": "100.00", "clase": "pasivo"})
    assert (linea.cuenta, linea.debe_haber, linea.importe, linea.clase) == ("421201", "H", "100.00", "pasivo")
    assert api.esquema_open_accounting()["$defs"]["linea"]["required"] == [
        "cuenta", "debe_haber", "importe", "clase"], "los cuatro, y ninguno más"
    doc = {"open_accounting": api.OPEN_ACCOUNTING,
           "libro": {"ruc": "20601234567", "periodo": "202601", "tipo": "compra"},
           "asiento": [linea.a_dict()]}
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
    el valor se mueve a `TIPOS_DEL_MOTOR` a propósito — **y eso pasó en la 12.8**, con tesorería: dejó de ser de
    adorno exactamente como se había anunciado, y el tercer libro entró por la puerta y no por la ventana."""
    assert set(motor.TIPOS_DEL_MOTOR) <= set(vocabulario.TIPOS_LIBRO)
    assert motor.TIPOS_DEL_MOTOR == ("venta", "compra", "tesoreria")


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
    # `ROLES_DEL_MOTOR` —de hecho lo definen, porque esa tupla se deriva de ellos—; tesorería no declara ninguno,
    # que es la única afirmación comprobable mientras el motor no emita ni una línea suya. El día que la emita, las
    # dos cosas se mueven juntas o esto cae. En el catálogo sí hay roles que esa tupla deja fuera a propósito
    # (`tesoreria` y `contrapartida`, desde el 1-oct-2026): son vocabulario para quien produce un asiento que el
    # motor no origina.
    no_origina = set(RASGOS) - set(motor.TIPOS_DEL_MOTOR)
    # Y es una equivalencia EXACTA, no una inclusión: un libro declara roles si y solo si el motor lo origina.
    # Declararlos para uno que no se origina sería adivinar —no hay forma de medirlo ejecutando el motor— y el
    # intento de hacerlo con tesorería salió incompleto a la primera.
    assert {k for k, r in RASGOS.items() if r.roles} == set(motor.TIPOS_DEL_MOTOR)
    assert {k for k, r in RASGOS.items() if not r.roles} == no_origina
    # **El sub-diario ya NO es la misma frontera**, y tesorería es lo que las separó (12.8): el motor sabe armar su
    # asiento y todavía no sabe NUMERARLO, porque numerar es por sub-diario y el suyo espera el archivo real que
    # diga cuál es. Vacío significa ahora «este libro no se numera», que es comprobable, y lo comprueba
    # `LibroQueTodaviaNoSeNumera` — no «este libro no se origina», que ya no sería verdad.
    assert {k for k, r in RASGOS.items() if not r.sub_diario} == {"tesoreria"}
    for tipo, r in RASGOS.items():
        assert r.tipo == tipo, "la clave de la tabla y el tipo de la fila tienen que ser el mismo"

    # **Lo que es cierto de los libros cuyo LADO lo fija el libro**, que no es lo mismo que «los que el motor
    # origina» — y hasta la 12.8 lo parecía porque los dos conjuntos coincidían. Las tres cosas de abajo son
    # consecuencia de UNA sola: que el libro fije el lado. Un libro que no lo fija no puede tener una cuenta de
    # contraparte, porque no hay una sola con la que se salde.
    for tipo, r in RASGOS.items():
        if r.decide_la_operacion:
            continue
        assert r.sentido_principal in ("D", "H")
        assert r.sentido_contraparte != r.sentido_principal, "la partida doble: el otro lado es el otro"
        assert r.cuenta_contraparte, "si el libro fija el lado, fija también contra qué se salda"

    # Y de los que no lo fijan: el lado no lo dice el libro, y pedírselo **para** en vez de contestar de más. Hasta
    # la 9.0 ese `sentido_contraparte` era `"D" if sentido_principal == "H" else "H"`, que con un tercer valor
    # habría devuelto «haber» callado y mal — el mismo fallo que la mayor vino a cerrar, una capa más abajo.
    from contaperu.modelo import POR_OPERACION, SentidoNoLoDiceElLibro

    por_operacion = {k for k, r in RASGOS.items() if r.decide_la_operacion}
    # **Nombrado, para que el bucle no pueda quedarse vacío sin ponerse rojo**: un test que deja de comprobar es el
    # único que no avisa, y al mover tesorería de un conjunto al otro este bucle estuvo a un paso de vaciarse.
    assert por_operacion == {"tesoreria"}
    for tipo in por_operacion:
        r = RASGOS[tipo]
        assert r.sentido_principal == POR_OPERACION and r.decide_la_operacion
        with pytest.raises(SentidoNoLoDiceElLibro):
            r.sentido_contraparte

    # Y la equivalencia que lo explica, que es lo que la tabla ya tenía escrito en prosa: la contrapartida la pone
    # la imputación exactamente cuando el lado no lo fija el libro.
    assert {k for k, r in RASGOS.items() if not r.cuenta_contraparte} == por_operacion


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
