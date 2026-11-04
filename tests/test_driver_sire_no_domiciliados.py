"""El driver `sire_no_domiciliados`: el TXT del registro de compras de no domiciliados del SIRE, el 080500 (15.6.0).

La forma sale del registro real que SUNAT aceptó en setiembre de 2026: 35 campos, el 36 vacío y palote, CRLF, el CAR
vacío, DD/MM/AAAA, importes y tasa con dos decimales y el tipo de cambio con tres. Aquí se prueba esa forma con un caso
sintético y, si el registro real está en `tests/fixtures/privado/sire/` (fuera de Git), **la ida y vuelta entera**: se
lee, se vuelve a escribir y cada fila tiene que salir igual campo a campo. Lo que no salga igual se dice por su número
de fila y de campo, nunca por su valor: es data de un contribuyente.
"""
from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest

from contaperu import drivers
from contaperu.asiento.faltas import NoExportable
from contaperu.comprobantes import sire_txt
from contaperu.drivers import contrato
from contaperu.drivers import sire_no_domiciliados as nd
from contaperu.modelo import Comprobante, Libro
from contaperu.pipeline import salida as g

LIBRO = Libro(ruc="20601234567", razon_social="EMPRESA DE PRUEBA SAC", periodo="202609", tipo="compra")

# Una suscripción de 100 dólares al 3.750: 375 soles de renta al 30 %, sin convenio (Estados Unidos), un servicio
# digital, y el IGV de utilización del 18 % de los 375 soles.
BLOQUE = {"pais": "9249", "domicilio": "100 MAIN ST SAN FRANCISCO", "vinculo": "00", "renta_bruta": "375.00",
          "deduccion": "0.00", "renta_neta": "375.00", "porcentaje": "30", "impuesto_retenido": "112.50",
          "igv_utilizacion": "67.50", "convenio": "00", "tipo_renta": "18", "modalidad": "3", "art_76": "1"}


def _del_exterior(tipo_cp="91", **cambios) -> Comprobante:
    bloque = {**BLOQUE, **cambios.pop("bloque", {})}
    datos = dict(tipo_cp=tipo_cp, serie="INV", numero="1042", fecha_emision="2026-09-10", contraparte_tipo_doc="0",
                 contraparte_doc="X0000001", contraparte_nombre="PROVEEDOR DEL EXTERIOR", moneda="USD",
                 tipo_cambio="3.750", valor_no_gravado="100.00", total="100.00", origen="manual",
                 no_domiciliado=bloque)
    datos.update(cambios)
    return Comprobante(**datos)


def _campos(texto: bytes) -> list[list[str]]:
    return [fila.split("|") for fila in texto.decode("ascii").split("\r\n") if fila]


def test_el_nombre_es_el_del_libro_electronico_080500():
    # LE + RUC + periodo + 00 + el código del libro + oportunidad 00 + banderas 1112, como el registro aceptado.
    assert g.generar(LIBRO, [_del_exterior()], "sire_no_domiciliados").nombre == "LE2060123456720260900080500001112.TXT"


def test_la_fila_tiene_35_campos_el_36_vacio_y_palote():
    exp = g.generar(LIBRO, [_del_exterior()], "sire_no_domiciliados")
    assert exp.texto.endswith(b"\r\n") and b"\n" not in exp.texto.replace(b"\r\n", b"")
    [f] = _campos(exp.texto)
    assert len(f) == 37 and f[35] == "" and f[36] == ""   # el 36 vacío y lo que queda tras el palote
    assert f[0] == "202609" and f[1] == ""                 # periodo y el CAR, que lo pone SUNAT
    assert f[2] == "10/09/2026" and f[3] == "91" and f[4] == "INV" and f[5] == "1042"


def test_los_importes_del_comprobante_van_en_soles_y_los_del_bloque_tal_cual():
    [f] = _campos(g.generar(LIBRO, [_del_exterior()], "sire_no_domiciliados").texto)
    assert f[6] == "375.00" and f[8] == "375.00"          # 7 valor y 9 total: 100 dólares × 3.750
    assert f[14] == "USD" and f[15] == "3.750"            # 15 moneda y 16 tipo de cambio
    assert f[13] == "67.50"                               # 14 el IGV de utilización, ya en soles
    assert f[24:29] == ["375.00", "0.00", "375.00", "30.00", "112.50"]   # 25-29 renta, tasa e impuesto
    assert f[16] == "9249" and f[29:34] == ["00", "", "18", "3", "1"]    # 17 país; 30-34 los códigos


def test_lee_lo_que_escribe():
    """La ida y vuelta sintética: lo escrito, leído por el lector del motor, es el mismo comprobante."""
    original = _del_exterior()
    exp = g.generar(LIBRO, [original], "sire_no_domiciliados")
    [leido] = sire_txt.parsear(exp.texto, LIBRO, archivo_nombre=exp.nombre)
    for campo in ("tipo_cp", "serie", "numero", "fecha_emision", "moneda", "tipo_cambio", "contraparte_doc",
                  "contraparte_nombre"):
        assert getattr(leido, campo) == getattr(original, campo), campo
    assert leido.total == original.total and leido.valor_no_gravado == original.valor_no_gravado
    # La tasa vuelve con sus dos decimales («30.00» por «30»): el mismo número, que es lo que el modelo guarda.
    sin_tasa = lambda b: {k: v for k, v in b.items() if k != "porcentaje"}  # noqa: E731
    assert sin_tasa(leido.no_domiciliado) == sin_tasa(original.no_domiciliado)
    assert Decimal(leido.no_domiciliado["porcentaje"]) == Decimal(original.no_domiciliado["porcentaje"])


