"""El mapa de campos del SIRE (`datos/sunat/sire_campos.json`) dice la verdad sobre el código.

Publicar el formato columna a columna solo sirve si no puede separarse de lo que el motor hace de
verdad. Hasta que existió este archivo, el mismo conocimiento vivía en tres sitios que nada obligaba
a concordar —`POS_VENTA`/`POS_COMPRA` del lector, los nombres de `comparar_sire` y el escritor del
driver `sire`—, y tres de las cuatro versiones anteriores fueron columnas del SIRE mal leídas o
ignoradas: el 26-sep-2026 `tipo_nota` y `estado_sunat` estaban en la lista de «referenciales que se
ignoran» y resultó que importaban, con cinco filas reales dadas de baja por SUNAT que el motor leía
como si les faltara el importe.

Así que aquí se confronta el mapa con las dos puntas: lo que el lector lee y lo que el driver
escribe. Un cambio en cualquiera de las tres sin los otros dos pone la batería en rojo.
"""
from __future__ import annotations

from dataclasses import fields

import pytest

from contaperu import catalogos, comparar_sire
from contaperu.drivers.kit.opciones import Opciones
from contaperu.lectores.sire_txt import IGV_COMPRAS, POS_COMPRA, POS_VENTA, VALOR_NO_GRAVADO
from contaperu.modelo import Comprobante
from contaperu.pipeline import salida as g
from util import campos, cargar_golden

# El registro, su mapa de posiciones del lector y cuántas columnas tiene su anexo.
REGISTROS = [(True, "rvie", POS_VENTA, 40, 33), (False, "rce", POS_COMPRA, 41, 37)]
# Las columnas que el lector lee como un campo del documento, tal cual o partiéndolas en dos.
DEL_LECTOR = {"directa", "neto"}


def columnas(es_venta: bool) -> list[dict]:
    return catalogos.columnas_del_sire(es_venta)


@pytest.mark.parametrize("es_venta,libro,pos,total,informados", REGISTROS)
def test_los_numeros_son_los_del_anexo(es_venta, libro, pos, total, informados):
    """Las columnas van de 1 a N sin huecos, y N es el del anexo: 40 en ventas, 41 en compras."""
    cols = columnas(es_venta)
    assert [c["n"] for c in cols] == list(range(1, total + 1))
    declarado = catalogos.campos_del_sire()["libros"][libro]
    assert declarado["columnas"] == total and declarado["campos_informados"] == informados


@pytest.mark.parametrize("es_venta,libro,pos,total,informados", REGISTROS)
def test_el_mapa_y_el_lector_dicen_lo_mismo(es_venta, libro, pos, total, informados):
    """Toda columna que el mapa da por leída está en el lector con ESE índice, y al revés.

    Es la comprobación que impide la clase de fallo que costó tres versiones: una columna que el mapa
    promete y el lector no lee (un dato que se pierde sin aviso) o que el lector lee y el mapa no
    documenta (un hueco que nadie sabe que se tapó).
    """
    del_mapa = {c["campo"]: c["n"] - 1 for c in columnas(es_venta) if c["lectura"] in DEL_LECTOR}
    assert del_mapa == pos


def test_las_parejas_de_igv_y_las_no_gravadas_son_las_del_lector():
    """Las seis columnas de base/IGV del RCE y la de adquisiciones no gravadas tienen lectura propia."""
    cols = columnas(False)
    parejas: dict[str, list[int]] = {}
    for c in cols:
        if c["lectura"] == "pareja_igv":
            parejas.setdefault(c["destino"], []).append(c["n"] - 1)
    assert {d: tuple(sorted(i)) for d, i in parejas.items()} == IGV_COMPRAS

    no_gravadas = [c for c in cols if c["lectura"] == "no_gravadas"]
    assert [c["n"] - 1 for c in no_gravadas] == [VALOR_NO_GRAVADO]
    assert no_gravadas[0]["campo"] == "valor_no_gravado"


@pytest.mark.parametrize("es_venta,libro,pos,total,informados", REGISTROS)
def test_todo_hueco_dice_su_motivo(es_venta, libro, pos, total, informados):
    """Una columna que el motor no lee explica por qué. Sin motivo no se sabe si es decisión o despiste."""
    sin_motivo = [c["n"] for c in columnas(es_venta) if not c["campo"] and not c.get("motivo", "").strip()]
    assert sin_motivo == [], f"columnas sin campo y sin motivo en {libro}: {sin_motivo}"


@pytest.mark.parametrize("es_venta,libro,pos,total,informados", REGISTROS)
def test_todo_campo_del_mapa_existe_en_el_comprobante(es_venta, libro, pos, total, informados):
    """El mapa no puede prometer un campo que el documento no tiene: sería una promesa que nadie cumple."""
    del_comprobante = {f.name for f in fields(Comprobante)}
    nombrados = {c["campo"] for c in columnas(es_venta) if c["campo"]}
    nombrados |= {c["tambien"] for c in columnas(es_venta) if c.get("tambien")}
    assert nombrados <= del_comprobante, f"el mapa de {libro} nombra lo que no existe: {nombrados - del_comprobante}"


