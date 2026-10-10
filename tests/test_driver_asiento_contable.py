"""El driver open-accounting: el asiento para los ERP que vienen, sin el vocabulario de ningún sistema legacy.

La promesa (John, 15-sep-2026): la contabilidad es la misma que la de CONCAR —cuentas, sentidos, importes y roles, en
el mismo orden—, y lo único que cambia es el vocabulario: sin siglas, sin sub-diarios, sin correlativos y sin el
documento comodín de la detracción.
"""
from __future__ import annotations

import base64
import json
import types

import pytest

from contaperu import api
from contaperu.asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from contaperu.drivers import contrato, asiento_contable
from test_caracterizacion import IMPUTACION_CASOS
from util import GOLDEN


def casos() -> dict:
    return json.loads((GOLDEN / "casos_202608.json").read_text(encoding="utf-8"))


def contabilidad(lineas: list[dict]) -> list[tuple]:
    return [(linea["cuenta"], linea["debe_haber"], linea["importe"], linea.get("rol")) for linea in lineas]


def test_la_contabilidad_es_la_misma_que_la_de_concar():
    """Soles y dólares, notas, detracción, honorarios, boleta, reparto y extemporáneo: el mismo asiento para los dos."""
    neutral = api.generar_asiento(casos(), driver="asiento_contable", imputacion=IMPUTACION_CASOS)
    concar = api.generar_asiento(casos(), driver="concar", imputacion=IMPUTACION_CASOS)
    assert neutral["asiento"] and contabilidad(neutral["asiento"]) == contabilidad(concar["asiento"])
    assert neutral["_asiento"]["cuadre"] == concar["_asiento"]["cuadre"]


def test_las_lineas_no_llevan_vocabulario_legacy():
    lineas = api.generar_asiento(casos(), driver="asiento_contable", imputacion=IMPUTACION_CASOS)["asiento"]
    assert all(not {"sub_diario", "correlativo"} & set(linea) for linea in lineas)
    assert all(linea["documento"].get("tipo_cp") and "tipo" not in linea["documento"] for linea in lineas)
    assert all("tipo" not in (linea.get("referencia") or {}) for linea in lineas)
    detraccion = [linea for linea in lineas if linea["rol"] == "detraccion"]
    assert detraccion, "el golden trae una factura con detracción"
    assert all(linea["documento"]["serie_numero"] != "999999999" for linea in detraccion)
    assert all(linea["detraccion"]["codigo"] and "codigo_interno" not in linea["detraccion"] for linea in detraccion)


def test_el_desglose_tributario_y_la_contraparte_viajan():
    """Lo que el asiento por sí solo no puede decir, y que hasta la 3.9 se perdía sin aviso.

    Una compra de 100 gravado más 50 exonerado produce **una sola línea de gasto de 150**: la contabilidad es
    correcta, pero quien recibe el archivo no puede separar el desglose ni comprobar que el IGV de 18 corresponde a
    100 y no a 150. Y el nombre de la contraparte viajaba por accidente —dentro de la glosa, y solo cuando el
    concepto venía vacío—: con un concepto propio desaparecía del archivo y el ERP se quedaba con el RUC a secas.
    """
    documento = casos()
    c = documento["comprobantes"][0]
    c.update(base_gravada="100.00", igv="18.00", exonerado="50.00", total="168.00",
             concepto="ALQUILER DE ANDAMIOS ENERO", contraparte_nombre="MAYORISTA NACIONAL SAC")
    r = api.exportar(documento, driver="asiento_contable", imputacion=IMPUTACION_CASOS)
    d = json.loads(base64.b64decode(r["contenido_base64"]))

    assert list(d) == ["open_accounting", "libro", "comprobantes", "asiento", "_exportacion"]
    comprobante = d["comprobantes"][0]
    assert comprobante["exonerado"] == "50.00", "el asiento no puede decir qué parte no estaba gravada"
    assert comprobante["base_gravada"] == "100.00" and comprobante["igv"] == "18.00"
    assert comprobante["contraparte_nombre"] == "MAYORISTA NACIONAL SAC"
    assert comprobante["concepto"] == "ALQUILER DE ANDAMIOS ENERO"
    # Y el asiento sigue siendo el mismo: la línea del gasto es una sola, por los 150.
    principal = [linea for linea in d["asiento"] if linea["rol"] == "principal"][0]
    assert principal["importe"] == "150.00"


