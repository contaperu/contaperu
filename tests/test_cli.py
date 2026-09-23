"""La CLI genera el TXT del SIRE desde XML locales, sin API ni portal."""
import json
import zipfile

from contaperu.puertas import cli
from util import GOLDEN, XML


def test_generar_desde_xml(tmp_path, capsys):
    salida = tmp_path / "salida"
    codigo = cli.main([
        "generar", "--tipo", "venta", "--ruc", "20131312955", "--razon", "EMISOR DE PRUEBA S.A.C.",
        "--periodo", "202601", "--salida", str(salida), "--json", str(tmp_path / "datos.json"),
        str(XML / "20131312955-01-F001-123.xml"), str(XML / "20131312955-03-B001-55.xml"),
        str(XML / "R-20131312955-01-F001-123.xml"), str(tmp_path / "no-existe.xml"),
    ])
    out = capsys.readouterr().out
    assert codigo == 0
    assert "1 ignorados" in out and "no-existe.xml: No existe" in out
    nombres = sorted(p.name for p in salida.iterdir())
    # "todas" = los drivers de TXT, que desde la muerte del PLE es solo el SIRE
    assert nombres == [
        "LE2013131295520260100140400021112.TXT", "LE2013131295520260100140400021112.zip",
    ]
    with zipfile.ZipFile(salida / "LE2013131295520260100140400021112.zip") as z:
        assert z.namelist() == ["LE2013131295520260100140400021112.TXT"]
    datos = json.loads((tmp_path / "datos.json").read_text(encoding="utf-8"))
    assert [c["numero"] for c in datos["comprobantes"]] == ["123", "55"]


def test_errores_bloquean_salvo_flag(tmp_path, capsys):
    args = ["generar", "--tipo", "venta", "--ruc", "20131312955", "--razon", "X", "--periodo", "202601",
            "--driver", "sire", "--salida", str(tmp_path / "s"), str(XML / "20131312955-01-F001-124.xml")]
    assert cli.main(args) == 1                      # USD sin tipo de cambio → error
    assert "TC_FALTA" in capsys.readouterr().out
    assert not (tmp_path / "s").exists()
    assert cli.main(args + ["--incluir-errores"]) == 0
    assert (tmp_path / "s" / "LE2013131295520260100140400021112.zip").exists()


def test_verificar_un_driver_propio(tmp_path, monkeypatch, capsys):
    """Un driver de terceros se comprueba contra el contrato antes de registrarlo: 0 si cumple, 1 si le falta algo
    (y dice qué), 2 si ni siquiera se puede importar."""
    assert cli.main(["verificar-driver", "drivers_de_prueba.diario_json"]) == 0
    assert "CUMPLE" in capsys.readouterr().out
    (tmp_path / "driver_a_medias.py").write_text('NOMBRE = "a_medias"\nCANAL = "legacy"\n', encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    assert cli.main(["verificar-driver", "driver_a_medias"]) == 1
    salida = capsys.readouterr().out
    assert "NO cumple" in salida and "!!" in salida
    assert cli.main(["verificar-driver", "no_existe_este_driver"]) == 2


def test_la_cli_dice_que_se_configura(capsys):
    """Para escribir un --config sin adivinar: lo que se configura de un sistema, o los valores por defecto."""
    assert cli.main(["configuracion", "--driver", "contasis"]) == 0
    descripcion = json.loads(capsys.readouterr().out)
    assert descripcion["sistema"] == "contasis" and descripcion["campos"][0]["clave"] == "medio_pago"
    assert [c["clave"] for c in descripcion["general"]["campos"]][:2] == ["cuentas", "usa_centros_costo"]
    assert cli.main(["configuracion", "--por-defecto", "--driver", "contasis"]) == 0
    partida = json.loads(capsys.readouterr().out)
    assert partida["contasis"] == {"medio_pago": "001", "columnas": {"centro_costo": ["centro_costo"]}}
    assert "concar" not in partida and partida["cuentas"]["igv"] == "401111"


def _golden_con_ids(tmp_path):
    """El golden con un `id_externo` por comprobante, escrito en tmp: por ahí lo alcanza la imputación."""
    doc = json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))
    for n, c in enumerate(doc["comprobantes"], 1):
        c["id_externo"] = f"fila-{n}"
    archivo = tmp_path / "mes_con_ids.json"
    archivo.write_text(json.dumps(doc), encoding="utf-8")
    return archivo


