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
        "EXIGE no lo declara un registro tributario (forma `linea`): no lleva cuentas"]


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


# --- la familia registro: un sistema contable que importa su registro y arma el asiento él mismo ------------

def driver_de_registro(nombre: str = "registro") -> types.ModuleType:
    """Un driver de la forma `desde_comprobantes`, del tamaño de un ejemplo: una fila por cada parte de la base de
    cada comprobante, con las cuentas que resuelve el núcleo. No decide ninguna."""
    from contaperu import asiento as asi

    m = types.ModuleType(f"contaperu_{nombre}")
    m.NOMBRE = nombre
    m.FORMATOS = {"compra": f"{nombre}_registro", "venta": f"{nombre}_registro"}
    m.OPCIONES = Opciones(extension=".txt")
    m.CONTENT_TYPE = "text/plain; charset=utf-8"
    m.nombre = lambda libro, op=m.OPCIONES: f"{nombre}_{libro.ruc}_{libro.periodo}{op.extension}"

    def desde_comprobantes(libro, comprobantes, contab, op=m.OPCIONES):
        venta = libro.es_venta
        filas = [f"{c.serie}-{c.numero}|{cuenta}|{centro}|{'' if importe is None else importe}|"
                 f"{asi.cuenta_tercero(c, contab, venta)}"
                 for c in comprobantes for cuenta, centro, importe in asi.partes_de(c, contab, venta)]
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
    assert [contrato.necesita_config(m) for m in todos] == [False, True, True, True]
    assert [contrato.necesita_asiento(m) for m in todos] == [False, False, True, True]
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
    r = op.exportar(doc, "registro", CONTAB)
    filas = [f.split("|") for f in r["texto"].splitlines()]
    assert len(filas) == r["resumen"]["filas"] == r["filas"] == len(doc["comprobantes"])
    asiento = op.generar_asiento(doc, CONTAB)["asiento"]
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
    r = op.exportar(doc, "registro", CONTAB, imputacion={"fila-1": {"reparto": reparto}})
    filas = [f.split("|") for f in r["texto"].splitlines()]
    assert len(filas) == len(doc["comprobantes"]) + 1
    assert [f[1:4] for f in filas[:2]] == [["636301", "SISTEMAS", f"{mitad:.2f}"],
                                           ["632201", "DESARROLLO", f"{base - mitad:.2f}"]]

    sin_equivalencia = dict(CONTAB, tipos={c["tipo_cp"]: {"concar": ""} for c in doc["comprobantes"]})
    with pytest.raises(asi.TipoSinMapa):
        op.exportar(doc, "csv", sin_equivalencia)
    assert op.exportar(doc, "registro", sin_equivalencia)["resumen"]["filas"] == len(doc["comprobantes"])


def test_el_registro_exige_la_cuenta_antes_de_escribir_y_diagnosticar_lo_dice(con_terceros):
    """Sin cuenta, el driver ni se llama; lo que declara en EXIGE lo hace cumplir el núcleo. `diagnosticar` le
    cuenta la cuenta, el reparto y el centro, sin sub-diarios, y solo lo exigido deja el mes «no listo»."""
    from contaperu import asiento as asi

    exigente = driver_de_registro("exigente")
    exigente.EXIGE = frozenset({"centro_costo"})
    con_terceros(_Entrada("registro", driver_de_registro()), _Entrada("exigente", exigente))
    doc = documento_de_compras()
    with pytest.raises(asi.SinCuenta):
        op.exportar(doc, "registro")
    with pytest.raises(asi.SinCentro):
        op.exportar(doc, "exigente", CONTAB_CON_CENTROS)

    d = op.diagnosticar(doc, driver="registro")
    assert d["exige"] == ["cuenta_contable"] and d["listo_para_exportar"] is False
    assert set(d["faltantes"]) == {"sin_cuenta", "reparto_no_cuadra", "sin_centro_de_costo"}
    assert d["por_que_no"] == [f"{len(doc['comprobantes'])} sin cuenta contable"] and d["sub_diarios"] == {}
    con_centros = op.diagnosticar(doc, CONTAB_CON_CENTROS, driver="registro")
    assert con_centros["faltantes"]["sin_centro_de_costo"] and con_centros["listo_para_exportar"] is True
    assert op.diagnosticar(doc, CONTAB_CON_CENTROS, driver="exigente")["listo_para_exportar"] is False


