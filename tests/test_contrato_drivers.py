"""El examen que pasa cualquier driver registrado, de serie o de terceros.

Un driver nuevo —SISCONT, STARSOFT, el de tu ERP— no necesita que nadie revise a mano si expone lo
que el núcleo espera: si está registrado, este archivo lo comprueba y lo hace exportar el golden de
compras. Y un driver de terceros se enchufa por entry points sin tocar este repositorio; aquí se
prueba con uno de mentira.
"""
from __future__ import annotations

import ast
import base64
import json
import pathlib
import types

import pytest

from contaperu import drivers
from contaperu import api
from contaperu.pipeline import preparacion as prep
from contaperu.asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from contaperu.configuracion import CONFIGURACION_GENERAL, Campo, Columna
from contaperu.drivers import contrato
from contaperu.drivers.kit import Opciones
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
    r = api.exportar(doc, driver=nombre, configuracion=CONTAB)
    crudo = base64.b64decode(r.get("contenido_base64") or r.get("zip_base64") or "")
    assert crudo, f"{nombre} no produjo bytes"
    assert r["archivo"] == mod.nombre(prep.libro_de(doc), mod.OPCIONES)
    if contrato.arma_asientos(mod):
        assert r["resumen"]["debe"] == r["resumen"]["haber"], f"{nombre}: el asiento no cuadra"


def test_la_forma_de_cada_driver_de_serie():
    assert contrato.forma(drivers.sire) == "linea"
    assert contrato.forma(drivers.concar) == "desde_lineas"      # hasta la 0.10, `construir`
    assert contrato.forma(drivers.csv) == "desde_lineas"
    assert contrato.forma(drivers.contasis) == "desde_comprobantes"


def test_lo_que_exige_cada_driver_de_serie():
    """`exige` = lo del núcleo (cuenta y tipo con equivalencia) más lo que el driver declara."""
    assert contrato.exige(drivers.concar) == {"cuenta_contable", "tipo_cp", "centro_costo", "moneda"}
    assert contrato.exige(drivers.csv) == {"cuenta_contable", "tipo_cp"}
    assert contrato.exige(drivers.contasis) == {"cuenta_contable", "cuenta_unica"}
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
        "EXIGE no lo declara un registro tributario (forma `linea`): no lleva cuentas"]


def test_lo_que_el_driver_exige_lo_hace_cumplir_el_nucleo(con_terceros):
    """Un driver `desde_lineas` nunca ve los comprobantes: si exige el centro, lo detiene el núcleo."""
    from contaperu import asiento as asi
    exigente = driver_de_prueba("exigente")
    exigente.EXIGE = frozenset({"centro_costo"})
    con_terceros(_Entrada("exigente", exigente))
    with pytest.raises(asi.SinCentro):
        api.exportar(documento_de_compras(), driver="exigente", configuracion=CONTAB_CON_CENTROS)
    assert api.exportar(documento_de_compras(), driver="exigente", configuracion=CONTAB)["archivo"].endswith(".txt")


def test_el_csv_no_exige_centro_y_concar_si():
    from contaperu import asiento as asi
    assert api.exportar(documento_de_compras(), driver="csv", configuracion=CONTAB_CON_CENTROS)["archivo"].endswith(".csv")
    with pytest.raises(asi.SinCentro):
        api.exportar(documento_de_compras(), driver="concar", configuracion=CONTAB_CON_CENTROS)


def test_las_claves_del_resumen_son_contrato():
    """El portal guarda `resumen` tal cual y lee de él los rangos («hasta») y, desde la 0.8, la huella."""
    r = api.exportar(documento_de_compras(), driver="concar", configuracion=CONTAB)["resumen"]
    assert {"filas", "fechas", "sub_diarios", "debe", "haber", "huella"} <= set(r)
    assert {"desde", "hasta", "comprobantes", "desde_codigo", "hasta_codigo", "desborda", "etiqueta"} <= set(r["sub_diarios"]["11"])
    r2 = api.exportar(documento_de_compras(), driver="csv", configuracion=CONTAB)["resumen"]
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
    m.CANAL = "legacy"
    m.EXIGE = frozenset()
    m.FORMATOS = {"compra": f"{nombre}_asiento"}
    m.OPCIONES = Opciones(extension=".txt")
    m.CONTENT_TYPE = "text/plain; charset=utf-8"
    m.CONFIGURACION = CONFIGURACION_DEL_ASIENTO       # arma asientos: el núcleo lee esas claves al armar sus líneas
    m.nombre = lambda libro, op=m.OPCIONES: f"{nombre}_{libro.ruc}_{libro.periodo}{op.extension}"

    def desde_lineas(libro, lineas, config, op=m.OPCIONES):
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
    r = api.exportar(documento_de_compras(), driver="prueba", configuracion=CONTAB)
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