def test_la_nota_dice_por_que_se_emitio():
    """El motivo del Catálogo 09 decide el tratamiento, y una nota asentada no lo lleva escrito en ninguna línea."""
    documento = casos()
    notas = [c for c in documento["comprobantes"] if c["tipo_cp"] in ("07", "87")]
    assert notas, "el golden trae una nota de crédito"
    notas[0]["tipo_nota"] = "06"
    r = api.exportar(documento, driver="asiento_contable", imputacion=IMPUTACION_CASOS)
    d = json.loads(base64.b64decode(r["contenido_base64"]))
    de_la_nota = [c for c in d["comprobantes"] if c["tipo_cp"] in ("07", "87")][0]
    assert de_la_nota["tipo_nota"] == "06"
    assert de_la_nota["ref_serie"] and de_la_nota["ref_numero"], "y a qué comprobante apunta"


def test_el_documento_vuelve_a_entrar_y_da_el_mismo_asiento():
    """La prueba de que el documento se basta: sale del motor y vuelve a entrar dando lo mismo, bit a bit.

    Es lo que un ERP necesita para no depender de haber guardado nada más, y lo que era imposible antes de que la
    cabecera llevara los ocho hechos que faltaban: sin el vencimiento la validación se detenía en
    `VENCIMIENTO_FALTA`, sin el tipo de cambio en `TC_FALTA` y sin los `ref_*` en `NOTA_SIN_REFERENCIA`.

    **El límite, y es a propósito**: la imputación no viaja en el documento —el esquema exigiría `id_externo` en
    todos los comprobantes— así que quien quiera el mismo asiento pasa la misma imputación que la primera vez. Sin
    ella, el mes se detiene pidiendo la cuenta, que es lo correcto: la cuenta es una decisión, no un hecho.
    """
    ida = api.generar_asiento(casos(), driver="asiento_contable", imputacion=IMPUTACION_CASOS)
    archivo = json.loads(api.exportar_archivo(casos(), driver="asiento_contable",
                                              imputacion=IMPUTACION_CASOS).contenido)

    vuelta = api.generar_asiento(archivo, driver="asiento_contable", imputacion=IMPUTACION_CASOS)
    assert vuelta["asiento"] == ida["asiento"]
    assert vuelta["_asiento"]["huella"] == ida["_asiento"]["huella"]
    assert vuelta["_asiento"]["comprobantes"] == ida["_asiento"]["comprobantes"]

    assert "imputaciones" not in archivo
    with pytest.raises(api.SinCuenta):
        api.generar_asiento(archivo, driver="asiento_contable")


def test_la_constancia_pendiente_no_viaja_como_comodin():
    """El `999999999` es un apaño peruano para llenar una columna obligatoria, y no un número de depósito.

    Se colaba en el perfil del estándar: el flag solo suprimía el código interno, y la constancia se resolvía igual
    para los dos vocabularios. Un ERP de fuera recibía un vóucher que no existe y no tenía forma de saberlo — y el
    test de al lado no lo veía, porque solo mira el documento comodín y no el bloque de la detracción.

    Con constancia de verdad pegada, el número sale tal cual: lo que se quita es el comodín, no el dato."""
    lineas = api.generar_asiento(casos(), driver="asiento_contable", imputacion=IMPUTACION_CASOS)["asiento"]
    detraccion = [linea for linea in lineas if linea["rol"] == "detraccion"]
    assert detraccion, "el golden trae una factura con detracción"
    assert all("nro_constancia" not in linea["detraccion"] for linea in detraccion),         "sin depósito documentado la clave no viaja: un comodín es una afirmación falsa"

    # Y al legacy no se le quita: su columna es obligatoria y el comodín es lo que CONCAR espera.
    legacy = api.generar_asiento(casos(), driver="concar", imputacion=IMPUTACION_CASOS)["asiento"]
    comodines = [linea for linea in legacy if linea["rol"] == "detraccion"]
    assert all(linea["detraccion"]["nro_constancia"] == "999999999" for linea in comodines)


