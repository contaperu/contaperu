"""El examen que pasa cualquier driver registrado, de serie o de terceros.

Un driver nuevo —SISCONT, STARSOFT, el de tu ERP— no necesita que nadie revise a mano si expone lo
que el núcleo espera: si está registrado, este archivo lo comprueba y lo hace exportar el golden de
compras. Y un driver de terceros se enchufa por entry points sin tocar este repositorio; aquí se
prueba con uno de mentira.
"""
from __future__ import annotations

import base64
import json
import types

import pytest

from contaperu import drivers
from contaperu import operaciones as op
from contaperu.drivers import contrato
from contaperu.formato import Opciones
from util import GOLDEN

# El golden no trae cuenta de gasto (sale del RUC en la vida real): se la pone la configuración. Tampoco
# trae centros de costo —viene de SUNAT, que no los conoce—, y desde la 0.8 CONCAR exige el centro donde
# la cuenta lo lleva: este RUC declara que no los usa. Con centros (CONTAB_CON_CENTROS) se niega.
CONTAB = {"cuentas": {"gasto": "659999"}, "usa_centros_costo": False}
CONTAB_CON_CENTROS = {"cuentas": {"gasto": "659999"}}


def documento_de_compras() -> dict:
    return json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("nombre", sorted(drivers.DRIVERS))
def test_cumple_el_contrato(nombre):
    assert contrato.incumplimientos(drivers.obtener(nombre)) == []


@pytest.mark.parametrize("nombre", sorted(drivers.DRIVERS))
def test_exporta_el_golden_de_compras(nombre):
    mod = drivers.obtener(nombre)
    if "compra" not in mod.FORMATOS:
        pytest.skip(f"{nombre} no genera libros de compras")
    doc = documento_de_compras()
    r = op.exportar(doc, nombre, CONTAB)
    crudo = base64.b64decode(r.get("contenido_base64") or r.get("zip_base64") or "")
    assert crudo, f"{nombre} no produjo bytes"
    assert r["archivo"] == mod.nombre(op.libro_de(doc), mod.OPCIONES)
    if contrato.necesita_asiento(mod):
        assert r["resumen"]["debe"] == r["resumen"]["haber"], f"{nombre}: el asiento no cuadra"


def test_la_forma_de_cada_driver_de_serie():
    assert contrato.forma(drivers.sire) == "linea"
    assert contrato.forma(drivers.concar) == "construir"
    # El CSV expone las dos de archivo (conserva `construir` por compatibilidad): gana la nueva.
    assert contrato.forma(drivers.csv) == "desde_lineas"


def test_lo_que_exige_cada_driver_de_serie():
    """`exige` = lo del núcleo (cuenta y tipo con equivalencia) más lo que el driver declara."""
    assert contrato.exige(drivers.concar) == {"cuenta_contable", "tipo_cp", "centro_costo", "moneda"}
    assert contrato.exige(drivers.csv) == {"cuenta_contable", "tipo_cp"}
    assert contrato.exige(drivers.sire) == frozenset() and not hasattr(drivers.sire, "EXIGE")


def test_un_requisito_fuera_del_catalogo_no_pasa_el_contrato():
    raro = driver_de_prueba()
    raro.EXIGE = {"anexo"}
    assert contrato.incumplimientos(raro) == ["EXIGE solo admite ['centro_costo', 'moneda']; sobra ['anexo']"]
    texto = driver_de_prueba()
    texto.EXIGE = "centro_costo"                 # un str también es iterable: no vale
    assert contrato.incumplimientos(texto) == ["EXIGE es un conjunto de textos"]


def test_un_driver_de_texto_no_declara_exige():
    tributario = types.ModuleType("tributario")
    tributario.NOMBRE, tributario.FORMATOS, tributario.OPCIONES = "trib", {"venta": "trib"}, Opciones()
    tributario.nombre = lambda libro, op=None: "x.txt"
    tributario.linea = lambda c, libro, idx, op=None: ""
    assert contrato.incumplimientos(tributario) == []
    tributario.EXIGE = frozenset()
    assert contrato.incumplimientos(tributario) == [
        "EXIGE solo lo declara un driver de asientos: un registro tributario no arma asientos"]


def test_lo_que_el_driver_exige_lo_hace_cumplir_el_nucleo(con_terceros):
    """Un driver `desde_lineas` nunca ve los comprobantes: si exige el centro, lo detiene el núcleo."""
    from contaperu import asiento as asi
    exigente = driver_de_prueba("exigente")
    exigente.EXIGE = frozenset({"centro_costo"})
    con_terceros(_Entrada("exigente", exigente))
    with pytest.raises(asi.SinCentro):
        op.exportar(documento_de_compras(), "exigente", CONTAB_CON_CENTROS)
    assert op.exportar(documento_de_compras(), "exigente", CONTAB)["archivo"].endswith(".txt")


