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
- `REFERENCIAS.md`, `INTEROPERABILIDAD.md` y `API-DE-REGISTRO.md`, que son investigación fechada y dicen en su
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
    fantasmas = sorted(nombrados - set(drivers.DRIVERS))
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
    for doc in ("REFERENCIAS.md", "INTEROPERABILIDAD.md", "API-DE-REGISTRO.md"):
        cabecera = "\n".join(texto(doc).splitlines()[:40])
        assert "**Estado:" in cabecera or "Investigación hecha el" in cabecera, (
            f"{doc} no dice en su cabecera de cuándo es ni contra qué versión se escribió")


def test_la_lista_de_vigentes_no_se_queda_atras():
    """Si aparece un documento nuevo en la raíz o en `estandar/`, hay que decidir si habla del presente."""
    en_disco = {p.name for p in RAIZ.glob("*.md")} | {f"estandar/{p.name}" for p in (RAIZ / "estandar").glob("*.md")}
    fechados = {"CHANGELOG.md", "REFERENCIAS.md", "INTEROPERABILIDAD.md", "API-DE-REGISTRO.md",
                "CODE_OF_CONDUCT.md", "SECURITY.md"}
    sin_decidir = sorted(en_disco - set(VIGENTES) - fechados - {f"estandar/{Path(v).name}" for v in VIGENTES})
    assert not sin_decidir, (f"documentos sin decidir si hablan del presente: {sin_decidir}. "
                             "Van a `VIGENTES` o a `fechados`, con su motivo.")