# --- la familia registro: un sistema contable que importa su registro y arma el asiento él mismo ------------

def driver_de_registro(nombre: str = "registro") -> types.ModuleType:
    """Un driver de la forma `desde_comprobantes`, del tamaño de un ejemplo: una fila por cada parte de la base de
    cada comprobante, con las cuentas que resuelve el núcleo. No decide ninguna."""
    from contaperu import asiento as asi

    m = types.ModuleType(f"contaperu_{nombre}")
    m.NOMBRE = nombre
    m.CANAL = "legacy"
    m.EXIGE = frozenset()
    m.FORMATOS = {"compra": f"{nombre}_registro", "venta": f"{nombre}_registro"}
    m.OPCIONES = Opciones(extension=".txt")
    m.CONTENT_TYPE = "text/plain; charset=utf-8"
    m.nombre = lambda libro, op=m.OPCIONES: f"{nombre}_{libro.ruc}_{libro.periodo}{op.extension}"

    def desde_comprobantes(libro, comprobantes, config, op=m.OPCIONES):
        es_venta = libro.es_venta
        filas = [f"{c.serie}-{c.numero}|{cuenta}|{centro}|{'' if importe is None else importe}|"
                 f"{asi.cuenta_tercero(c, config, es_venta)}"
                 for c in comprobantes for cuenta, centro, importe in asi.partes_de(c, config, es_venta)]
        return "\n".join(filas).encode("utf-8"), {"filas": len(filas)}

    m.desde_comprobantes = desde_comprobantes
    return m


def test_las_dos_familias_y_lo_que_pide_cada_forma():
    """Registro (una fila por comprobante) o asiento. Lo que pide cada forma sale de ahí: la configuración, todo
    driver que lleva cuentas; los correlativos, solo el que arma asientos."""
    registro = driver_de_registro()
    assert contrato.incumplimientos(registro) == [] and contrato.forma(registro) == "desde_comprobantes"
    todos = (drivers.sire, registro, drivers.concar, drivers.csv)
    assert [contrato.familia(m) for m in todos] == ["registro", "registro", "asiento", "asiento"]
    assert [contrato.lleva_cuentas(m) for m in todos] == [False, True, True, True]
    assert [contrato.arma_asientos(m) for m in todos] == [False, False, True, True]
    # El núcleo le exige la cuenta y nada del sub-diario; puede sumar el centro, y la moneda de CONCAR no.
    assert contrato.exige(registro) == {"cuenta_contable"}
    registro.EXIGE = frozenset({"centro_costo"})
    assert contrato.incumplimientos(registro) == []
    assert contrato.exige(registro) == {"cuenta_contable", "centro_costo"}
    registro.EXIGE = frozenset({"moneda"})
    assert contrato.incumplimientos(registro) == ["EXIGE solo admite ['centro_costo', 'cuenta_unica']; sobra ['moneda']"]


def test_un_registro_sale_sin_asiento_y_con_las_cuentas_del_asiento(con_terceros):
    """El núcleo no le arma asiento —ni sub-diarios, ni cuadre, ni huella—, pero cada cuenta es la que llevaría el
    asiento, porque sale de la misma resolución: ningún driver decide una cuenta."""
    con_terceros(_Entrada("registro", driver_de_registro()))
    doc = documento_de_compras()
    r = api.exportar(doc, driver="registro", configuracion=CONTAB)
    filas = [f.split("|") for f in r["texto"].splitlines()]
    assert len(filas) == r["resumen"]["filas"] == r["comprobantes"] == len(doc["comprobantes"])
    asiento = api.generar_asiento(doc, driver="concar", configuracion=CONTAB)["asiento"]
    assert [f[1] for f in filas] == [ln["cuenta"] for ln in asiento if ln["rol"] == "principal"]
    assert [f[4] for f in filas] == [ln["cuenta"] for ln in asiento if ln["rol"] == "tercero"]
    assert not {"sub_diarios", "debe", "haber", "huella"} & set(r["resumen"])
    assert r["archivo"] == "registro_20601234567_202601.txt" and "huella" not in r["_exportacion"]


