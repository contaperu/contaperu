"""Los catálogos del registro de compras de NO DOMICILIADOS (el 080500 del SIRE) y el convenio que le toca a un país.

Entraron en la 15.6.0, cuando el motor empezó a darle forma al no domiciliado (la enmienda 0007 del estándar). Hasta
entonces el lector del 080500 dejaba el país, la renta, el convenio y la modalidad crudos en la fila de SUNAT, porque
no había contra qué leerlos: estos son esos «contra qué».

**Seis tablas del Anexo 01 de la RS 040-2022**, la norma del SIRE, cada una con su fuente en `datos/sunat/catalogos.json`:
países (Tabla 16), vinculación económica (17), convenios para evitar la doble tributación (18), tipo de renta (19),
modalidad del servicio (20) y exoneraciones del art. 19 de la LIR (21). ⚠️ **Los números son los del SIRE, no los del
PLE**: el Anexo 3 de la RS 169-2015 numeraba las mismas tablas 35, 27, 25, 31, 32 y 33, y por eso aquí se nombran por
lo que son (la regla de `catalogos/__init__`), y el número solo vive dentro de la fuente.

**Y una tabla del motor, `datos/sunat/convenios.json`**: qué país tiene convenio, con qué código de la Tabla 18 y desde
cuándo se aplica. No es de SUNAT —la Tabla 18 nombra convenios, no países—, así que tiene su fuente propia.
"""
from __future__ import annotations

from datetime import date

from .. import _datos
from ._fuente import CATALOGOS

PAISES: dict[str, str] = dict(CATALOGOS["paises"]["codigos"])
VINCULOS_ECONOMICOS: dict[str, str] = dict(CATALOGOS["vinculos_economicos"]["codigos"])
CONVENIOS_DOBLE_IMPOSICION: dict[str, str] = dict(CATALOGOS["convenios_doble_imposicion"]["codigos"])
TIPOS_RENTA: dict[str, str] = dict(CATALOGOS["tipos_renta"]["codigos"])
MODALIDADES_SERVICIO: dict[str, str] = dict(CATALOGOS["modalidades_servicio"]["codigos"])
EXONERACIONES_NO_DOMICILIADO: dict[str, str] = dict(CATALOGOS["exoneraciones_no_domiciliado"]["codigos"])

# El Perú en la Tabla 16. Un no domiciliado reside FUERA (LIR, art. 7), así que este código en su país es casi siempre
# un error de captura: en el registro real de setiembre de 2026 que SUNAT aceptó hay filas con él.
PAIS_PERU = "9589"
# «Ninguno» en la Tabla 18: el código que va cuando el país no tiene convenio vigente.
SIN_CONVENIO = "00"

RUTA_CONVENIOS = "datos/sunat/convenios.json"


def _tabla_de_convenios() -> dict:
    """Los convenios por país, validados contra los dos catálogos de SUNAT. Si falta el fichero o su fuente, o un
    país o un código que no existe, el motor no arranca: un convenio sugerido con un código inventado es peor que
    ninguno."""
    tabla = _datos.leer_json(RUTA_CONVENIOS)
    if not tabla or not str(tabla.get("fuente") or "").strip():
        raise FileNotFoundError(f"No encuentro la tabla de convenios por país con su fuente ({RUTA_CONVENIOS})")
    for pais, convenio in tabla["por_pais"].items():
        if pais not in PAISES:
            raise ValueError(f"{RUTA_CONVENIOS}: el país {pais!r} no está en la Tabla 16")
        codigo = convenio["convenio"]
        if codigo and codigo not in CONVENIOS_DOBLE_IMPOSICION:
            raise ValueError(f"{RUTA_CONVENIOS}: el convenio {codigo!r} de {pais} no está en la Tabla 18")
        date.fromisoformat(convenio["desde"])
    return tabla


_CONVENIOS = _tabla_de_convenios()
CONVENIOS_POR_PAIS: dict[str, dict[str, str]] = {p: dict(c) for p, c in _CONVENIOS["por_pais"].items()}
FUENTE_CONVENIOS: str = _CONVENIOS["fuente"]


def _fecha(valor: date | str | None) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def convenio_sugerido(pais: str, fecha: date | str | None = None) -> dict[str, str]:
    """El convenio para evitar la doble imposición que le toca a un no domiciliado por su país de residencia, en la
    fecha del comprobante: `{"convenio", "instrumento", "motivo"}`.

    `convenio` es un código de la Tabla 18, o **vacío** cuando el motor no puede decirlo —el país no existe, es el
    Perú, o tiene convenio y la tabla no le da código, como Japón—; el porqué va siempre en `motivo`. **Es una
    SUGERENCIA**: aplicar un convenio exige además el certificado de residencia del beneficiario (D.S. 090-2008-EF), y
    eso no lo sabe el motor. Sin fecha se responde como si el convenio ya rigiera —el núcleo no mira el reloj— y el
    motivo dice desde cuándo.

    La fecha es la de EMISIÓN del comprobante: un convenio se aplica a las rentas desde el 1 de enero en que entra en
    aplicación, y antes de esa fecha el código que va es el 00 «Ninguno»."""
    codigo_pais = str(pais or "").strip()
    if codigo_pais not in PAISES:
        return {"convenio": "", "instrumento": "",
                "motivo": f"El país {codigo_pais!r} no está en la Tabla 16 del Anexo 01 de la RS 040-2022."}
    if codigo_pais == PAIS_PERU:
        return {"convenio": "", "instrumento": "",
                "motivo": "El 9589 es el Perú, y un no domiciliado reside fuera del país (LIR, art. 7): revisa el país."}
    convenio = CONVENIOS_POR_PAIS.get(codigo_pais)
    nombre = PAISES[codigo_pais].title()
    if convenio is None:
        return {"convenio": SIN_CONVENIO, "instrumento": "",
                "motivo": f"{nombre} no tiene convenio para evitar la doble imposición con el Perú: 00 «Ninguno»."}
    desde = date.fromisoformat(convenio["desde"])
    cuando = _fecha(fecha)
    if cuando is not None and cuando < desde:
        return {"convenio": SIN_CONVENIO, "instrumento": convenio["instrumento"],
                "motivo": f"El {convenio['instrumento'].lower()} se aplica desde el {desde.isoformat()}: en "
                          f"{cuando.isoformat()} todavía no, así que 00 «Ninguno»."}
    if not convenio["convenio"]:
        return {"convenio": "", "instrumento": convenio["instrumento"],
                "motivo": f"El {convenio['instrumento'].lower()} se aplica desde el {desde.isoformat()}, pero la Tabla "
                          "18 no le da código. Qué se declara lo decide el contador; el motor no elige «09 Otros» por "
                          "su cuenta."}
    return {"convenio": convenio["convenio"], "instrumento": convenio["instrumento"],
            "motivo": f"{convenio['instrumento']}, aplicable desde el {desde.isoformat()}. Pide el certificado de "
                      "residencia del beneficiario (D.S. 090-2008-EF) para aplicarlo."}
