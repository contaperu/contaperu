"""El TXT del Libro Diario 5.1, con el molde de `test_driver_sire.py`.

**Sin snapshot, y a propósito**, por la misma razón que el del SIRE: los archivos reales no viven en el repositorio
—son datos de un contribuyente—, así que aquí se prueba la **forma** que se contrastó con uno. El ancla fuerte es una
línea entera, carácter a carácter: si algo del layout se mueve, se ve en el diff.

Lo contrastado (1-oct-2026, un Libro Diario presentado y aceptado por SUNAT con sus constancias): 21 campos por fila
separados por `|` y con palote final, CRLF, fechas `DD/MM/AAAA`, importes con dos decimales y el cero escrito en la
columna que no toca, el CUO con la forma `SD-MMNNNN` y el secuencial `M000N` dentro de cada asiento.
"""
from __future__ import annotations

import base64

import pytest

from contaperu import api
from contaperu.drivers import ple
from util import cargar_golden

CAMPOS = 21


def documento(nombre_golden: str, cuenta: str = "631101", centro: str = "001") -> dict:
    """El golden, con un `id_externo` por comprobante y su imputación: lo que todo driver de asientos necesita."""
    libro, comps = cargar_golden(nombre_golden)
    crudos = []
    for n, c in enumerate(comps, 1):
        d = c.a_dict()
        d["id_externo"] = f"f{n}"
        crudos.append(d)
    return {"open_accounting": "1.0", "libro": libro.a_dict(), "comprobantes": crudos,
            "imputaciones": {f"f{n}": {"cuenta_contable": cuenta, "centro_costo": centro}
                             for n in range(1, len(crudos) + 1)}}


def exportar(nombre_golden: str = "compras_202601.json", **kw) -> tuple[dict, list[str]]:
    """`incluir_observados` porque lo que se prueba aquí es el LAYOUT, no la validación: el golden de ventas trae
    RUCs inválidos a propósito, para ejercitarla en los tests que son de eso."""
    r = api.exportar(documento(nombre_golden, **kw), driver="ple", fecha="2026-10-01", incluir_observados=True)
    texto = base64.b64decode(r["contenido_base64"]).decode("ascii")
    return r, texto.splitlines()


def campos_de(linea: str) -> list[str]:
    """Los 21 campos. El palote final cierra la línea y no abre un campo más."""
    assert linea.endswith("|"), linea
    return linea[:-1].split("|")


@pytest.mark.parametrize("golden", ["compras_202601.json", "ventas_202512.json"])
def test_estructura(golden):
    """Lo que SUNAT mira antes que el contenido: el nombre, el número de campos y el salto de línea."""
    r, filas = exportar(golden)
    libro = documento(golden)["libro"]
    assert r["archivo"] == f"LE{libro['ruc']}{libro['periodo']}00{ple.LIBRO_DIARIO}{ple.OPORTUNIDAD}{ple.BANDERAS}.TXT"
    assert filas, "un mes con comprobantes no puede dar un archivo vacío"
    for fila in filas:
        assert len(campos_de(fila)) == CAMPOS
    # CRLF puro: el TXT se abre en Windows y una exportación con \n suelto es una fila partida.
    bruto = base64.b64decode(r["contenido_base64"]).decode("ascii")
    assert "\r\n" in bruto and "\n" not in bruto.replace("\r\n", "")


def test_la_primera_linea_entera():
    """El ancla, carácter a carácter. Si cambia, que cambie a propósito."""
    _, filas = exportar()
    assert filas[0] == (
        "20260100|11-010001|M0001|631101||001|PEN|0|0|01|F001|00045680|10/01/2026|10/02/2026|10/01/2026|"
        "MAYORISTA NACIONAL DE PRODUCTOS SAC|-|40000.00|0.00||1|")


def test_el_cuo_y_el_secuencial_identifican_el_asiento():
    """El campo 2 es el CUO —sub-diario y correlativo del asiento— y el 3 el movimiento dentro de él.

    Las líneas de un mismo comprobante comparten CUO y numeran `M0001`, `M0002`… El correlativo ya trae el mes
    delante, que lo pone el núcleo."""
    _, filas = exportar()
    por_cuo: dict[str, list[str]] = {}
    for fila in filas:
        c = campos_de(fila)
        por_cuo.setdefault(c[1], []).append(c[2])
    for cuo, secuenciales in por_cuo.items():
        assert "-" in cuo, f"el CUO lleva sub-diario y correlativo: {cuo}"
        assert secuenciales == [f"M{n:04d}" for n in range(1, len(secuenciales) + 1)]
    assert len(por_cuo) > 1, "el golden tiene varios comprobantes: tienen que dar varios asientos"