def test_al_registro_le_llega_la_imputacion_y_no_le_pide_la_equivalencia_del_tipo(con_terceros):
    """La imputación de cada documento le llega dentro de la configuración, como al asiento: un reparto, una fila
    por parte. Y la equivalencia del tipo es del asiento (de ella sale el sub-diario): sin ella el CSV se niega y
    el registro sale."""
    from contaperu import asiento as asi
    from contaperu.igv import base_imputable
    from contaperu.modelo import Comprobante

    con_terceros(_Entrada("registro", driver_de_registro()))
    doc = documento_de_compras()
    primero = doc["comprobantes"][0]
    primero["id_externo"] = "fila-1"
    base = base_imputable(Comprobante.de_dict(primero), False)
    mitad = (base / 2).quantize(base)
    reparto = [{"importe": str(mitad), "cuenta_contable": "636301", "centro_costo": "SISTEMAS"},
               {"importe": str(base - mitad), "cuenta_contable": "632201", "centro_costo": "DESARROLLO"}]
    r = api.exportar(doc, driver="registro", configuracion=CONTAB, imputacion={"fila-1": {"reparto": reparto}})
    filas = [f.split("|") for f in r["texto"].splitlines()]
    assert len(filas) == len(doc["comprobantes"]) + 1
    assert [f[1:4] for f in filas[:2]] == [["636301", "SISTEMAS", f"{mitad:.2f}"],
                                           ["632201", "DESARROLLO", f"{base - mitad:.2f}"]]

    sin_equivalencia = dict(CONTAB, csv={"tipos": {c["tipo_cp"]: {"sigla": ""} for c in doc["comprobantes"]}})
    with pytest.raises(asi.SinSigla):
        api.exportar(doc, driver="csv", configuracion=sin_equivalencia)
    assert api.exportar(doc, driver="registro", configuracion=sin_equivalencia)["resumen"]["filas"] == len(doc["comprobantes"])


def test_el_registro_exige_la_cuenta_antes_de_escribir_y_diagnosticar_lo_dice(con_terceros):
    """Sin cuenta, el driver ni se llama; lo que declara en EXIGE lo hace cumplir el núcleo. `diagnosticar` le
    cuenta la cuenta, el reparto y el centro, sin sub-diarios, y solo lo exigido deja el mes «no listo»."""
    from contaperu import asiento as asi

    exigente = driver_de_registro("exigente")
    exigente.EXIGE = frozenset({"centro_costo"})
    con_terceros(_Entrada("registro", driver_de_registro()), _Entrada("exigente", exigente))
    doc = documento_de_compras()
    with pytest.raises(asi.SinCuenta):
        api.exportar(doc, driver="registro")
    with pytest.raises(asi.SinCentro):
        api.exportar(doc, driver="exigente", configuracion=CONTAB_CON_CENTROS)

    d = api.diagnosticar(doc, driver="registro")
    assert d["exige"] == ["cuenta_contable"] and d["listo_para_exportar"] is False
    assert set(d["faltantes"]) == {"sin_cuenta", "sin_clase", "reparto_que_no_cuadra", "sin_centro"}
    assert d["por_que_no"] == [f"{len(doc['comprobantes'])} sin cuenta contable"] and d["sub_diarios"] == {}
    con_centros = api.diagnosticar(doc, configuracion=CONTAB_CON_CENTROS, driver="registro")
    assert con_centros["faltantes"]["sin_centro"] and con_centros["listo_para_exportar"] is True
    assert api.diagnosticar(doc, configuracion=CONTAB_CON_CENTROS, driver="exigente")["listo_para_exportar"] is False


def test_la_terminal_alcanza_al_registro_con_su_configuracion_y_su_imputacion(con_terceros, tmp_path):
    from contaperu.puertas import cli

    con_terceros(_Entrada("registro", driver_de_registro()))
    doc = documento_de_compras()
    doc["comprobantes"][0]["id_externo"] = "fila-1"
    documento, config, imputacion = tmp_path / "mes.json", tmp_path / "config.json", tmp_path / "imputacion.json"
    documento.write_text(json.dumps(doc), encoding="utf-8")
    config.write_text(json.dumps(CONTAB), encoding="utf-8")
    imputacion.write_text(json.dumps({"fila-1": {"cuenta_contable": "636301"}}), encoding="utf-8")
    salida = tmp_path / "s"
    assert cli.main(["desde-json", str(documento), "--driver", "registro", "--salida", str(salida),
                     "--config", str(config), "--imputacion", str(imputacion)]) == 0
    filas = (salida / "registro_20601234567_202601.txt").read_text(encoding="utf-8").splitlines()
    assert [f.split("|")[1] for f in filas] == ["636301", "659999", "659999"]


