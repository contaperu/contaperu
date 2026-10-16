"""Que añadir un libro sea de verdad añadir una fila, y que se pueda comprobar.

`ARQUITECTURA.md` lo promete tres veces desde la 9.0 —«añadir un libro pasa de auditar cincuenta `if` a rellenar
una fila»— y hasta la 13.1 era verdad a medias: el eje del libro sí era una tabla, pero **de qué bloque salen sus
líneas se decidía con un `if` repetido en siete sitios**, donde el `else` significaba «comprobantes» sin decirlo.
Un cuarto libro añadía un `elif` en los siete, y el que se olvidara salía tratado como una compra en silencio —
que es exactamente el fallo que la 9.0 vino a cerrar, reaparecido una capa más abajo.

Este fichero es lo que impide que vuelva. Tres cosas:

- **el guardián**, que recorre el paquete y prohíbe decidir por el nombre de un origen;
- **el inventario de las tablas**, que exige que cada capa sepa tratar todos los orígenes que haya;
- **el libro de mentira**, que mete una fila en `RASGOS` y comprueba hasta dónde llega sin tocar una línea de
  código. Es la medida de verdad: lo demás dice que no hay `if`, y esto dice qué se consigue por no tenerlos.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from contaperu import api
from contaperu.asiento import comun
from contaperu.modelo import ORIGENES_DE_LIBRO
from contaperu.modelo import libro as libro_mod
from contaperu.modelo.libro import POR_OPERACION, RASGOS, Libro, Rasgos

RAIZ = pathlib.Path(__file__).resolve().parents[1]

# Los módulos a los que se les perdona decidir por el nombre de un origen, con su motivo. **Está vacía, y ese es
# el objetivo**: empezó con los siete de antes de la 13.1 y se vació al convertirlos en tablas. Si algo tiene que
# volver aquí, que sea con su motivo escrito en esta tabla, no con una supresión suelta del linter — el molde es la
# `TOLERADAS` de `test_capas.py`.
TOLERADAS: dict[str, str] = {}


def _modulos():
    for py in sorted((RAIZ / "contaperu").rglob("*.py")):
        yield py.relative_to(RAIZ).as_posix(), ast.parse(py.read_text(encoding="utf-8"))


def test_nadie_decide_por_el_nombre_de_un_origen():
    """Ni una comparación contra `"comprobantes"` o `"movimientos"` en todo el paquete.

    Caza las dos formas que había: `origen == "movimientos"` —seis veces, en el pipeline, en dos drivers y en la
    guarda del motor— y `"movimientos" in totales`, el de la consola, que era peor porque **deducía de qué libro
    era la respuesta por un síntoma de su forma** en vez de preguntar por el libro.

    Lo que NO caza, a propósito: leer una clave con ese nombre (`detalle["comprobantes"]`), que no decide nada, y
    la propia tabla `RASGOS`, donde el literal es el dato. Un `MI_ORIGEN = "movimientos"` tampoco, porque declarar
    de qué es un módulo no es elegir camino — y la guarda que lo usa afirma su identidad, no despacha.
    """
    def _habla_del_origen(nodo) -> bool:
        """Que el otro lado de la comparación sea el origen de un libro, y no otra cosa con el mismo nombre.

        Hace falta desde que el Libro Diario entró con `origen="asiento"`: «asiento» nombra además el bloque del
        documento y la **familia** de un driver (`contrato.familia(modulo) == "asiento"`), que es otro eje. Mirar
        solo el literal daba por culpable a quien comparaba la familia, que no decide nada de un libro.
        """
        if isinstance(nodo, ast.Attribute):
            return nodo.attr == "origen"
        return isinstance(nodo, ast.Name) and nodo.id == "origen"

    culpables: dict[str, list[int]] = {}
    for ruta, arbol in _modulos():
        if ruta in TOLERADAS:
            continue
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Compare):
                continue
            partes = [nodo.left, *nodo.comparators]
            literal = any(isinstance(p, ast.Constant) and p.value in ORIGENES_DE_LIBRO for p in partes)
            if literal and any(_habla_del_origen(p) for p in partes):
                culpables.setdefault(ruta, []).append(nodo.lineno)

    assert culpables == {}, (
        f"alguien volvió a decidir por el nombre de un origen: {culpables}. De qué bloque sale un libro lo dice "
        f"su fila en `RASGOS`, y qué hace cada capa con ese bloque lo dice la tabla de esa capa "
        f"(`CAMINOS_DEL_ASIENTO` y sus hermanas). Un `if` aquí es un libro nuevo tratado como una compra.")


def test_cada_capa_sabe_tratar_todos_los_origenes_que_hay():
    """Las seis tablas cubren los orígenes que los libros declaran. Por inclusión, no por igualdad.

    La inclusión es lo que permite escribir el motor de un bloque **antes** de que exista ningún libro que entre
    por él: la tabla puede saber de más, nunca de menos. Al revés —un origen que un libro declara y una capa no
    sabe tratar— es un `KeyError` en producción, y aquí es un rojo con nombre.
    """
    from contaperu.drivers.asiento_contable import BLOQUES_POR_ORIGEN
    from contaperu.drivers.kit.rol import DERIVACION_DEL_ROL
    from contaperu.pipeline.armado import CAMINOS_DEL_ASIENTO
    from contaperu.pipeline.diagnostico import CAMINOS_DEL_DIAGNOSTICO
    from contaperu.pipeline.salida import CAMINOS_DEL_ARCHIVO
    from contaperu.puertas.cli import IMPRESORES

    tablas = {"armado": CAMINOS_DEL_ASIENTO, "salida": CAMINOS_DEL_ARCHIVO,
              "diagnostico": CAMINOS_DEL_DIAGNOSTICO, "rol": DERIVACION_DEL_ROL,
              "asiento_contable": BLOQUES_POR_ORIGEN, "consola": IMPRESORES}
    for nombre, tabla in tablas.items():
        faltan = set(ORIGENES_DE_LIBRO) - set(tabla)
        assert not faltan, (f"la tabla de {nombre} no sabe qué hacer con {sorted(faltan)}, y hay libros que "
                            f"entran por ahí. Añade su entrada o quita la fila del libro.")


def test_no_nace_una_cuarta_propiedad_es_algo():
    """`Libro` tiene `es_venta`, `es_compra` y `es_tesoreria`, y no puede ganar una cuarta.

    Son de antes de la tabla y están en la superficie congelada, así que no se quitan en una menor —`es_tesoreria`
    **no la llama ni una línea de código**, solo comentarios y tests—. Lo que sí se puede impedir es que crezcan:
    un libro nuevo se pregunta por sus `rasgos`, que es lo que la 9.0 compró, y no estrenando una propiedad que
    cada rama tendría que acordarse de consultar.
    """
    assert {n for n in dir(Libro) if n.startswith("es_")} == {"es_venta", "es_compra", "es_tesoreria"}


@pytest.fixture
def libro_de_mentira(monkeypatch):
    """Mete un libro entero y lo quita, y «entero» son **dos datos y ningún código**.

    Lo descubrió este test al escribirse: no basta la fila en `RASGOS`. Un libro existe cuando está en el
    **catálogo publicado del estándar** —`estandar/catalogos.json`, de donde sale `vocabulario.TIPOS_LIBRO`, que
    es contra lo que `Libro` valida su tipo— y además tiene su fila, que es lo que el motor necesita para armar
    su asiento. Son las dos caras que el repo ya tenía separadas a propósito: el catálogo dice qué libros existen
    y `RASGOS` en qué se diferencian. Las dos son datos.

    **Las constantes derivadas se calculan al importar** —`ORIGENES_DE_LIBRO`, `TIPOS_DEL_MOTOR`—, así que esto
    no las mueve, y es justo lo que hace posible el test sin `importlib.reload`: lo que se comprueba es el camino
    que lee los rasgos EN CALIENTE, que es por donde pasa un libro de verdad. Donde hace falta la derivación se
    recalcula con su misma fórmula, y se dice.
    """
    metidos: list[str] = []

    def meter(tipo: str, **campos) -> Rasgos:
        monkeypatch.setattr(libro_mod, "TIPOS_LIBRO", (*libro_mod.TIPOS_LIBRO, tipo))
        fila = Rasgos(tipo=tipo, origen=campos.pop("origen"), roles=campos.pop("roles", ()),
                      sentido_principal=campos.pop("sentido_principal", POR_OPERACION),
                      cuenta_contraparte="", da_credito_fiscal=False, lleva_detraccion=False,
                      lleva_honorarios=False, sub_diario="", etiqueta_de_archivo=tipo.upper())
        RASGOS[tipo] = fila
        metidos.append(tipo)
        return fila

    yield meter
    for tipo in metidos:
        RASGOS.pop(tipo, None)


def test_un_libro_con_un_bloque_que_nadie_sabe_asentar_se_para_limpio(libro_de_mentira):
    """La fila entra sola, sin motor y sin tocar una línea, y el motor la rechaza nombrando los que sí origina.

    **Es la mitad que la 13.1 desató.** Antes, meter esta fila era imposible sin escribir a la vez su motor: los
    roles se declaran midiendo lo que el motor emite y `TIPOS_DEL_MOTOR` era una tupla a mano, así que las dos
    cosas tenían que entrar en el mismo commit. Ahora la fila entra, el motor dice que no sabe, y lo dice con la
    excepción que ya existía para esto.
    """
    from contaperu.asiento import LibroQueElMotorNoOrigina, lineas_e_indice_del_libro
    from contaperu.asiento.comprobante import TIPOS_DEL_MOTOR

    libro_de_mentira("inventario", origen="existencias")

    # No está entre los que el motor origina, y no porque nadie lo escribiera: porque su bloque no tiene motor.
    # Se recalcula con la fórmula de `comprobante.py`, porque la constante se congeló al importar el paquete.
    origina_ahora = {t for t, r in RASGOS.items() if r.origen in comun.ORIGENES_CON_MOTOR}
    assert "inventario" not in origina_ahora and "inventario" not in TIPOS_DEL_MOTOR
    assert "existencias" not in comun.ORIGENES_CON_MOTOR
    # Y los rasgos sí lo conocen: el catálogo sabe qué es, el motor sabe que no sabe armarlo. Son dos «noes»
    # distintos y el repo los separó a propósito (`LibroSinRasgos` contra esto).
    assert api.rasgos_de("inventario").origen == "existencias"

    with pytest.raises(LibroQueElMotorNoOrigina) as fallo:
        lineas_e_indice_del_libro(Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC",
                                        periodo="202610", tipo="inventario"), [], {}, {})
    assert "inventario" in str(fallo.value)


def test_un_libro_que_reutiliza_un_bloque_con_motor_llega_hasta_donde_llega_su_hermano(libro_de_mentira):
    """Una fila con un origen que YA tiene motor recorre el circuito entero sin una línea nueva en el paquete.

    Es el caso de caja chica y de las rendiciones, que el estándar ya resolvió como tesorería: el hecho es el
    mismo —dinero moviéndose— y lo que cambia es contra qué se salda. Lo que esto demuestra es que si algún día
    se decidiera darles libro propio, el motor no habría que tocarlo.

    Los roles se declaran porque su origen tiene motor, y son los que ese motor emite: eso es lo único que un
    libro así tiene que medir, y `test_vocabulario` imprime la tupla cuando no cuadra.
    """
    libro_de_mentira("caja_chica", origen="movimientos", roles=("tesoreria", "tercero", "principal"))

    # Entra entre los que el motor origina **sin que nadie lo escriba**: lo decide su bloque. Con la fórmula en
    # caliente, porque `TIPOS_DEL_MOTOR` se congeló al importar; lo que importa es que la regla lo incluye.
    assert "caja_chica" in {t for t, r in RASGOS.items() if r.origen in comun.ORIGENES_CON_MOTOR}
    # Y las seis tablas ya saben tratarlo, porque están tecleadas por origen y no por libro.
    test_cada_capa_sabe_tratar_todos_los_origenes_que_hay()
    # Lo que lo para no es el motor: es que ningún driver de serie declara ese libro, que es la degradación que
    # el estándar promete —quien degrada es el destino, nombrando los libros que sí lleva—.
    from contaperu.drivers import LibroQueElDestinoNoLleva, formato_de

    with pytest.raises(LibroQueElDestinoNoLleva):
        formato_de("asiento_contable", "caja_chica")