def imputacion_del_golden(tmp_path, cuenta: str = "659999") -> list[str]:
    """`--imputacion <archivo>` con los tres comprobantes del golden imputados a la misma cuenta.

    Hasta la 3.0 esto se conseguía con `cuentas.gasto` en el --config: una cuenta de la EMPRESA que el motor le
    ponía a quien no traía ninguna. Desde la 3.0 la cuenta es del comprobante y llega por aquí."""
    doc = json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8"))
    archivo = tmp_path / "imputacion.json"
    archivo.write_text(json.dumps({f"fila-{n}": {"cuenta_contable": cuenta}
                                   for n in range(1, len(doc["comprobantes"]) + 1)}), encoding="utf-8")
    return ["--imputacion", str(archivo)]


def test_desde_json(tmp_path):
    assert cli.main(["desde-json", str(GOLDEN / "compras_202601.json"), "--driver", "sire", "--salida", str(tmp_path)]) == 0
    assert (tmp_path / "LE2060123456720260100080400021112.TXT").read_bytes().count(b"\r\n") == 3


def test_desde_json_llega_a_los_drivers_de_asientos(tmp_path, capsys):
    """La puerta de la CLI alcanza a TODOS los drivers, no solo a los de texto.

    Hasta la 0.7 pedir `--driver csv` o `concar` reventaba con un TypeError: la CLI nunca pasaba la
    configuración ni los correlativos que un driver de asientos necesita. Ahora entran por --config y
    los correlativos arrancan en 1, igual que en `operaciones.exportar`. Es lo que hace que un driver
    de la comunidad enchufado por entry point se pueda probar desde la terminal.
    """
    golden = str(_golden_con_ids(tmp_path))
    config = tmp_path / "config.json"
    # CON BOM a propósito: es lo que escriben el Bloc de notas y `Out-File` de PowerShell en Windows,
    # que es donde trabaja un contador peruano. Un JSON con BOM tiene que leerse igual que sin él.
    config.write_bytes(b"\xef\xbb\xbf" + json.dumps({"usa_centros_costo": False}).encode())
    salida = tmp_path / "s"
    imputado = imputacion_del_golden(tmp_path)
    assert cli.main(["desde-json", golden, "--driver", "csv", "--salida", str(salida), "--config", str(config)]
                    + imputado) == 0
    csv = (salida / "CSV_COMPRAS_202601_20601234567.csv").read_bytes().decode("utf-8-sig")
    assert csv.startswith("sub_diario;correlativo;fecha;cuenta") and csv.count("\r\n") == 1 + 9   # 3 facturas × 3 líneas
    assert cli.main(["desde-json", golden, "--driver", "concar", "--salida", str(salida), "--config", str(config)]
                    + imputado) == 0
    assert (salida / "CONCAR_COMPRAS_202601_20601234567.xlsx").read_bytes()[:2] == b"PK"
    assert "concar concar_xlsx   3 comprobantes" in capsys.readouterr().out
    # Sin la cuenta de gasto el driver se niega, y la CLI dice a dónde ir a mirar en vez de un traceback.
    assert cli.main(["desde-json", golden, "--driver", "csv", "--salida", str(salida)]) == 1
    assert "contaperu diagnosticar" in capsys.readouterr().err