def test_un_registro_de_una_cuenta_por_documento_no_admite_reparto(con_terceros):
    """`cuenta_unica`: el destino lleva una cuenta por fila y arma un asiento por fila (CONTASIS, John
    12-sep-2026). El reparto se dice antes, con a quién pedírselo, y el núcleo se niega; a un destino que no lo
    declara —un registro cualquiera, el CSV de asientos— no le cambia nada. Un driver de asientos no lo declara."""
    from contaperu import asiento as asi
    from contaperu.igv import base_imputable
    from contaperu.modelo import Comprobante

    unica = driver_de_registro("unica")
    unica.EXIGE = frozenset({"cuenta_unica"})
    con_terceros(_Entrada("unica", unica), _Entrada("registro", driver_de_registro()))
    doc = documento_de_compras()
    primero = doc["comprobantes"][0]
    primero["id_externo"] = "fila-1"
    base = base_imputable(Comprobante.de_dict(primero), False)
    imputacion = {"fila-1": {"reparto": [{"importe": str(base - 1), "cuenta_contable": "636301"},
                                         {"importe": "1", "cuenta_contable": "632201"}]}}

    d = api.diagnosticar(doc, configuracion=CONTAB, driver="unica", imputacion=imputacion)
    etiqueta = d["saldrian"][0]
    assert d["exige"] == ["cuenta_contable", "cuenta_unica"] and d["listo_para_exportar"] is False
    assert d["faltantes"]["reparto_no_admitido"] == [etiqueta]
    assert d["por_que_no"] == ["1 con la base repartida entre varias cuentas, que el sistema de destino no admite"]
    assert {"motivo": "reparto_no_admitido", "texto": asi.FALTA["reparto_no_admitido"].texto,
            "comprobantes": [etiqueta], "pedir_a": "contador"} in d["que_falta"]
    with pytest.raises(asi.RepartoNoAdmitido):
        api.exportar(doc, driver="unica", configuracion=CONTAB, imputacion=imputacion)

    assert "reparto_no_admitido" not in api.diagnosticar(doc, configuracion=CONTAB, driver="registro", imputacion=imputacion)["faltantes"]
    assert api.exportar(doc, driver="registro", configuracion=CONTAB, imputacion=imputacion)["resumen"]["filas"] == len(doc["comprobantes"]) + 1
    assert api.exportar(doc, driver="csv", configuracion=CONTAB, imputacion=imputacion)["archivo"].endswith(".csv")
    asientos = driver_de_prueba("asientos")
    asientos.EXIGE = frozenset({"cuenta_unica"})
    assert contrato.incumplimientos(asientos) == ["EXIGE solo admite ['centro_costo', 'moneda']; sobra ['cuenta_unica']"]


def test_lo_que_no_cabe_en_el_formato_se_dice_antes_y_detiene_el_archivo(con_terceros, tmp_path, capsys):
    """`no_caben`: lo que el formato no puede llevar aunque la contabilidad esté completa. `diagnosticar` lo lista
    por motivo y el mes no está listo; exportar se niega sin llegar a llamar al driver, y la CLI lo dice sin
    traceback. A un driver que no lo declara no le aparece la clave."""
    from contaperu.puertas import cli

    llamado = []
    solo_soles = driver_de_registro("soles")
    original = solo_soles.desde_comprobantes
    solo_soles.desde_comprobantes = lambda *a, **k: llamado.append(1) or original(*a, **k)
    solo_soles.no_caben = lambda libro, comprobantes, config: {
        "en una moneda que el destino no admite": [c for c in comprobantes if c.moneda != "PEN"],
        "con un motivo que no aplica a este mes": []}
    con_terceros(_Entrada("soles", solo_soles))
    doc = documento_de_compras()
    doc["comprobantes"][0].update(moneda="EUR", tipo_cambio="4.100")

    d = api.diagnosticar(doc, configuracion=CONTAB, driver="soles")
    etiqueta = d["saldrian"][0]
    assert d["faltantes"]["no_cabe"] == {"en una moneda que el destino no admite": [etiqueta]}
    assert d["listo_para_exportar"] is False and d["por_que_no"] == ["1 en una moneda que el destino no admite"]
    assert {"motivo": "no_cabe", "texto": "en una moneda que el destino no admite", "comprobantes": [etiqueta],
            "pedir_a": "contador"} in d["que_falta"]
    with pytest.raises(contrato.NoCabe) as e:
        api.exportar(doc, driver="soles", configuracion=CONTAB)
    assert list(e.value.motivos) == ["en una moneda que el destino no admite"] and not llamado
    assert "no_cabe" not in api.diagnosticar(doc, configuracion=CONTAB, driver="csv")["faltantes"]

    documento, config = tmp_path / "mes.json", tmp_path / "config.json"
    documento.write_text(json.dumps(doc), encoding="utf-8")
    config.write_text(json.dumps(CONTAB), encoding="utf-8")
    assert cli.main(["desde-json", str(documento), "--driver", "soles", "--salida", str(tmp_path / "s"),
                     "--config", str(config)]) == 1
    err = capsys.readouterr().err
    assert "no puede llevar" in err and "Traceback" not in err
    assert cli.main(["diagnosticar", str(documento), "--driver", "soles", "--config", str(config)]) == 1
    assert "No cabe en el formato (en una moneda que el destino no admite)" in capsys.readouterr().out

    roto = driver_de_registro("roto")
    roto.no_caben = "no"
    assert contrato.incumplimientos(roto) == ["no_caben es una función: no_caben(libro, comprobantes, config)"]