def test_solo_lleva_lo_del_exterior_y_el_resto_sale_fuera_del_destino():
    factura = Comprobante(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-09-10", contraparte_tipo_doc="6",
                          contraparte_doc="20602222226", contraparte_nombre="PROVEEDOR SAC", base_gravada="100",
                          igv="18", total="118")
    exp = g.generar(LIBRO, [factura, _del_exterior(), _del_exterior("97", numero="7")], "sire_no_domiciliados")
    assert exp.comprobantes == 2 and exp.resumen["fuera_del_destino"] == 1
    assert b"F001" not in exp.texto


def test_un_no_domiciliado_sin_pais_no_cabe_y_el_nucleo_lo_dice_antes_de_escribir():
    sin_pais = _del_exterior(bloque={"pais": ""})
    assert list(contrato.no_caben(nd, LIBRO, [sin_pais], None)) == [nd.MOTIVOS["pais"]]
    with pytest.raises(contrato.NoCabe):
        g.generar(LIBRO, [sin_pais], "sire_no_domiciliados")
    # Y si alguien llama a la línea a mano, se niega igual, con su clave.
    with pytest.raises(nd.SinPaisDelNoDomiciliado) as e:
        nd.linea(sin_pais, LIBRO, 1)
    assert e.value.clave == "sin_pais_del_no_domiciliado"


def test_en_dolares_sin_tipo_de_cambio_no_se_escribe():
    """Sin él, los campos 7 a 9 saldrían en dólares bajo el rótulo de soles."""
    sin_cambio = _del_exterior(tipo_cambio=None)
    assert list(contrato.no_caben(nd, LIBRO, [sin_cambio], None)) == [nd.MOTIVOS["cambio"]]
    with pytest.raises(contrato.NoCabe):
        g.generar(LIBRO, [sin_cambio], "sire_no_domiciliados")
    with pytest.raises(NoExportable):
        nd.linea(sin_cambio, LIBRO, 1)


def test_un_tipo_de_otro_registro_no_se_cuenta_como_que_no_cabe():
    """El 01 no es de este destino —lo saca `EXCLUYE_TIPOS`—, que es otra cosa que no caber en su formato."""
    factura = Comprobante(tipo_cp="01", serie="F001", numero="1", fecha_emision="2026-09-10", contraparte_doc="20602222226",
                          contraparte_nombre="PROVEEDOR SAC", base_gravada="100", igv="18", total="118")
    assert contrato.no_caben(nd, LIBRO, [factura], None) == {}


def test_es_un_registro_de_sunat_que_no_lleva_ventas():
    assert contrato.canal(nd) == "sunat"
    assert drivers.formato_de("sire_no_domiciliados", "compra") == "sire_rce_no_domiciliados"
    with pytest.raises(drivers.LibroQueElDestinoNoLleva):
        drivers.formato_de("sire_no_domiciliados", "venta")


def test_la_nota_de_credito_va_en_negativo_como_en_el_sire():
    nota = _del_exterior("97", numero="8", bloque={"renta_bruta": "375.00", "impuesto_retenido": "112.50"})
    [f] = _campos(g.generar(LIBRO, [nota], "sire_no_domiciliados").texto)
    assert f[8].startswith("-") and Decimal(f[8]) == Decimal("-375.00")
    assert not f[27].startswith("-")                     # la tasa es un porcentaje: nunca lleva signo


# ── El registro real ──────────────────────────────────────────────────────────────────────────────────────────────
PRIVADO = pathlib.Path(__file__).parent / "fixtures" / "privado" / "sire"


def _registro_real() -> pathlib.Path:
    archivos = sorted(PRIVADO.glob("LE*080500*.txt")) if PRIVADO.is_dir() else []
    if not archivos:
        pytest.skip("sin el registro de no domiciliados real en tests/fixtures/privado/sire (fuera de Git)")
    return archivos[0]


def test_el_registro_real_vuelve_igual_campo_a_campo():
    """Se lee el 080500 que SUNAT aceptó y se vuelve a escribir: cada fila, igual. Si una no sale, el fallo dice la
    fila y el campo, nunca el valor."""
    archivo = _registro_real()
    libro = Libro(ruc=archivo.name[2:13], razon_social="", periodo=archivo.name[13:19], tipo="compra")
    crudo = archivo.read_bytes()
    comprobantes = sire_txt.parsear(crudo, libro, archivo_nombre=archivo.name)
    exp = g.generar(libro, comprobantes, "sire_no_domiciliados", incluir_errores=True)
    assert exp.nombre.upper() == archivo.name.upper()
    presentado = [fila.split("|") for fila in crudo.decode("utf-8").splitlines() if fila.strip()]
    escrito = _campos(exp.texto)
    assert len(escrito) == len(presentado)

    def valor(fila: list[str], j: int) -> str | None:
        v = fila[j] if j < len(fila) else None
        # El 18 (razón social) y el 19 (domicilio) vuelven con los espacios dobles colapsados —medido el 04-nov-2026:
        # son los únicos caracteres que cambian, y los pierde ya el modelo al leer—. Es el mismo ruido conocido de la
        # razón social del 080400: SUNAT no casa por ese texto. Cualquier otra diferencia en ellos sí cae.
        return " ".join(v.split()) if v is not None and j in (17, 18) else v

    distintos = {(i, j + 1) for i, (a, b) in enumerate(zip(presentado, escrito), start=1)
                 for j in range(max(len(a), len(b))) if valor(a, j) != valor(b, j)}
    assert not distintos, f"filas y campos que no vuelven igual: {sorted(distintos)}"