def test_el_debe_y_el_haber_son_dos_columnas_y_el_libro_cuadra():
    """El estándar lleva un importe y su sentido; el 5.1 lleva dos columnas, y la que no toca va con el cero escrito.

    Y lo que de verdad mira un contador: que el libro cuadre, como cuadraba el archivo contrastado."""
    from decimal import Decimal
    _, filas = exportar()
    debe = haber = Decimal("0")
    for fila in filas:
        c = campos_de(fila)
        assert c[17] == "0.00" or c[18] == "0.00", "una línea no puede llevar importe en las dos columnas"
        debe += Decimal(c[17])
        haber += Decimal(c[18])
    assert debe == haber and debe > 0


def test_la_cuenta_contable_va_en_el_campo_4_y_la_denominacion_vacia():
    """Lo que el artículo 6 de la RS 234-2006 exige, y lo que hace opcional."""
    _, filas = exportar(cuenta="631101")
    for fila in filas:
        c = campos_de(fila)
        assert c[3] and c[3].isdigit(), f"toda fila lleva su cuenta contable: {c[3]!r}"
        assert c[4] == "", "la denominación es opcional con más de cuatro dígitos de subcuenta, y va vacía"


def test_el_tercero_lleva_su_tipo_de_documento_y_las_demas_filas_un_cero():
    """El campo 8 sale de la CABECERA, no de la línea: la línea lleva el número del tercero pero no su tipo."""
    _, filas = exportar()
    vistos = {(campos_de(f)[7], bool(campos_de(f)[8] != "0")) for f in filas}
    assert ("6", True) in vistos, "la línea del proveedor lleva su RUC con tipo 6"
    assert ("0", False) in vistos, "las líneas sin tercero llevan 0 en los dos campos"


def test_sin_fecha_va_la_fecha_nula_del_formato():
    """Donde no hay fecha el formato no lleva vacío: lleva `01/01/0001`, que es lo que SUNAT aceptó."""
    _, filas = exportar()
    for fila in filas:
        for i in (12, 13, 14):
            assert campos_de(fila)[i].count("/") == 2, "las tres fechas van siempre escritas"


def test_el_campo_20_va_vacio_y_se_sabe_por_que():
    """La referencia al registro de origen pide el CUO de ESE registro, que el motor no numera todavía.

    Va vacía a propósito y su motivo está en el mapa (`datos/sunat/ple_campos.json`), no solo aquí."""
    _, filas = exportar()
    assert all(campos_de(f)[19] == "" for f in filas)
    campo = next(c for c in api.campos_del_ple()["libros"]["diario"]["campos"] if c["n"] == 20)
    assert campo["escritura"] == "pendiente" and campo["motivo"]


def test_el_estado_es_el_del_periodo():
    """El 8 y el 9 los decide quien lleva el libro, no el motor."""
    _, filas = exportar()
    assert {campos_de(f)[20] for f in filas} == {"1"}


def test_el_mapa_declara_las_mismas_columnas_que_el_driver_escribe():
    """El candado que cierra `test_ple_campos.py`: el mapa publicado y el archivo real no se pueden separar."""
    _, filas = exportar()
    assert len(api.campos_del_ple()["libros"]["diario"]["campos"]) == len(campos_de(filas[0])) == ple.CAMPOS


def test_sin_indice_no_escribe_nada_a_medias():
    """Un driver `desde_lineas` necesita la cabecera de cada comprobante; sin ella las filas saldrían incompletas
    en silencio, que es peor que no salir."""
    from contaperu.modelo import Libro
    from contaperu.asiento import LineaDiario
    libro = Libro(ruc="20601234567", razon_social="X", periodo="202601", tipo="compra")
    with pytest.raises(ValueError, match="necesita el `indice`"):
        ple.desde_lineas(libro, [LineaDiario(cuenta="601101", debe_haber="D", importe="1.00", clase="gasto")], {})