# --- la configuración que declara cada driver (13-sep-2026) --------------------------------------------------------

def test_cada_driver_de_serie_declara_lo_que_se_configura_en_su_seccion():
    """Lo del asiento lo declaran los dos drivers de asientos; CONCAR suma lo de su formato, y CONTASIS solo lo suyo.
    El SIRE no se configura: no lleva cuentas."""
    del_asiento = [c.clave for c in CONFIGURACION_DEL_ASIENTO]
    assert [c.clave for c in contrato.configuracion(drivers.concar)] == [*del_asiento, "monedas_codigo",
                                                                          "detraccion_area"]
    assert [c.clave for c in contrato.configuracion(drivers.csv)] == del_asiento
    assert [c.clave for c in contrato.configuracion(drivers.contasis)] == ["medio_pago"]
    assert contrato.configuracion(drivers.sire) == () and contrato.columnas_elegibles(drivers.sire) == {}
    assert contrato.seccion_por_defecto(drivers.contasis) == {"medio_pago": "001",
                                                              "columnas": {"centro_costo": ["centro_costo"]}}
    concar = contrato.seccion_por_defecto(drivers.concar)
    assert concar["columnas"] == {"centro_costo": ["centro_costo", "anexo_auxiliar_del_tercero"]}
    assert concar["monedas_codigo"] == {"PEN": "MN", "USD": "US"}
    assert concar["tipos"]["02"] == {"sigla": "RH", "sub_diario": "15"}
    assert "columnas" not in contrato.seccion_por_defecto(drivers.csv)
    descripcion = contrato.describir(drivers.contasis)
    json.dumps(descripcion)
    assert descripcion["sistema"] == "contasis" and descripcion["campos"][0]["patron"] == "^[0-9]{3}$"
    assert [c["columna"] for c in descripcion["columnas"]["centro_costo"]] == ["centro_costo", "centro_costo_2"]


def test_las_columnas_elegibles_llevan_el_titulo_y_la_letra_de_su_excel():
    from contaperu.drivers.concar.datos import CABECERAS
    from contaperu.drivers.contasis.datos import COLUMNAS

    for c in contrato.columnas_elegibles(drivers.concar)["centro_costo"]:
        assert {CABECERAS["titulos"][letra] for letra in c.letra.values()} == {c.titulo}, c.columna
    for c in contrato.columnas_elegibles(drivers.contasis)["centro_costo"]:
        for libro, letra in c.letra.items():
            assert {l: nombre for l, nombre, _, _ in COLUMNAS[libro]}[letra] == c.titulo, (c.columna, libro)


def test_el_contrato_revisa_la_configuracion_que_declara_un_driver():
    """Un driver de terceros declara su sección como los de serie, y el registro lo examina al cargarlo."""
    sin_asiento = driver_de_prueba()
    del sin_asiento.CONFIGURACION
    assert contrato.incumplimientos(sin_asiento) == [
        "un driver de asientos incluye en CONFIGURACION las claves del asiento (asiento.CONFIGURACION_DEL_ASIENTO), "
        "que el núcleo lee al armar sus líneas; faltan: tipos, sub_diario_ventas, sub_diario_compras, "
        "sub_diario_detraccion, detraccion_tipo_doc, detraccion_codigos"]

    repetida = driver_de_registro()
    repetida.CONFIGURACION = (Campo("x", "texto"), Campo("x", "texto"), Campo("cuentas", "texto"))
    assert contrato.incumplimientos(repetida) == [
        "CONFIGURACION repite claves: x", "CONFIGURACION no declara claves de lo general ni reservadas: cuentas"]
    mal_defecto = driver_de_registro()
    mal_defecto.CONFIGURACION = (Campo("medio_pago", "texto", "1", patron="^[0-9]{3}$"),)
    assert contrato.incumplimientos(mal_defecto) == [
        'los valores por defecto de CONFIGURACION no cumplen lo declarado: `medio_pago`: el texto "1" no cumple el '
        'patrón ^[0-9]{3}$']
    mal_defecto.CONFIGURACION = {"medio_pago": "001"}
    assert contrato.incumplimientos(mal_defecto) == ["CONFIGURACION es una tupla de configuracion.Campo"]

    columnas = driver_de_registro()
    columnas.COLUMNAS_ELEGIBLES = {
        "centro_costo": (Columna("a", "A", {"compra": "A", "venta": "A"}, fija=True),
                         Columna("b", "B", {"compra": "B"}, fija=True, rol="tercero")),
        "cuenta_contable": (Columna("c", "C", {}),)}
    assert contrato.incumplimientos(columnas) == [
        "COLUMNAS_ELEGIBLES['centro_costo'] lleva una sola columna fija: la principal",
        "COLUMNAS_ELEGIBLES['centro_costo']: la letra de 'b' va por cada libro de FORMATOS (compra, venta)",
        "COLUMNAS_ELEGIBLES['centro_costo']: 'b' no lleva rol ni campo, que son de las líneas neutrales de un driver "
        "de asientos",
        "COLUMNAS_ELEGIBLES: 'cuenta_contable' no se elige por columnas; los que sí: centro_costo"]
    asientos = driver_de_prueba()
    asientos.COLUMNAS_ELEGIBLES = {"centro_costo": (
        Columna("m", "M", {"compra": "M"}, fija=True, rol="principal", campo="centro_costo"),
        Columna("x", "X", {"compra": "X"}, rol="igv", campo="anexo_auxiliar"))}
    assert contrato.incumplimientos(asientos) == [
        "COLUMNAS_ELEGIBLES['centro_costo']: en un driver de asientos, 'x' dice qué línea neutral la llena: la fija, "
        "con el centro_costo de la principal; las demás, con el anexo_auxiliar de la principal o del tercero"]

    tributario = types.ModuleType("tributario")
    tributario.NOMBRE, tributario.FORMATOS, tributario.OPCIONES = "trib", {"venta": "trib"}, Opciones()
    tributario.nombre = lambda libro, op=None: "x.txt"
    tributario.linea = lambda c, libro, idx, op=None: ""
    tributario.CONFIGURACION = ()
    assert contrato.incumplimientos(tributario) == [
        "CONFIGURACION y COLUMNAS_ELEGIBLES son de un driver que lleva cuentas: un registro tributario no se configura"]

    con_moneda = driver_de_prueba()
    con_moneda.EXIGE = frozenset({"moneda"})
    assert contrato.incumplimientos(con_moneda) == [
        "un driver que exige `moneda` declara `monedas_codigo` en CONFIGURACION: de ahí lee el núcleo el código de "
        "cada moneda"]