def test_una_constancia_de_verdad_si_viaja():
    """Lo que se descarta es el comodín; un depósito documentado sale con su número y su fecha."""
    documento = casos()
    for c in documento["comprobantes"]:
        if (c.get("detraccion") or {}).get("codigo"):
            c["detraccion"] = {**c["detraccion"], "nro_constancia": "00123456789", "fecha_constancia": "2026-08-20"}
    lineas = api.generar_asiento(documento, driver="asiento_contable", imputacion=IMPUTACION_CASOS)["asiento"]
    detraccion = [linea for linea in lineas if linea["rol"] == "detraccion"]
    assert detraccion
    assert all(linea["detraccion"]["nro_constancia"] == "00123456789" for linea in detraccion)
    assert all(linea["detraccion"]["fecha_constancia"] == "2026-08-20" for linea in detraccion)


def test_un_tipo_sin_sigla_no_detiene_a_un_erp():
    """Un ERP no necesita la sigla de CONCAR: le basta el código SUNAT. Al CSV, que habla legacy, sí lo detiene."""
    sin_sigla = {"csv": {"tipos": {"01": {"sigla": ""}}}}
    with pytest.raises(api.SinSigla):
        api.generar_asiento(casos(), driver="csv", configuracion=sin_sigla, imputacion=IMPUTACION_CASOS)
    assert api.generar_asiento(casos(), driver="asiento_contable", imputacion=IMPUTACION_CASOS)["asiento"]


def test_exporta_el_documento_del_estandar_y_valida_su_esquema():
    jsonschema = pytest.importorskip("jsonschema")
    respuesta = api.exportar(casos(), driver="asiento_contable", imputacion=IMPUTACION_CASOS)
    documento = json.loads(base64.b64decode(respuesta["contenido_base64"]))
    jsonschema.Draft202012Validator(api.esquema_open_accounting()).validate(documento)
    assert documento["asiento"] and respuesta["resumen"]["sub_diarios"] == {}
    assert respuesta["_exportacion"]["huella"] and respuesta["_exportacion"]["comprobantes"][0]["lineas"]


def test_el_archivo_se_basta_solo_para_no_repetir_un_comprobante():
    """El archivo lleva `_exportacion` en su raíz (3.1), y esto es lo que hace que sirva a quien NO llama al motor.

    Hasta la 3.1 el documento tenía tres claves y la huella vivía solo en la respuesta del API, así que quien
    recibiera el JSON —por correo, en una carpeta— se quedaba sin la clave con la que reconocer lo que ya había
    importado. `INTEGRAR.md` le pide a un ERP justamente eso, «la identidad y la huella de cada comprobante como
    clave para no repetir», y por la vía del archivo era imposible de seguir.

    Y lo que va dentro es LO MISMO que dice el API, no una versión reducida: las dos salen de
    `asiento.exportacion_de`."""
    respuesta = api.exportar(casos(), driver="asiento_contable", imputacion=IMPUTACION_CASOS)
    documento = json.loads(base64.b64decode(respuesta["contenido_base64"]))

    dentro = documento["_exportacion"]
    assert dentro["huella"] == respuesta["_exportacion"]["huella"]
    assert dentro["comprobantes"] == respuesta["_exportacion"]["comprobantes"]
    assert dentro["driver"] == "asiento_contable" and dentro["motor"]

    # Cada comprobante: su identidad, su tramo y la huella de ese tramo. Los tramos parten las líneas enteras.
    tramos = [c["lineas"] for c in dentro["comprobantes"]]
    assert tramos[0][0] == 0 and tramos[-1][1] == len(documento["asiento"])
    assert all(a[1] == b[0] for a, b in zip(tramos, tramos[1:])), "los tramos dejan hueco o se solapan"
    assert all(c["identidad"]["ruc"] and c["huella"] for c in dentro["comprobantes"])


def test_lo_que_el_archivo_no_puede_saber_no_se_inventa():
    """`fecha` la pone quien llama a `exportar` y `archivo` es el nombre del propio archivo: ninguna de las dos es
    un hecho del asiento, así que el documento no las lleva. Decirlo con un test evita que alguien las añada
    «por simetría» con la respuesta del API."""
    documento = json.loads(base64.b64decode(
        api.exportar(casos(), driver="asiento_contable", imputacion=IMPUTACION_CASOS)["contenido_base64"]))
    assert set(documento["_exportacion"]) == {"driver", "motor", "huella", "comprobantes"}