@pytest.mark.parametrize("es_venta,libro,pos,total,informados", REGISTROS)
def test_las_lecturas_y_los_vuelve_estan_descritos(es_venta, libro, pos, total, informados):
    """Cada valor que usa una columna está explicado en el propio mapa: se lee sin abrir el código."""
    mapa = catalogos.campos_del_sire()
    for clave in ("lectura", "vuelve"):
        usados = {c[clave] for c in columnas(es_venta)}
        descritos = set(mapa["lecturas" if clave == "lectura" else "vuelve"])
        assert usados <= descritos, f"{clave} sin describir en {libro}: {usados - descritos}"


@pytest.mark.parametrize("json_golden,es_venta,libro", [("ventas_202512.json", True, "rvie"),
                                                        ("compras_202601.json", False, "rce")])
def test_lo_que_vuelve_es_lo_que_el_driver_escribe(json_golden, es_venta, libro):
    """El mapa promete qué columnas devuelve el TXT de reemplazo: se comprueba contra el TXT de verdad.

    Las que el mapa da por `no` no están en la línea —el reemplazo del RVIE acaba en el campo 33— y las
    que da por `vacio` están presentes y vacías, que es lo que el Anexo 11 pide y lo que hace que el
    archivo generado saliera idéntico al RCE real presentado.
    """
    cols = columnas(es_venta)
    esperados = [c for c in cols if c["vuelve"] != "no"]
    libro_, comprobantes = cargar_golden(json_golden)
    linea = g.generar(libro_, comprobantes, "sire").texto.decode("ascii").split("\r\n")[0]
    f = campos(linea, palote_final=True)

    assert len(f) == len(esperados), f"el mapa de {libro} promete {len(esperados)} columnas y el TXT trae {len(f)}"
    vacias = [c["n"] for c in esperados if c["vuelve"] == "vacio"]
    assert vacias, "algún registro tiene que mandar columnas presentes y vacías"
    for n in vacias:
        assert f[n - 1] == "", f"el mapa dice que la columna {n} de {libro} va vacía y el TXT trae {f[n - 1]!r}"


def test_los_campos_informados_son_los_que_el_driver_manda():
    """Lo que el driver manda son los campos informados del anexo más los que añade una opción
    (`rvie_vacios`, `rce_vacios`): el RVIE acaba en el 33 y el RCE manda los 38-41 vacíos porque su nota (2)
    lo pide de forma explícita. Si SUNAT cambia de idea, cambia la opción, y este test lo dice.

    Y las columnas informadas que van presentes y vacías son exactamente las que el anexo no deja llenar: el
    CAR SUNAT, que es de SU registro, y en compras el % de participación, el IMB y el CAR original, que solo
    aplican a operaciones o ajustes que el motor no produce.
    """
    o = Opciones()
    vacias_por_el_anexo = {True: [4], False: [4, 35, 36, 37]}
    for es_venta, libro, _, total, informados in REGISTROS:
        vacios = o.rvie_vacios if es_venta else o.rce_vacios
        mandadas = [c for c in columnas(es_venta) if c["vuelve"] != "no"]
        assert len(mandadas) == informados + vacios, libro
        assert [c["n"] for c in mandadas if c["vuelve"] == "vacio" and c["n"] <= informados] ==             vacias_por_el_anexo[es_venta], libro


def test_los_nombres_del_informe_salen_del_mapa():
    """`comparar_sire` nombra las columnas con los nombres del mapa, no con una lista propia.

    Tenía la suya, copiada a mano del anexo, y una lista copiada es una lista que se queda atrás."""
    assert comparar_sire.CAMPOS_RVIE == catalogos.nombres_del_sire(True)
    assert comparar_sire.CAMPOS_RCE == catalogos.nombres_del_sire(False)
    assert len(comparar_sire.CAMPOS_RVIE) == 33 and len(comparar_sire.CAMPOS_RCE) == 37


# Los nombres que un informe de `comparar_sire` usa a diario y que salieron del contraste real de agosto.
# El resto no se puede comprobar contra el anexo, que no vive en el repositorio: para eso el mapa lleva
# `fuentes`. Estos se fijan porque un renombrado silencioso aquí hace que el informe que lee el contador
# diga otra cosa —«campo 17» en vez de «IGV»— sin que nada se rompa.
ANCLAS = {True: {1: "RUC", 4: "CAR SUNAT", 17: "IGV", 26: "total", 27: "moneda"},
          False: {1: "RUC", 4: "CAR SUNAT", 15: "base gravada DG", 16: "IGV DG",
                  21: "adquisiciones no gravadas", 25: "total", 26: "moneda"}}


@pytest.mark.parametrize("es_venta,libro,pos,total,informados", REGISTROS)
def test_las_columnas_ancla_conservan_su_nombre(es_venta, libro, pos, total, informados):
    """Un nombre es lo que el informe de una diferencia acaba diciendo, así que no se cambia sin querer."""
    por_numero = {c["n"]: c["nombre"] for c in columnas(es_venta)}
    assert {n: por_numero[n] for n in ANCLAS[es_venta]} == ANCLAS[es_venta], libro