# --- los vigilantes de «un sistema nuevo solo toca su paquete» (John, 13-sep-2026) -------------------------------

GENERALES = {c.clave for c in CONFIGURACION_GENERAL}
DEL_ASIENTO = {c.clave for c in CONFIGURACION_DEL_ASIENTO}
PAQUETE = pathlib.Path(drivers.__file__).resolve().parents[1]


class _Espia(dict):
    """Una configuración que anota cada clave que se le lee."""

    def __init__(self, datos: dict, leidas: set[str]):
        super().__init__(datos)
        self.leidas = leidas

    def get(self, clave, defecto=None):
        self.leidas.add(clave)
        return super().get(clave, defecto)

    def __getitem__(self, clave):
        self.leidas.add(clave)
        return super().__getitem__(clave)

    def __contains__(self, clave):
        self.leidas.add(clave)
        return super().__contains__(clave)


def _propias(modulo) -> set[str]:
    """Las claves de la sección de un driver: las que declara, y `columnas` si declara columnas elegibles."""
    return ({c.clave for c in contrato.configuracion(modulo)}
            | ({"columnas"} if contrato.columnas_elegibles(modulo) else set()))


def _meses_que_pasan_por_todo() -> list[tuple[dict, dict]]:
    """Un mes de compras y uno de ventas que recorren todo lo que se puede leer de la configuración: una factura con
    detracción, otra en dólares, una nota de crédito, un recibo por honorarios y una boleta, con su imputación."""
    compras = documento_de_compras()
    base = compras["comprobantes"][0]
    compras["comprobantes"] += [
        dict(base, numero="9001", detraccion={"codigo": "027", "porcentaje": 4}),
        dict(base, numero="9002", moneda="USD", tipo_cambio="3.500"),
        dict(base, tipo_cp="07", serie="FC01", numero="9003", ref_tipo_cp="01", ref_serie=base["serie"],
             ref_numero=base["numero"], ref_fecha=base["fecha_emision"]),
        dict(base, tipo_cp="02", serie="E001", numero="9004", base_gravada="0", igv="0", inafecto="1000",
             total="1000", retencion="80"),
        dict(base, tipo_cp="03", serie="B001", numero="9005"),
    ]
    ventas = json.loads((GOLDEN / "ventas_202512.json").read_text(encoding="utf-8"))
    meses = []
    for doc, cuenta in ((compras, "631101"), (ventas, "701101")):
        for n, c in enumerate(doc["comprobantes"], 1):
            c["id_externo"] = f"leida-{n}"
        meses.append((doc, {c["id_externo"]: {"cuenta_contable": cuenta, "centro_costo": "OBRA01"}
                            for c in doc["comprobantes"]}))
    return meses


