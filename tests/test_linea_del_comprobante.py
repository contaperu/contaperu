"""La línea del comprobante y el driver CSV que la escribe.

Es la pieza que convierte a este proyecto en un traductor y no en un exportador de CONCAR:
el asiento sale del vocabulario de un ERP concreto y entra en el del estándar.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from contaperu import asiento as asi
from contaperu.configuracion import CONFIG_POR_DEFECTO
from contaperu.drivers import concar as driver_concar
from contaperu.drivers.concar import proyeccion
from contaperu.pipeline import salida as gen
from contaperu import api
from contaperu.pipeline import preparacion as prep
from contaperu.drivers import csv as driver_csv
from contaperu.modelo import Comprobante, Libro
from util import comprobante, con_imputaciones, en_secciones

def configuracion(config_contable: dict | None = None) -> dict:
    """La configuración aplicada para CONCAR (la del entorno sobre la de por defecto) con las imputaciones de las
    pruebas. Se escribe plana y se guarda en su sección (`util.en_secciones`)."""
    return con_imputaciones(prep.config_aplicada(en_secciones(config_contable, "concar"), "concar"))


CONTAB = configuracion(None)
MES = (date(2026, 8, 1), date(2026, 8, 31))
ESQUEMA = Path(__file__).resolve().parents[1] / "estandar" / "open-accounting.schema.json"


def factura(**k) -> Comprobante:
    base = dict(tipo_cp="01", serie="E001", numero="871", fecha_emision="2026-08-10",
                fecha_vencimiento="2026-08-27", contraparte_doc="20602222226",
                contraparte_nombre="PROVEEDOR DE PRUEBA SAC", base_gravada="4200", igv="756",
                total="4956", concepto="SERVICIO DE TRANSPORTE", cuenta_contable="659999",
                centro_costo="CC-64")
    base.update(k)
    return comprobante(**base)


def test_el_centro_de_referencia_viaja_como_anexo_auxiliar():
    """Con la X del gasto elegida en `columnas`, el centro de una cuenta que no lo lleva en M sale del asiento
    por el campo `anexo_auxiliar` del estándar, no por `centro_costo`. Es correcto —la X es la
    X— pero conviene fijarlo aquí y no descubrirlo desde el MCP o desde el driver CSV."""
    columnas = ["centro_costo", "anexo_auxiliar", "anexo_auxiliar_del_tercero"]
    ref = configuracion({"columnas": {"centro_costo": columnas}})
    filas = driver_concar.filas_de_comprobante(factura(cuenta_contable="603201"), ref, MES, "080001")
    gasto = driver_concar.desde_fila(filas[0])
    assert gasto.centro_costo == "" and gasto.anexo_auxiliar == "CC-64"


def test_la_linea_neutral_dice_lo_mismo_que_la_columna():
    filas = driver_concar.filas_de_comprobante(factura(), CONTAB, MES, "080084")
    gasto, igv, proveedor = driver_concar.a_lineas(filas, CONTAB)

    assert gasto.cuenta == "659999" and gasto.debe_haber == "D" and gasto.importe == "4200.00"
    assert gasto.centro_costo == "CC-64" and gasto.moneda == "PEN"
    assert gasto.sub_diario == "11" and gasto.correlativo == "080084"
    assert gasto.fecha == "2026-08-10"
    # Al leer vuelven los DOS: el `tipo_cp` de SUNAT, que es lo que la línea lleva y de lo que el driver saca su
    # columna R —sin él la vuelta no sería vuelta—, y la sigla literal del archivo, que es un dato de ese archivo.
    assert gasto.documento == {"tipo": "FT", "tipo_cp": "01", "serie_numero": "E001-871",
                               "fecha_emision": "2026-08-10", "fecha_vencimiento": "2026-08-27"}
    assert igv.cuenta == "401111" and igv.glosa == gasto.glosa, "la misma glosa en todas las lineas"
    assert proveedor.cuenta == "421201" and proveedor.debe_haber == "H"
    assert proveedor.contraparte_doc == "20602222226" and proveedor.anexo_auxiliar == "CC-64"


def test_el_codigo_de_moneda_del_erp_vuelve_a_iso():
    """En el Excel la moneda es 'MN' o 'US'; en el estándar, PEN y USD."""
    pen = driver_concar.a_lineas(driver_concar.filas_de_comprobante(factura(), CONTAB, MES, "080001"), CONTAB)[0]
    usd = driver_concar.a_lineas(driver_concar.filas_de_comprobante(factura(moneda="USD", tipo_cambio="3.5"), CONTAB, MES, "080002"), CONTAB)[0]
    assert pen.moneda == "PEN" and usd.moneda == "USD" and usd.tipo_cambio == "3.5"


def test_la_linea_de_detraccion_lleva_su_bloque():
    filas = driver_concar.filas_de_comprobante(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084")
    lineas = driver_concar.a_lineas(filas, CONTAB)
    assert len(lineas) == 5
    det = lineas[-1]
    assert det.cuenta == "421203" and det.debe_haber == "H" and det.importe == "198.00"
    # La sigla sale de la columna R, que es de CONCAR: al volver a línea se recupera del archivo, aunque el asiento
    # ya no la escriba. El código, en cambio, vuelve al de SUNAT: la AI lleva el interno de la T.G. 28.
    assert det.documento["tipo"] == "DR" and det.documento["serie_numero"] == "999999999"
    assert det.detraccion == {"codigo": "027", "tasa": "4", "base": "4956.00"}
    assert det.glosa == lineas[0].glosa, "la misma glosa en todas las lineas, sin prefijo (2.2)"


def test_el_excel_de_concar_vuelve_a_su_excel_sin_perder_columnas():
    """Ida y vuelta COMPLETA: escribir, leer y volver a escribir da las mismas filas.

    Es lo que se rompió al mover la sigla al driver (4.0) y lo que ningún test veía: `fila()` pasó a sacar la columna
    R del `tipo_cp` de la línea, y el lector seguía devolviendo solo la sigla, así que una línea leída volvía al Excel
    con la R y la Z VACÍAS. El snapshot no lo veía porque solo mira la ida, y los tests de la vuelta miraban la línea
    y no el Excel que sale de ella."""
    for c in (factura(), factura(detraccion={"codigo": "027", "porcentaje": "4"}),
              factura(tipo_cp="07", serie="FC01", numero="9", ref_tipo_cp="01", ref_serie="E001", ref_numero="871",
                      ref_fecha="2026-08-01")):
        ida = driver_concar.filas_de_comprobante(c, CONTAB, MES, "080084")
        cab = proyeccion.cabecera_de(c)
        vuelta = [proyeccion.fila(ln, cab, CONTAB) for ln in driver_concar.a_lineas(ida, CONTAB)]
        for antes, despues in zip(ida, vuelta):
            for columna in ("R", "Z", "AI"):
                assert antes.get(columna, "") == despues.get(columna, ""), f"{columna} se pierde en la vuelta"


def test_la_columna_ai_vuelve_al_codigo_de_sunat():
    """Ida y vuelta por la T.G. 28. El interno mapeado vuelve por el mapa del contribuyente (`03799` -> `037`), y uno
    que la empresa no mapeó, por sus tres primeros dígitos, que es como se numera esa tabla. El lector devuelve lo que
    dice el estándar —el Catálogo 54—, no el código de un ERP."""
    config = dict(CONTAB, detraccion_codigos={**CONTAB.get("detraccion_codigos", {}), "037": "03799"})
    filas = driver_concar.filas_de_comprobante(factura(detraccion={"codigo": "037", "porcentaje": "10"}),
                                               config, MES, "080084")
    assert filas[-1]["AI"] == "03799"
    assert driver_concar.a_lineas(filas, config)[-1].detraccion["codigo"] == "037", "por el mapa"
    # Un interno que no está en el mapa: por los tres primeros dígitos.
    assert proyeccion._codigo_sunat_de("03101", {}) == "031"
    assert proyeccion._codigo_sunat_de("", {}) == "" and proyeccion._codigo_sunat_de("03", {}) == ""


def test_a_dict_no_arrastra_claves_vacias():
    linea = driver_concar.a_lineas(driver_concar.filas_de_comprobante(factura(), CONTAB, MES, "080001"), CONTAB)[1]  # el IGV
    d = linea.a_dict()
    assert "centro_costo" not in d and "referencia" not in d and "detraccion" not in d
    assert d["cuenta"] == "401111"


def test_las_lineas_validan_contra_el_estandar():
    """Lo que produce el motor tiene que caber en el bloque `asiento` de open-accounting."""
    validador = Draft202012Validator(json.loads(ESQUEMA.read_text(encoding="utf-8")))
    doc = {
        "open_accounting": "1.0",
        "libro": {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC",
                  "periodo": "202608", "tipo": "compra"},
        "asiento": [ln.a_dict() for ln in driver_concar.a_lineas(
            driver_concar.filas_de_comprobante(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084"),
            CONTAB)],
    }
    assert list(validador.iter_errors(doc)) == []


# --- el motor: la línea del comprobante como fuente (0.7) -------------------------------------

def test_las_dos_cuentas_del_sistema_se_leen_igual_y_con_su_respaldo():
    """`lineas_del_comprobante` es PÚBLICA, así que un ERP la llama con la configuración que quiera. Dos de las cuentas
    que necesita no vienen de la imputación sino de la configuración —la del IGV y la de la retención de 4ta— y hasta la
    5.1 se leían de dos formas distintas en líneas consecutivas: la segunda caía a su valor de fábrica y la primera se
    indexaba sin red.

    Con una `cuentas` incompleta, eso daba un `KeyError: 'igv'` **pelado**: no es un `ErrorContaperu`, así que quien
    atrapa los errores del motor no lo caza y le sale un error de Python en la cara. El espejo de esto en el
    diagnóstico (`resolucion.cuentas_del_asiento`) ya era simétrico, que es lo que delató la diferencia."""
    sin_las_dos = dict(CONTAB, cuentas={k: v for k, v in CONTAB["cuentas"].items()
                                       if k not in ("igv", "retencion_4ta")})
    lineas = asi.lineas_del_comprobante(factura(), sin_las_dos, MES, "080084")
    del_impuesto = next(ln for ln in lineas if ln.rol == "impuesto")
    assert del_impuesto.cuenta == CONFIG_POR_DEFECTO["cuentas"]["igv"] == "401111"

    # Y la de la retención, que ya lo hacía, para que las dos queden fijadas por el mismo test y no se separen otra vez.
    rh = factura(tipo_cp="02", retencion="160.00", igv="0.00", base_gravada="0.00",
                 exonerado="2000.00", total="2000.00")
    de_la_retencion = next(ln for ln in asi.lineas_del_comprobante(rh, sin_las_dos, MES, "150001")
                           if ln.rol == "retencion")
    assert de_la_retencion.cuenta == CONFIG_POR_DEFECTO["cuentas"]["retencion_4ta"] == "401721"

    # La clave de configuración NO se renombró con el rol en la 5.0: sigue siendo `retencion_4ta`, porque es la cuenta
    # que el contribuyente configura y renombrarla rompería la configuración de todos los integradores.
    assert "retencion_4ta" in CONFIG_POR_DEFECTO["cuentas"] and "retencion" not in CONFIG_POR_DEFECTO["cuentas"]


def test_la_linea_del_impuesto_dice_de_que_tributo_es():
    """Lo que hace que el rol `impuesto` no sea una pérdida respecto del `igv` al que reemplaza (5.0).

    El rol dice QUÉ HACE la línea y el bloque dice CUÁL es el tributo. Con el nombre dentro del rol no había forma de
    decir que una línea era del ISC o del ICBPER; con el bloque, el valor del rol es genérico y el catálogo de SUNAT
    pone la precisión. Mismo patrón que `detraccion`, que lo hace desde la 1.0 con su código y su tasa."""
    from contaperu import catalogos

    lineas = asi.lineas_del_comprobante(factura(), CONTAB, MES, "080084")
    del_impuesto = next(ln for ln in lineas if ln.rol == "impuesto")
    assert del_impuesto.impuesto == {"codigo": "1000"} == {"codigo": catalogos.TRIBUTO_IGV}
    assert del_impuesto.impuesto["codigo"] in catalogos.TRIBUTOS
    # El bloque es SOLO de su línea: ninguna otra lo lleva, como ninguna otra lleva la detracción.
    assert [ln.rol for ln in lineas if ln.impuesto] == ["impuesto"]
    # Y NO lleva tasa, a propósito: la del IGV ya viaja en `tasa_igv` y con otra convención —fracción frente a
    # porcentaje—, y el ICBPER no tiene ninguna porque es un importe por bolsa.
    assert "tasa" not in del_impuesto.impuesto and del_impuesto.tasa_igv


def test_la_linea_de_la_retencion_dice_de_que_tributo_y_de_que_categoria():
    """Sin la categoría, `retencion` sería PEOR que el `retencion_4ta` al que reemplaza: perdería el «de 4ta». Y el
    tributo no es el del IGV sino el 3000, Impuesto a la Renta, que estaba en el Catálogo 05 y no en el motor.

    La categoría es `4` con certeza y no por deducción: el motor solo emite esta línea desde un recibo por honorarios,
    que es trabajo independiente —el artículo 33 del TUO de la Ley del Impuesto a la Renta—."""
    from contaperu import catalogos

    rh = factura(tipo_cp="02", retencion="160.00", igv="0.00", base_gravada="0.00",
                 exonerado="2000.00", total="2000.00")
    lineas = asi.lineas_del_comprobante(rh, CONTAB, MES, "150001")
    de_la_retencion = next(ln for ln in lineas if ln.rol == "retencion")
    assert de_la_retencion.retencion == {"codigo": "3000", "categoria": "4"}
    assert de_la_retencion.retencion["codigo"] == catalogos.TRIBUTO_RENTA
    assert de_la_retencion.retencion["categoria"] == catalogos.CATEGORIA_RENTA_4TA
    # El IMPORTE retenido no está aquí: está donde está el de cualquier línea, en `importe`. Este bloque dice de qué
    # es, y `comprobante.retencion` dice cuánto. Confundirlos es el error que costó un mes sin su línea de retención.
    assert de_la_retencion.importe == "160.00" and "monto" not in de_la_retencion.retencion
    assert [ln.rol for ln in lineas if ln.retencion] == ["retencion"]


def test_el_motor_dice_el_rol_y_el_codigo_sunat_de_cada_linea():
    lineas = asi.lineas_del_comprobante(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084")
    assert [ln.rol for ln in lineas] == ["principal", "impuesto", "tercero", "recorte", "detraccion"]
    assert all(ln.rol in asi.ROLES for ln in lineas)
    # La línea lleva el código de SUNAT y NO la sigla: `FT` es la T.G. 06 de CONCAR y la escribe su driver (4.0).
    assert lineas[0].documento["tipo_cp"] == "01" and "tipo" not in lineas[0].documento
    # La detracción no es un comprobante de SUNAT: su documento es el DR, sin código de la Tabla 10;
    # y su referencia es la propia factura, que sí lo tiene.
    assert "tipo_cp" not in lineas[-1].documento and lineas[-1].referencia["tipo_cp"] == "01"
    assert lineas[-1].detraccion["codigo"] == "027"


def test_la_linea_lleva_el_codigo_de_sunat_y_el_interno_lo_pone_cada_erp():
    """El `02702` es la Tabla General 28 de CONCAR: es de un ERP, no del asiento. Hasta la 3.10 el núcleo lo anotaba
    al lado del código de SUNAT —inventando el de SUNAT más «01» para lo que nadie hubiera mapeado— y se lo escribía
    igual al CSV y a STARSOFT, que trabajan con el Catálogo 54. Desde la 4.0 la línea lleva solo el de SUNAT, en los
    DOS vocabularios, y la traducción la hace `drivers.concar.proyeccion.codigo_interno_detraccion`."""
    for vocabulario in ("legacy", "neutral"):
        lineas = asi.lineas_del_comprobante(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES,
                                            "080084", vocabulario=vocabulario)
        det = lineas[-1].detraccion
        assert det["codigo"] == "027", vocabulario
        assert "codigo_interno" not in det, f"el interno de la T.G. 28 no es del asiento ({vocabulario})"


def test_la_glosa_de_la_linea_va_entera_y_el_corte_es_del_driver():
    """La MISMA glosa en todas las lineas, entera y sin prefijos (John, 21-sep-2026).

    Que es cada linea lo dicen su `rol` y su cuenta; hasta la 2.1 las derivadas anteponian `IGV - `,
    `RET 4TA - ` o `DETRACCION - `, que ademas gastaba los 30 caracteres de la columna W de CONCAR."""
    concepto = "SERVICIO DE TRANSPORTE DE MATERIALES DE CONSTRUCCION A LA OBRA"
    lineas = asi.lineas_del_comprobante(factura(concepto=concepto), CONTAB, MES, "080001")
    assert {ln.glosa for ln in lineas} == {concepto}
    filas = driver_concar.filas_de_comprobante(factura(concepto=concepto), CONTAB, MES, "080001")
    assert filas[0]["W"] == concepto[:30] and filas[0]["F"] == concepto[:40]


def test_la_tasa_del_igv_que_viaja_es_la_LEGAL_y_concar_la_redondea():
    """La linea lleva la tasa que la ley reconoce, no el cociente `igv / base` (08-oct-2026).

    El caso que lo separa es el de abajo, y es real: una notaria de S/ 30 con base 25.42 e IGV 4.58 —el 18 % exacto
    seria 4.5756, y el emisor redondeo al centimo—. El cociente da 18.0173..., y asi STARSOFT escribia `18.02` en su
    columna TASA IGV. La tolerancia con la que se decide es la de `validar`, una sola para las dos preguntas.

    La reducida no cambia: 10.5 se escribe `10.5` y CONCAR la redondea a 11, porque su columna AO solo admite entero
    y ese redondeo es suyo."""
    reducida = factura(base_gravada="100", igv="10.5", total="110.5")
    assert asi.lineas_del_comprobante(reducida, CONTAB, MES, "080001")[0].tasa_igv == "10.5"
    assert driver_concar.filas_de_comprobante(reducida, CONTAB, MES, "080001")[0]["AO"] == 11

    notaria = factura(base_gravada="25.42", igv="4.58", total="30.00")
    assert asi.lineas_del_comprobante(notaria, CONTAB, MES, "080001")[0].tasa_igv == "18"


def test_una_nota_de_credito_lleva_los_dos_codigos_de_su_referencia():
    nc = factura(tipo_cp="07", serie="FC01", numero="9", ref_tipo_cp="01", ref_serie="E001",
                 ref_numero="871", ref_fecha="2026-08-01")
    principal = asi.lineas_del_comprobante(nc, CONTAB, MES, "080001")[0]
    assert principal.documento["tipo_cp"] == "07" and principal.debe_haber == "H"
    assert principal.referencia == {"tipo_cp": "01", "serie_numero": "E001-871", "fecha": "2026-08-01"}


def test_lo_que_arma_el_motor_valida_contra_el_estandar():
    validador = Draft202012Validator(json.loads(ESQUEMA.read_text(encoding="utf-8")))
    nc = factura(tipo_cp="07", serie="FC01", numero="9", ref_tipo_cp="01", ref_serie="E001", ref_numero="871",
                 ref_fecha="2026-08-01", detraccion={"codigo": "027", "porcentaje": "4"})
    lineas = (asi.lineas_del_comprobante(factura(detraccion={"codigo": "027", "porcentaje": "4"}), CONTAB, MES, "080084")
              + asi.lineas_del_comprobante(nc, CONTAB, MES, "080085")
              + asi.lineas_del_comprobante(factura(tipo_cp="02", retencion="336", igv="0", base_gravada="0",
                                            inafecto="4956"), CONTAB, MES, "080086"))
    doc = {"open_accounting": "1.0",
           "libro": {"ruc": "20601111111", "razon_social": "EMPRESA DE PRUEBA SAC",
                     "periodo": "202608", "tipo": "compra"},
           "asiento": [ln.a_dict() for ln in lineas]}
    assert list(validador.iter_errors(doc)) == []
    assert {ln.rol for ln in lineas} == set(asi.ROLES_DEL_MOTOR)


# --- el driver CSV -----------------------------------------------------------------

def libro_compras() -> Libro:
    return Libro(ruc="20601111111", razon_social="EMPRESA DE PRUEBA SAC",
                 periodo="202608", tipo="compra")


def _csv(**opciones_csv) -> bytes:
    """El CSV de una factura como lo arma el núcleo: las líneas numeradas y cuadradas, y el driver que las escribe."""
    libro = libro_compras()
    lineas, _ = asi.lineas_del_libro(libro, [factura()], CONTAB, {"11": 1})
    return driver_csv.desde_lineas(libro, lineas, CONTAB, **opciones_csv)[0]


def test_el_csv_escribe_una_fila_por_linea():
    config = con_imputaciones(prep.config_aplicada(None, "csv"))      # la del CSV: sin lo propio de CONCAR
    exp = gen.generar(libro_compras(), [factura()], "csv", config=config, correlativos={"11": 1})
    resumen = exp.resumen
    texto = exp.contenido.decode("utf-8-sig")
    filas = [f for f in texto.split("\r\n") if f]
    assert len(filas) == 4                      # cabecera + 3 lineas
    assert filas[0].startswith("sub_diario;correlativo;fecha;cuenta;debe_haber;importe")
    assert filas[1].split(";")[3:6] == ["659999", "D", "4200.00"]
    assert resumen["filas"] == 3 and resumen["debe"] == resumen["haber"] == "4956.00"


def test_el_csv_lleva_bom_para_que_excel_no_rompa_las_tildes():
    assert _csv().startswith(b"\xef\xbb\xbf")
    assert not _csv(bom=False).startswith(b"\xef\xbb\xbf")


def test_el_separador_se_puede_cambiar():
    assert _csv(separador=",").decode("utf-8-sig").startswith("sub_diario,correlativo")


def test_el_csv_esta_registrado_como_driver():
    from contaperu import drivers

    assert drivers.obtener("csv") is driver_csv
    assert drivers.formato_de("csv", "compra") == "csv_asiento"
    with pytest.raises(ValueError):
        drivers.obtener("un-erp-que-no-existe")


def test_el_csv_lleva_el_rol_y_los_codigos_sunat():
    """B5: lo que un driver necesita para no adivinar sale en columnas al final, llenas. La 1.0 suma dos más, `clase`
    y el id del comprobante, y siguen yendo al final para no mover las columnas de siempre."""
    import csv
    import io

    from util import GOLDEN

    from util import imputando

    documento = imputando(json.loads((GOLDEN / "compras_202601.json").read_text(encoding="utf-8")), "659999")
    texto = api.exportar(documento, driver="csv", configuracion={"usa_centros_costo": False})["texto"]
    filas = list(csv.DictReader(io.StringIO(texto.lstrip("\ufeff")), delimiter=";"))
    assert list(filas[0])[-5:] == ["rol", "doc_tipo_cp", "ref_tipo_cp", "clase", "doc_id_externo"]
    assert [f["rol"] for f in filas[:3]] == ["principal", "impuesto", "tercero"]
    assert [f["clase"] for f in filas[:3]] == ["gasto", "pasivo", "pasivo"]
    assert all(f["doc_tipo_cp"] for f in filas) and {f["ref_tipo_cp"] for f in filas} == {""}
    # El enlace con la imputación: cada línea dice de qué comprobante salió. Desde la 3.0 el documento imputa
    # —la cuenta es suya, no de la configuración—, así que la columna va llena; con un documento sin imputaciones
    # sale vacía, que es lo que la hace opcional.
    assert {f["doc_id_externo"] for f in filas} == {"fila-1", "fila-2", "fila-3"}