def test_el_diagnostico_de_un_erp_no_mira_vocabulario_legacy():
    diagnostico = api.diagnosticar(casos(), driver="asiento_contable", imputacion=IMPUTACION_CASOS)
    assert diagnostico["listo_para_exportar"] is True
    assert diagnostico["exige"] == ["cuenta_contable", "detraccion"] and diagnostico["sub_diarios"] == {}
    assert "sin_sigla" not in diagnostico["faltantes"] and "sin_codigo_de_moneda" not in diagnostico["faltantes"]


def test_un_erp_no_tiene_seccion_propia_en_la_configuracion():
    """Lee lo general, que es contabilidad; no tiene siglas ni sub-diarios que configurar."""
    assert api.errores_de_configuracion({"asiento_contable": {}}) == [
        "`asiento_contable` no tiene sección: ese sistema no tiene nada propio que configurar, solo lo general"]
    assert "asiento_contable" not in api.configuracion_por_defecto()


def test_el_contrato_de_un_driver_neutral():
    assert contrato.incumplimientos(asiento_contable) == []
    assert (contrato.vocabulario(asiento_contable), contrato.canal(asiento_contable)) == ("neutral", "erp")
    assert contrato.exige(asiento_contable) == {"cuenta_contable", "detraccion"}
    assert api.drivers_disponibles()["asiento_contable"]["vocabulario"] == "neutral"
    assert api.drivers_disponibles()["concar"]["vocabulario"] == "legacy"

    def copia(**cambios) -> types.ModuleType:
        falso = types.ModuleType("falso")
        falso.__dict__.update({k: v for k, v in vars(asiento_contable).items() if not k.startswith("__")})
        falso.__dict__.update(cambios)
        return falso

    assert any("canal es `erp`" in p for p in contrato.incumplimientos(copia(CANAL="legacy")))
    assert any("no existe" in p for p in contrato.incumplimientos(copia(VOCABULARIO="otro")))
    legacy = contrato.incumplimientos(copia(CONFIGURACION=CONFIGURACION_DEL_ASIENTO))
    assert any("no declara vocabulario legacy" in p for p in legacy)
    assert any("código de la moneda" in p for p in contrato.incumplimientos(copia(EXIGE=frozenset({"moneda"}))))

def test_el_nombre_viejo_del_driver_ya_no_existe():
    """La 4.0 retiró `asiento_neutral`, el nombre que este driver tuvo hasta la 3.10.

    Avisó durante toda la 3.x con `RutaObsoleta`, y era necesario: el paquete está en PyPI y una aplicación en
    producción fija su versión, así que sin el alias se habría roto con un `ValueError` el día que adoptara la 3.10, y
    ninguna guarda de este repositorio lo habría visto, porque el valor de `driver` no está en ningún enum. Cumplido el
    aviso, se va: ni el nombre resuelve ni existe el módulo talón que sostenía las cuatro formas de importarlo.

    Lo que NO se va con él es el mecanismo: `drivers.ALIAS` se queda vacío para el próximo renombrado."""
    import importlib

    from contaperu import drivers

    with pytest.raises(ValueError, match="Driver desconocido"):
        drivers.obtener("asiento_neutral")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("contaperu.drivers.asiento_neutral")
    assert "asiento_neutral" not in drivers.ALIAS and not hasattr(drivers, "asiento_neutral")
    # Los archivos ya exportados llevan ese nombre DENTRO, en `_exportacion.driver`, y eso no lo arregla ninguna
    # versión: el alias cubría la entrada, no los datos que ya están en disco.


def test_el_alias_de_un_driver_sigue_en_pie(monkeypatch):
    """No queda ningún nombre viejo, pero el circuito que resuelve uno tiene que seguir funcionando: es lo que se usará
    la próxima vez que un destino se renombre. Se prueba con un nombre de mentira, para no tener que deprecar nada de
    verdad solo por cubrirlo — el mismo trato que `_obsoleto` recibe en `test_api.py`.

    Lo que se comprueba es lo que costó acertar: que resuelva al driver nuevo, que avise con `RutaObsoleta` y que
    **no** aparezca como un destino más en la lista que publica el registro."""
    from contaperu import RutaObsoleta
    from contaperu import drivers

    monkeypatch.setitem(drivers.ALIAS, "nombre_de_antes", "asiento_contable")
    with pytest.warns(RutaObsoleta, match="asiento_contable"):
        assert drivers.obtener("nombre_de_antes") is drivers.obtener("asiento_contable")
    assert "nombre_de_antes" not in drivers.DRIVERS
    assert "nombre_de_antes" not in api.drivers_disponibles()