def test_diagnosticar_dice_que_falta_y_luego_que_esta_listo(tmp_path, capsys):
    """Antes de generar nada: el golden no trae cuenta de gasto, y con la del RUC queda listo.

    Sin `--config` vale la cuenta de gasto que trae CONCAR (2.5), así que lo que falta ya no es la cuenta sino el
    CENTRO: esa cuenta es de la clase 63, y las 63 llevan centro de costo. Para ver la falta de cuenta hay que
    decir que no hay ninguna, que es lo que hace quien prefiere que le avisen."""
    golden = str(_golden_con_ids(tmp_path))
    sin_centros = tmp_path / "sin_centros.json"
    sin_centros.write_text(json.dumps({"usa_centros_costo": False}), encoding="utf-8")
    # Sin imputar, faltan las tres cuentas: desde la 3.0 no hay ninguna de la empresa que las supla.
    assert cli.main(["diagnosticar", golden, "--config", str(sin_centros)]) == 1
    out = capsys.readouterr().out
    assert "NO está listo: 3 sin cuenta contable" in out and "Sin cuenta contable:" in out
    imputado = imputacion_del_golden(tmp_path)
    assert cli.main(["diagnosticar", golden] + imputado) == 1
    assert "NO está listo: 3 sin centro de costo" in capsys.readouterr().out
    assert cli.main(["diagnosticar", golden, "--config", str(sin_centros)] + imputado) == 0
    out = capsys.readouterr().out
    assert "LISTO para exportar: 3 comprobantes." in out and "Sub-diario 11 (Compras): 3 comprobantes desde el 1" in out
    # Para el SIRE no hay cuentas que pedir: el mismo golden está listo tal cual.
    assert cli.main(["diagnosticar", golden, "--driver", "sire"]) == 0


def test_la_consola_de_windows_no_tumba_el_cli(monkeypatch):
    """La consola de Windows es cp1252 y el CLI imprime flechas y tildes. Que se caiga al
    IMPRIMIR, con los archivos ya escritos, seria absurdo."""
    from contaperu.puertas.cli import _consola_utf8

    class SinReconfigure:
        encoding = "cp1252"

    monkeypatch.setattr("sys.stdout", SinReconfigure())
    _consola_utf8()          # no revienta aunque el flujo no sepa reconfigurarse


def test_sin_centro_la_cli_remite_a_diagnosticar(tmp_path, capsys):
    """Desde la 0.8 CONCAR se niega sin centro de costo donde la cuenta lo lleva; la CLI lo dice sin traceback."""
    golden = str(_golden_con_ids(tmp_path))
    config = tmp_path / "config.json"
    config.write_text(json.dumps({}), encoding="utf-8")     # centros encendidos
    assert cli.main(["desde-json", golden, "--driver", "concar", "--salida", str(tmp_path / "s"),
                     "--config", str(config)] + imputacion_del_golden(tmp_path)) == 1
    err = capsys.readouterr().err
    assert "sin centro de costo" in err and "contaperu diagnosticar" in err and "Traceback" not in err


def test_la_imputacion_entra_por_la_terminal(tmp_path, capsys):
    """La imputación de cada documento llega aparte, por `id_externo`, igual que por la fachada: --imputacion en
    `desde-json` y en `diagnosticar`. Una llave que no es de ningún documento se rechaza antes de escribir nada."""
    documento = _golden_con_ids(tmp_path)
    config, imputacion = tmp_path / "config.json", tmp_path / "propia.json"
    config.write_text(json.dumps({"usa_centros_costo": False}), encoding="utf-8")
    imputacion.write_text(json.dumps({"fila-1": {"cuenta_contable": "636301"},
                                      "fila-2": {"cuenta_contable": "659999"},
                                      "fila-3": {"cuenta_contable": "659999"}}), encoding="utf-8")
    salida = tmp_path / "s"
    orden = ["desde-json", str(documento), "--driver", "csv", "--salida", str(salida), "--config", str(config)]
    assert cli.main(orden + ["--imputacion", str(imputacion)]) == 0
    csv = (salida / "CSV_COMPRAS_202601_20601234567.csv").read_bytes().decode("utf-8-sig")
    assert csv.count(";636301;D;") == 1 and csv.count(";659999;D;") == 2

    # Con una imputación que solo alcanza al primero, a los otros dos les falta la cuenta: desde la 3.0 no hay
    # ninguna de la empresa que se la dé.
    solo_uno = tmp_path / "solo_uno.json"
    solo_uno.write_text(json.dumps({"fila-1": {"cuenta_contable": "636301"}}), encoding="utf-8")
    assert cli.main(["diagnosticar", str(documento), "--imputacion", str(solo_uno),
                     "--config", str(config)]) == 1
    assert "NO está listo: 2 sin cuenta contable" in capsys.readouterr().out

    imputacion.write_text(json.dumps({"fila-9": {"cuenta_contable": "636301"}}), encoding="utf-8")
    assert cli.main(orden + ["--imputacion", str(imputacion)]) == 2
    assert "fila-9" in capsys.readouterr().err


