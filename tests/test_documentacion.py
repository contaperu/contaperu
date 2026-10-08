"""Los documentos que se publican no pueden nombrar algo que no existe.

Nace de dos despistes reales, los dos encontrados **a mano** el día antes de publicar el tag del estándar y ninguno
visto por la batería: `INTEGRAR.md` y `README.md` seguían diciendo `driver="open_accounting"` después de que el driver
pasara a llamarse `asiento_neutral`, e `INTEGRAR.md` seguía diciendo «entra un documento `open-accounting` 0.3» y «el
estándar sigue en 0.3» cuando el motor ya rechaza la 0.3 a propósito.

No son erratas: son las dos primeras cosas que lee quien integra, y copiar cualquiera de las dos falla. La guarda que
se usó al renombrar el driver fue un `grep` sobre `contaperu/` y `tests/`, así que la documentación quedó fuera —y la
documentación es justo donde vive el nombre que la gente copia.

Se comprueban los documentos que describen **lo que hay hoy**. Quedan fuera, a propósito:

- `CHANGELOG.md`, que es la bitácora: habla de versiones viejas porque para eso existe;
- `REFERENCIAS.md` y `API-DE-REGISTRO.md`, que son investigación fechada y dicen en su
  cabecera de cuándo son y contra qué versión se escribieron;
- `estandar/LEEME.md` en su historia de versiones, que narra la 0.1, la 0.2 y la 0.3 sin la palabra
  `open-accounting` delante, así que el patrón no la toca.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from contaperu import drivers
from contaperu._version import OPEN_ACCOUNTING

RAIZ = Path(__file__).resolve().parents[1]

# Lo que describe el estado de hoy. Escrito a mano y no con un glob: añadir un documento a esta lista es decidir que
# ese documento habla del presente.
VIGENTES = ("README.md", "INTEGRAR.md", "ARQUITECTURA.md", "CLAUDE.md", "HOJA-DE-RUTA.md", "CONTRIBUTING.md",
            "estandar/LEEME.md", "estandar/MIGRAR-A-1.0.md", "estandar/enmiendas/LEEME.md")

# Los que citan el código por su ruta y hablan del presente: los vigentes y los de investigación. **El CHANGELOG
# queda fuera, y es la exclusión importante**: es la bitácora, cita el código que había el día de cada versión y por
# eso no se reescribe. Exigirle las rutas de hoy lo pondría rojo en cada reestructuración y nos empujaría a mentir
# sobre el pasado. `CODE_OF_CONDUCT.md` y `SECURITY.md` no citan código.
CITAN_CODIGO = VIGENTES + ("REFERENCIAS.md", "API-DE-REGISTRO.md", "LIBROS-Y-CUENTAS.md", "STARSOFT-INTEGRACION.md")

# Una ruta de FICHERO del paquete citada en un documento, con su línea opcional: `contaperu/validar.py:244`.
#
# Solo ficheros, y no carpetas: se intentó y trae más ruido que valor —las carpetas citadas incluyen las
# **reservadas a propósito** (`contaperu/banco/`, `contaperu/jurisdicciones/`, que son hitos con su nombre ya
# escrito), la ruta del estándar dentro de la rueda y los `github.com/contaperu/contaperu/…` de los enlaces—.
# Un fichero que desaparece sí es siempre un error; una carpeta que todavía no existe puede ser una promesa.
RUTA_CITADA = re.compile(r"`?(contaperu/[A-Za-z0-9_/]+\.(?:py|json))(?::\d+(?:-\d+)?)?`?")

# Un documento nombra un driver así: `driver="x"`, `driver: "x"`, `--driver x` o «el driver `x`».
NOMBRA_DRIVER = re.compile(r"""driver[s]?[=:]\s*["'`]([a-z_][a-z_0-9]*)["'`]"""
                           r"""|--driver[= ]+`?([a-z_][a-z_0-9]*)`?"""
                           r"""|driver\s+`([a-z_][a-z_0-9]*)`""")

# Y afirma una versión del estándar así: «`open-accounting` 1.0», el tag `open-accounting-1.0`, o la clave del
# documento en un ejemplo.
AFIRMA_VERSION = (re.compile(r"open-accounting`?\**\s*\**`?(\d+\.\d+)\b"),
                  re.compile(r"open-accounting-(\d+\.\d+)"),
                  re.compile(r'"open_accounting"\s*:\s*"(\d+\.\d+)"'))