def test_el_csv_no_exige_centro_y_concar_si():
    from contaperu import asiento as asi
    assert op.exportar(documento_de_compras(), "csv", CONTAB_CON_CENTROS)["archivo"].endswith(".csv")
    with pytest.raises(asi.SinCentro):
        op.exportar(documento_de_compras(), "concar", CONTAB_CON_CENTROS)


def test_las_claves_del_resumen_son_contrato():
    """El portal guarda `resumen` tal cual y lee de él los rangos («hasta») y, desde la 0.8, la huella."""
    r = op.exportar(documento_de_compras(), "concar", CONTAB)["resumen"]
    assert {"filas_excel", "fechas", "sub_diarios", "debe", "haber", "huella"} <= set(r)
    assert {"desde", "hasta", "n", "desde_cod", "hasta_cod", "desborda", "etiqueta"} <= set(r["sub_diarios"]["11"])
    r2 = op.exportar(documento_de_compras(), "csv", CONTAB)["resumen"]
    assert {"filas", "sub_diarios", "debe", "haber", "huella"} <= set(r2)


def test_el_contrato_dice_que_falta():
    vacio = types.ModuleType("vacio")
    problemas = contrato.incumplimientos(vacio)
    assert any("NOMBRE" in p for p in problemas) and any("ninguna forma" in p for p in problemas)
    sin_tipo = driver_de_prueba()
    del sin_tipo.CONTENT_TYPE
    assert contrato.incumplimientos(sin_tipo) == ["un driver de archivo declara su CONTENT_TYPE"]


# --- drivers de terceros por entry points ----------------------------------------------------

class _Entrada:
    """Lo mínimo de un `importlib.metadata.EntryPoint`: su nombre y `load()`."""

    def __init__(self, name: str, mod=None, error: Exception | None = None):
        self.name, self._mod, self._error = name, mod, error

    def load(self):
        if self._error:
            raise self._error
        return self._mod


def driver_de_prueba(nombre: str = "prueba") -> types.ModuleType:
    """Un driver de asientos de la forma `desde_lineas`, del tamaño de un ejemplo."""
    m = types.ModuleType(f"contaperu_{nombre}")
    m.NOMBRE = nombre
    m.FORMATOS = {"compra": f"{nombre}_asiento"}
    m.OPCIONES = Opciones(extension=".txt")
    m.CONTENT_TYPE = "text/plain; charset=utf-8"
    m.nombre = lambda libro, op=m.OPCIONES: f"{nombre}_{libro.ruc}_{libro.periodo}{op.extension}"

    def desde_lineas(libro, lineas, contab, op=m.OPCIONES):
        texto = "\n".join(f"{ln.rol}|{ln.cuenta}|{ln.debe_haber}|{ln.importe}" for ln in lineas)
        return texto.encode("utf-8"), {"lineas_escritas": len(lineas)}

    m.desde_lineas = desde_lineas
    return m


@pytest.fixture
def con_terceros(monkeypatch):
    """Simula paquetes instalados en el grupo `contaperu.drivers` y deja el registro como estaba."""
    def instalar(*entradas):
        monkeypatch.setattr(drivers, "entry_points",
                            lambda group: list(entradas) if group == drivers.GRUPO else [])
        return drivers.recargar()
    yield instalar
    monkeypatch.undo()
    drivers.recargar()


def test_un_driver_de_terceros_se_enchufa_sin_tocar_el_nucleo(con_terceros):
    registrados = con_terceros(_Entrada("prueba", driver_de_prueba()))
    assert "prueba" in registrados and set(drivers.DE_SERIE) <= set(registrados)
    r = op.exportar(documento_de_compras(), "prueba", CONTAB)
    lineas = r["texto"].splitlines()
    # El driver solo tradujo: la contabilidad (rol, cuenta, sentido, cuadre) la puso el núcleo.
    assert lineas[0].startswith("principal|659999|D|")
    assert r["resumen"]["debe"] == r["resumen"]["haber"]
    assert r["resumen"]["lineas_escritas"] == len(lineas) == r["resumen"]["filas"]
    assert r["archivo"] == "prueba_20601234567_202601.txt"


def test_un_driver_roto_se_ignora_con_aviso_y_no_tumba_el_registro(con_terceros):
    roto = types.ModuleType("roto")
    roto.NOMBRE = "roto"
    with pytest.warns(drivers.AvisoDriver) as avisos:
        registrados = con_terceros(
            _Entrada("roto", roto),                                        # no cumple el contrato
            _Entrada("explota", error=ImportError("falta una dependencia")),  # revienta al importarse
            _Entrada("concar", driver_de_prueba("concar")),                # pisa un driver de serie
        )
    assert len(avisos) == 3
    assert set(registrados) == set(drivers.DE_SERIE)
    assert registrados["concar"] is drivers.DE_SERIE["concar"]


def test_el_registro_queda_limpio_despues():
    """El fixture de arriba restaura el registro: los tests que vengan después ven los de serie."""
    assert set(drivers.DRIVERS) == set(drivers.DE_SERIE)