def test_un_pdf_por_la_terminal_queda_pendiente_de_leer(tmp_path, capsys):
    """Hito 0.7: por la CLI el PDF llega con su nombre, y cuenta igual que por el protocolo."""
    pdf = tmp_path / "factura.pdf"
    pdf.write_bytes(b"%PDF-1.7\n1 0 obj")
    codigo = cli.main(["generar", "--tipo", "venta", "--ruc", "20131312955", "--razon", "EMISOR DE PRUEBA S.A.C.",
                       "--periodo", "202601", "--salida", str(tmp_path / "s"), str(pdf)])
    salida = capsys.readouterr().out
    assert codigo == 1 and "1 PDF/imagen (pendientes de IA) · 0 con error" in salida


# ── `verificar-documento`: el espejo de `verificar-driver`, para quien NO usa el motor ──────────────────────────

def _escribir(tmp_path, documento: dict):
    ruta = tmp_path / "documento.json"
    ruta.write_text(json.dumps(documento, ensure_ascii=False), encoding="utf-8")
    return str(ruta)


LIBRO_OK = {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202601", "tipo": "compra"}


def test_un_documento_conforme_sale_con_cero(tmp_path, capsys):
    """Lo que un tercero necesita para comprobar lo que produce sin escribirle a nadie, que es lo que el LEEME del
    estándar ofrece. Hasta la 3.1 el esquema estaba publicado y la única forma de correrlo era clonar el
    repositorio y lanzar pytest."""
    codigo = cli.main(["verificar-documento", _escribir(tmp_path, {"open_accounting": "1.0", "libro": LIBRO_OK})])
    assert codigo == 0 and "CONFORME" in capsys.readouterr().out


def test_lo_que_el_esquema_rechaza_es_un_ERROR(tmp_path, capsys):
    documento = {"open_accounting": "1.0", "libro": LIBRO_OK,
                 "asiento": [{"cuenta": "631101", "debe_haber": "X", "importe": "100.00", "clase": "gasto"}]}
    codigo = cli.main(["verificar-documento", _escribir(tmp_path, documento)])
    salida = capsys.readouterr().out
    assert codigo == 1 and "NO conforme: 1 cosa que corregir" in salida
    assert "debe_haber" in salida and "'D', 'H'" in salida


def test_lo_que_solo_saben_los_catalogos_es_un_AVISO(tmp_path, capsys):
    """La distinción es la del propio estándar y por eso se enseña en dos listas: un **error** es no cumplir el
    esquema, y ahí no hay nada que interpretar. Un **aviso** es lo que el esquema no puede decir porque vive en
    los catálogos — un `rol` desconocido se degrada y no rompe la línea; un `tipo` de libro desconocido sí rompe,
    porque de él dependen las columnas de cada registro."""
    documento = {"open_accounting": "1.0", "libro": {**LIBRO_OK, "tipo": "diario"},
                 "asiento": [{"cuenta": "631101", "debe_haber": "D", "importe": "100.00", "clase": "gasto",
                              "rol": "inventado"}]}
    codigo = cli.main(["verificar-documento", _escribir(tmp_path, documento)])
    salida = capsys.readouterr().out
    assert codigo == 0, "los catálogos avisan, no rechazan: el esquema es quien dice conforme o no"
    assert "SÍ rompe" in salida and "inventado" in salida and "No rompe" in salida