# Las únicas versiones distintas de la vigente que un documento del presente puede citar, cada una con su motivo.
OTRAS_VERSIONES: dict[str, set[str]] = {
    # El hito J5 de la hoja de ruta, que es lo próximo del estándar y se nombra por su número.
    "HOJA-DE-RUTA.md": {"1.1"},
    "ARQUITECTURA.md": {"1.1"},
    # La guía de migración existe para hablar de la versión de la que se viene.
    "estandar/MIGRAR-A-1.0.md": {"0.3"},
}


def texto(doc: str) -> str:
    return (RAIZ / doc).read_text(encoding="utf-8")


@pytest.mark.parametrize("doc", VIGENTES)
def test_ningun_documento_nombra_un_driver_que_no_existe(doc):
    """El caso que lo trae: `driver="open_accounting"` sobrevivió al renombrado en los dos documentos que más se leen."""
    nombrados = {next(g for g in m.groups() if g) for m in NOMBRA_DRIVER.finditer(texto(doc))}
    # Los nombres viejos cuentan como existentes: siguen resolviendo y un documento puede explicar el renombrado
    # usando la forma natural (`driver="asiento_neutral"`). Lo que se caza es un nombre que no resuelve de ninguna manera.
    fantasmas = sorted(nombrados - set(drivers.DRIVERS) - set(drivers.ALIAS))
    assert not fantasmas, (f"{doc} nombra un driver que no existe: {fantasmas}. "
                           f"Los de serie son {sorted(drivers.DRIVERS)}")


@pytest.mark.parametrize("doc", VIGENTES)
def test_ningun_documento_afirma_una_version_vieja_del_estandar(doc):
    """Un documento del presente que diga «`open-accounting` 0.3» manda a escribir un documento que el motor rechaza."""
    contenido = texto(doc)
    citadas = {v for patron in AFIRMA_VERSION for v in patron.findall(contenido)}
    permitidas = {OPEN_ACCOUNTING} | OTRAS_VERSIONES.get(doc, set())
    sobran = sorted(citadas - permitidas)
    assert not sobran, (f"{doc} cita del estándar la versión {sobran} y la vigente es {OPEN_ACCOUNTING}. "
                        "Si es a propósito, va en `OTRAS_VERSIONES` con su motivo.")


def test_los_documentos_de_investigacion_dicen_de_cuando_son():
    """La otra mitad de la regla: lo que NO se comprueba tiene que declararse fechado, o un lector lo toma por vigente.

    Es lo que separa un documento de investigación de uno desactualizado, y la diferencia la tiene que ver el lector
    en el primer párrafo, no deducirla del `git log`."""
    for doc in ("REFERENCIAS.md", "API-DE-REGISTRO.md"):
        cabecera = "\n".join(texto(doc).splitlines()[:40])
        assert "**Estado:" in cabecera or "Investigación hecha el" in cabecera, (
            f"{doc} no dice en su cabecera de cuándo es ni contra qué versión se escribió")


def test_la_lista_de_vigentes_no_se_queda_atras():
    """Si aparece un documento nuevo en la raíz o en `estandar/`, hay que decidir si habla del presente."""
    en_disco = {p.name for p in RAIZ.glob("*.md")} | {f"estandar/{p.name}" for p in (RAIZ / "estandar").glob("*.md")}
    fechados = {"CHANGELOG.md", "REFERENCIAS.md", "API-DE-REGISTRO.md",
                "CODE_OF_CONDUCT.md", "SECURITY.md",
                # Lo levantado del formato de STARSOFT el 20-sep-2026, de dos vídeos y sus capturas. Se declara
                # a sí mismo documento de trabajo y marca lo que está `[por confirmar]`: pasa a vigente el día
                # que una plantilla oficial lo respalde.
                "STARSOFT-INTEGRACION.md",
                # La investigación del 1-oct-2026 sobre el PLE como suelo del estándar y el modelo de cuentas de
                # los ERP abiertos. Mismo caso que el de STARSOFT: se declara documento de trabajo y marca lo que
                # está `[por confirmar]` —los códigos de libro del Anexo 3 de la RS 286-2009, entre otros—. Sus
                # candidatas a propuesta entran en la tabla del §8 de `HOJA-DE-RUTA.md` cuando cierre el refinado,
                # y entonces este documento pasa a vigente o se reparte entre los dos de investigación.
                "LIBROS-Y-CUENTAS.md"}
    sin_decidir = sorted(en_disco - set(VIGENTES) - fechados - {f"estandar/{Path(v).name}" for v in VIGENTES})
    assert not sin_decidir, (f"documentos sin decidir si hablan del presente: {sin_decidir}. "
                             "Van a `VIGENTES` o a `fechados`, con su motivo.")