@pytest.mark.parametrize("nombre", ["concar", "contasis", "csv"])
def test_lo_que_se_lee_de_la_configuracion_esta_declarado_y_lo_declarado_se_lee(nombre, monkeypatch):
    """Se exportan un mes de compras y uno de ventas que pasan por todo, y se anota cada clave que se lee de la
    configuración, la lea el driver o el núcleo por él. Lo leído tiene que estar declarado —lo general, su sección, la
    imputación—, y lo que su sección declara tiene que leerse: una clave que nadie lee se configura para nada."""
    from contaperu.pipeline import armado

    leidas: set[str] = set()
    original = armado.config_para
    monkeypatch.setattr(armado, "config_para", lambda modulo, config: _Espia(original(modulo, config), leidas))
    for doc, imputacion in _meses_que_pasan_por_todo():
        api.exportar(doc, driver=nombre, configuracion={}, imputacion=imputacion, incluir_observados=True)
    modulo = drivers.obtener(nombre)
    assert leidas - (GENERALES | _propias(modulo) | {"imputaciones"}) == set(), f"{nombre} lee claves sin declarar"
    assert _propias(modulo) - leidas == set(), f"{nombre} declara claves que no lee"


def _claves_leidas(archivo: pathlib.Path) -> set[str]:
    """Las claves que un módulo lee de la configuración por su nombre: `config.get("x")`, `config["x"]`,
    `(config or {}).get("x")` y `"x" in config`."""
    def es_config(nodo) -> bool:
        return ((isinstance(nodo, ast.Name) and nodo.id == "config")
                or (isinstance(nodo, ast.BoolOp) and es_config(nodo.values[0])))

    def texto(nodo) -> str | None:
        return nodo.value if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) else None

    claves: set[str] = set()
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"))):
        if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "get"
                and es_config(nodo.func.value) and nodo.args and texto(nodo.args[0])):
            claves.add(texto(nodo.args[0]))
        elif isinstance(nodo, ast.Subscript) and es_config(nodo.value) and texto(nodo.slice):
            claves.add(texto(nodo.slice))
        elif (isinstance(nodo, ast.Compare) and len(nodo.ops) == 1 and isinstance(nodo.ops[0], ast.In)
              and es_config(nodo.comparators[0]) and texto(nodo.left)):
            claves.add(texto(nodo.left))
    return claves


@pytest.mark.parametrize("nombre", sorted(drivers.DE_SERIE))
def test_ningun_driver_lee_por_su_nombre_una_clave_que_no_declara(nombre):
    """La misma regla, leída en el código: cada `config.get("x")` de un driver es de lo general, de su sección o la
    imputación. Caza también lo que el mes de prueba no llega a recorrer."""
    modulo = drivers.obtener(nombre)
    permitidas = GENERALES | _propias(modulo) | {"imputaciones"}
    ajenas = {str(f.relative_to(PAQUETE)).replace("\\", "/"): sorted(_claves_leidas(f) - permitidas)
              for f in sorted(pathlib.Path(modulo.__file__).parent.rglob("*.py"))}
    assert {f: claves for f, claves in ajenas.items() if claves} == {}


def test_el_nucleo_solo_lee_lo_general_y_lo_del_asiento():
    """El núcleo no vuelve a leer claves de un sistema (como leía las dos de la X de CONCAR hasta el 13-sep-2026). Las
    dos excepciones leen por el driver que las declara: `columnas`, el contrato (`centro_en_anexo`); y
    `monedas_codigo`, el requisito `moneda`, que solo exige quien la declara (lo comprueba `incumplimientos`)."""
    archivos = [*sorted((PAQUETE / "asiento").rglob("*.py")), PAQUETE / "igv.py", PAQUETE / "detracciones.py",
                PAQUETE / "generar.py", PAQUETE / "drivers" / "contrato.py"]
    permitidas = GENERALES | DEL_ASIENTO | {"imputaciones", "columnas", "monedas_codigo"}
    ajenas = {str(f.relative_to(PAQUETE)).replace("\\", "/"): sorted(_claves_leidas(f) - permitidas) for f in archivos}
    assert {f: claves for f, claves in ajenas.items() if claves} == {}
    assert "monedas_codigo" in _propias(drivers.concar) and "moneda" in drivers.concar.EXIGE


# --- el canal: a quién se entrega lo que sale (1.0) --------------------------------------------------------------

def test_cada_driver_de_serie_declara_su_canal():
    assert {n: contrato.canal(m) for n, m in drivers.DE_SERIE.items()} == {
        "sire": "tributario", "concar": "legacy", "csv": "intercambio", "contasis": "legacy",
        "asiento_neutral": "intercambio"}
    assert all(contrato.declara_canal(m) for m in drivers.DE_SERIE.values())
    assert api.drivers_disponibles()["concar"]["canal"] == "legacy"