def test_la_terminal_alcanza_al_registro_con_su_configuracion_y_su_imputacion(con_terceros, tmp_path):
    from contaperu import cli

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

    d = op.diagnosticar(doc, CONTAB, driver="unica", imputacion=imputacion)
    etiqueta = d["saldrian"][0]
    assert d["exige"] == ["cuenta_contable", "cuenta_unica"] and d["listo_para_exportar"] is False
    assert d["faltantes"]["reparto_no_admitido"] == [etiqueta]
    assert d["por_que_no"] == ["1 con la base repartida entre varias cuentas, que el sistema de destino no admite"]
    assert {"motivo": "reparto_no_admitido", "texto": op.TEXTO_FALTANTE["reparto_no_admitido"],
            "comprobantes": [etiqueta], "pedir_a": "contador"} in d["que_falta"]
    with pytest.raises(asi.RepartoNoAdmitido):
        op.exportar(doc, "unica", CONTAB, imputacion=imputacion)

    assert "reparto_no_admitido" not in op.diagnosticar(doc, CONTAB, driver="registro", imputacion=imputacion)["faltantes"]
    assert op.exportar(doc, "registro", CONTAB, imputacion=imputacion)["resumen"]["filas"] == len(doc["comprobantes"]) + 1
    assert op.exportar(doc, "csv", CONTAB, imputacion=imputacion)["archivo"].endswith(".csv")
    asientos = driver_de_prueba("asientos")
    asientos.EXIGE = frozenset({"cuenta_unica"})
    assert contrato.incumplimientos(asientos) == ["EXIGE solo admite ['centro_costo', 'moneda']; sobra ['cuenta_unica']"]


def test_lo_que_no_cabe_en_el_formato_se_dice_antes_y_detiene_el_archivo(con_terceros, tmp_path, capsys):
    """`no_caben`: lo que el formato no puede llevar aunque la contabilidad esté completa. `diagnosticar` lo lista
    por motivo y el mes no está listo; exportar se niega sin llegar a llamar al driver, y la CLI lo dice sin
    traceback. A un driver que no lo declara no le aparece la clave."""
    from contaperu import cli

    llamado = []
    solo_soles = driver_de_registro("soles")
    original = solo_soles.desde_comprobantes
    solo_soles.desde_comprobantes = lambda *a, **k: llamado.append(1) or original(*a, **k)
    solo_soles.no_caben = lambda libro, comprobantes, contab: {
        "en una moneda que el destino no admite": [c for c in comprobantes if c.moneda != "PEN"],
        "con un motivo que no aplica a este mes": []}
    con_terceros(_Entrada("soles", solo_soles))
    doc = documento_de_compras()
    doc["comprobantes"][0].update(moneda="EUR", tipo_cambio="4.100")

    d = op.diagnosticar(doc, CONTAB, driver="soles")
    etiqueta = d["saldrian"][0]
    assert d["faltantes"]["no_caben"] == {"en una moneda que el destino no admite": [etiqueta]}
    assert d["listo_para_exportar"] is False and d["por_que_no"] == ["1 en una moneda que el destino no admite"]
    assert {"motivo": "no_caben", "texto": "en una moneda que el destino no admite", "comprobantes": [etiqueta],
            "pedir_a": "contador"} in d["que_falta"]
    with pytest.raises(contrato.NoCabe) as e:
        op.exportar(doc, "soles", CONTAB)
    assert list(e.value.motivos) == ["en una moneda que el destino no admite"] and not llamado
    assert "no_caben" not in op.diagnosticar(doc, CONTAB, driver="csv")["faltantes"]

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
    assert contrato.incumplimientos(roto) == ["no_caben es una función: no_caben(libro, comprobantes, contab)"]