# Los numeros que el README dice de si mismo, escritos como palabra y como cifra. Llega hasta el 30 porque
# antes llegaba hasta el 15 y la herramienta numero 16 no habria fallado: habria reventado con un `KeyError`,
# que es lo que no se quiere de un guardian. Si alguna vez se pasa de 30, `palabra()` lo dice en una linea.
PALABRAS = {6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez", 11: "once", 12: "doce", 13: "trece",
            14: "catorce", 15: "quince", 16: "dieciseis", 17: "diecisiete", 18: "dieciocho",
            19: "diecinueve", 20: "veinte", 21: "veintiuna", 22: "veintidos", 23: "veintitres",
            24: "veinticuatro", 25: "veinticinco", 26: "veintiseis", 27: "veintisiete",
            28: "veintiocho", 29: "veintinueve", 30: "treinta"}


def en_palabra(cuantas: int) -> str:
    """El numero en palabra, o un fallo que dice que hay que ampliar la tabla."""
    assert cuantas in PALABRAS, f"{cuantas} no esta en PALABRAS: anade su palabra para que este test siga sirviendo"
    return PALABRAS[cuantas]


def test_el_readme_no_dice_cuantas_herramientas_hay_a_ojo():
    """El mismo despiste que este archivo existe para cazar, en su version aritmetica.

    El README decia «11 herramientas y 6 recursos» cuando ya eran 12 y 7, e `INTEGRAR.md` decia «las once»;
    `servidor-infra` decia 9. Nadie miente: es que un numero escrito a mano envejece solo, y estos tres se
    habian quedado en tres momentos distintos. Aqui el numero se cuenta, no se recuerda.
    """
    import asyncio

    import pytest as _pytest
    _pytest.importorskip("mcp")
    from contaperu.puertas.servidor_mcp import mcp

    herramientas = len(asyncio.run(mcp.list_tools()))
    recursos = len(asyncio.run(mcp.list_resources()))
    readme = texto("README.md")
    integrar = texto("INTEGRAR.md")

    assert f"{herramientas} herramientas" in readme, f"el README no dice las {herramientas} que hay"
    assert f"{en_palabra(herramientas).capitalize()} herramientas" in readme
    assert f"{en_palabra(herramientas)} herramientas" in integrar
    assert f"{recursos} recursos" in readme, f"el README no dice los {recursos} que hay"
    assert f"{en_palabra(recursos)} recursos" in readme

    # Y ningun recuento viejo sobrevive en otra frase.
    for numero, _ in PALABRAS.items():
        if numero not in (herramientas, recursos):
            assert f"{numero} herramientas" not in readme, f"queda un recuento viejo: {numero} herramientas"
            assert f"{numero} recursos" not in readme, f"queda un recuento viejo: {numero} recursos"


@pytest.mark.parametrize("doc", CITAN_CODIGO)
def test_ninguna_ruta_citada_en_un_documento_ha_dejado_de_existir(doc):
    """El hermano del de los drivers, y el que hace segura una reestructuración.

    Los documentos de aquí citan el código por su ruta —`contaperu/validar.py:244`— porque es lo que convierte
    una afirmación en algo que se puede ir a mirar. Pero una ruta envejece sin avisar: cuando esto entró,
    `HOJA-DE-RUTA.md` citaba **`contaperu/operaciones.py`, `contaperu/formato.py` y `contaperu/generar.py` en
    cinco sitios**, y esos tres módulos los había retirado la 2.0 **cuatro mayores antes**. Nadie lo había
    visto porque este fichero solo vigilaba los nombres de driver y la versión del estándar.

    Se comprueba que el fichero exista y **no** el número de línea: una línea que se corre no engaña a nadie
    —el código está al lado—, y exigirla pondría la batería roja en cada commit que añada una función.
    """
    citadas = {m.group(1) for m in RUTA_CITADA.finditer(texto(doc))}
    fantasmas = sorted(r for r in citadas if not (RAIZ / r).exists())
    assert not fantasmas, (f"{doc} cita rutas que ya no existen: {fantasmas}. Si el código cambió de sitio, la "
                           "cita va a la ruta nueva; si desapareció, la frase sobra.")