def test_las_reglas_de_cada_canal():
    tributario_de_asientos = driver_de_prueba("t")
    tributario_de_asientos.CANAL = "tributario"
    assert contrato.incumplimientos(tributario_de_asientos) == [
        "un driver tributario escribe un registro de texto para SUNAT: su forma es `linea`"]
    intercambio_de_registro = driver_de_registro("i")
    intercambio_de_registro.CANAL = "intercambio"
    assert contrato.incumplimientos(intercambio_de_registro) == [
        "un driver de intercambio proyecta la línea neutral: su forma es `desde_lineas`"]
    legacy_sin_exige = driver_de_prueba("l")
    del legacy_sin_exige.EXIGE
    assert contrato.incumplimientos(legacy_sin_exige) == [
        "un driver legacy declara EXIGE: lo que su sistema no puede importar sin (vacío si nada)"]
    legacy_de_texto = types.ModuleType("texto")
    legacy_de_texto.NOMBRE, legacy_de_texto.FORMATOS, legacy_de_texto.OPCIONES = "x", {"venta": "x"}, Opciones()
    legacy_de_texto.CANAL, legacy_de_texto.nombre = "legacy", (lambda libro, op=None: "x.txt")
    legacy_de_texto.linea = lambda c, libro, idx, op=None: ""
    assert contrato.incumplimientos(legacy_de_texto) == [
        "un driver legacy lleva cuentas: su forma es desde_lineas o desde_comprobantes",
        "un driver legacy declara EXIGE: lo que su sistema no puede importar sin (vacío si nada)"]


@pytest.mark.parametrize("valor,motivo", [("api_erp", "reservado"), ("banco", "no existe")])
def test_un_canal_reservado_o_desconocido_no_pasa(valor, motivo):
    driver = driver_de_prueba()
    driver.CANAL = valor
    [problema] = contrato.incumplimientos(driver)
    assert motivo in problema and (valor != "api_erp" or "A5" in problema)


def test_un_tercero_sin_canal_avisa_y_se_trata_como_legacy(con_terceros):
    sin_canal = driver_de_prueba("sincanal")
    del sin_canal.CANAL
    with pytest.warns(drivers.AvisoDriver, match="no declara CANAL"):
        registrados = con_terceros(_Entrada("sincanal", sin_canal))
    assert "sincanal" in registrados and contrato.canal(sin_canal) == "legacy"


def test_la_forma_construir_de_un_tercero_avisa_y_sigue_exportando(con_terceros):
    viejo = driver_de_prueba("viejo")
    del viejo.desde_lineas

    def construir(libro, comprobantes, config, correlativos, op=viejo.OPCIONES):
        return b"hecho a mano", {"filas": len(comprobantes)}

    viejo.construir = construir
    with pytest.warns(drivers.AvisoDriver, match="construir"):
        con_terceros(_Entrada("viejo", viejo))
    r = api.exportar(documento_de_compras(), driver="viejo", configuracion=CONTAB)
    assert base64.b64decode(r["contenido_base64"]) == b"hecho a mano" and r["resumen"]["filas"] == 3


def test_el_indice_llega_a_quien_lo_acepta(con_terceros):
    recibido = {}
    con_indice = driver_de_prueba("conindice")

    def desde_lineas(libro, lineas, config, op=con_indice.OPCIONES, *, indice=()):
        recibido["lineas"], recibido["indice"] = lineas, indice
        return b"", {}

    con_indice.desde_lineas = desde_lineas
    sin_indice = driver_de_prueba("sinindice")
    assert contrato.acepta_indice(con_indice) and not contrato.acepta_indice(sin_indice)
    con_terceros(_Entrada("conindice", con_indice), _Entrada("sinindice", sin_indice))
    api.exportar(documento_de_compras(), driver="conindice", configuracion=CONTAB)
    lineas, indice = recibido["lineas"], recibido["indice"]
    assert len(indice) == 3 and indice[0].desde == 0 and indice[-1].hasta == len(lineas)
    assert all(a.hasta == b.desde for a, b in zip(indice, indice[1:]))
    assert api.exportar(documento_de_compras(), driver="sinindice", configuracion=CONTAB)["resumen"]["filas"] == 9


def test_lo_que_no_cabe_detiene_tambien_la_forma_desde_lineas(con_terceros):
    corto = driver_de_prueba("corto")
    corto.no_caben = lambda libro, comprobantes, config: {"de prueba: ninguno cabe": list(comprobantes)}
    con_terceros(_Entrada("corto", corto))
    with pytest.raises(contrato.NoCabe):
        api.exportar(documento_de_compras(), driver="corto", configuracion=CONTAB)
    assert api.diagnosticar(documento_de_compras(), driver="corto", configuracion=CONTAB)["faltantes"]["no_cabe"]
