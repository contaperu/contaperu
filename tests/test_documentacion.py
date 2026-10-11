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
- `REFERENCIAS.md`, que es investigación fechada y dice en su cabecera de cuándo es cada uno de sus tres
  escalones y contra qué versión se escribió;
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
            "estandar/LEEME.md", "estandar/MIGRAR-A-1.0.md", "estandar/MIGRAR-A-2.0.md",
            "estandar/enmiendas/LEEME.md")

# Los que citan el código por su ruta y hablan del presente: los vigentes y los de investigación. **El CHANGELOG
# queda fuera, y es la exclusión importante**: es la bitácora, cita el código que había el día de cada versión y por
# eso no se reescribe. Exigirle las rutas de hoy lo pondría rojo en cada reestructuración y nos empujaría a mentir
# sobre el pasado. `CODE_OF_CONDUCT.md` y `SECURITY.md` no citan código.
CITAN_CODIGO = VIGENTES + ("REFERENCIAS.md",)

# Una ruta de FICHERO del paquete citada en un documento, con su línea opcional: `contaperu/validar.py:244`.
#
# Solo ficheros, y no carpetas: se intentó y trae más ruido que valor —las carpetas citadas incluyen las
# **reservadas a propósito** (`contaperu/jurisdicciones/`, que es un hito con su nombre ya escrito; `contaperu/banco/`
# lo era hasta la 8.2, que lo resolvió llamándolo `tesoreria/`), la ruta del estándar dentro de la rueda y los
# `github.com/contaperu/contaperu/…` de los enlaces—.
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
    "HOJA-DE-RUTA.md": {"2.1"},
    "ARQUITECTURA.md": {"2.1"},
    # Una guía de migración existe para hablar de la versión de la que se viene, y de la que se va a.
    "estandar/MIGRAR-A-1.0.md": {"0.3", "1.0"},
    "estandar/MIGRAR-A-2.0.md": {"1.0"},
}


def texto(doc: str) -> str:
    return (RAIZ / doc).read_text(encoding="utf-8")


@pytest.mark.parametrize("doc", VIGENTES)
def test_ningun_documento_nombra_un_driver_que_no_existe(doc):
    """El caso que lo trae: `driver="open_accounting"` sobrevivió al renombrado en los dos documentos que más se leen."""
    nombrados = {next(g for g in m.groups() if g) for m in NOMBRA_DRIVER.finditer(texto(doc))}
    # Hasta la 10.0 los nombres viejos contaban como existentes, porque una tabla `ALIAS` los resolvía. Se retiró
    # —estaba vacía desde la 4.0—, así que lo que se caza es un nombre que no resuelve, y punto.
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
    for doc in ("REFERENCIAS.md",):
        cabecera = "\n".join(texto(doc).splitlines()[:40])
        assert "**Estado:" in cabecera or "Investigación hecha el" in cabecera, (
            f"{doc} no dice en su cabecera de cuándo es ni contra qué versión se escribió")


def test_la_lista_de_vigentes_no_se_queda_atras():
    """Si aparece un documento nuevo en la raíz o en `estandar/`, hay que decidir si habla del presente."""
    en_disco = {p.name for p in RAIZ.glob("*.md")} | {f"estandar/{p.name}" for p in (RAIZ / "estandar").glob("*.md")}
    # Los tres documentos de trabajo que había —`API-DE-REGISTRO.md`, `STARSOFT-INTEGRACION.md` y
    # `LIBROS-Y-CUENTAS.md`— se retiraron el 10-oct-2026: su investigación está en `REFERENCIAS.md`, sus propuestas
    # vivas en el §8 de `HOJA-DE-RUTA.md` y la fuente del formato de STARSOFT en el código de su driver. Si vuelve
    # a aparecer un documento de trabajo en la raíz, entra aquí con su motivo y con la condición que lo haría
    # vigente.
    fechados = {"CHANGELOG.md", "REFERENCIAS.md", "CODE_OF_CONDUCT.md", "SECURITY.md"}
    sin_decidir = sorted(en_disco - set(VIGENTES) - fechados - {f"estandar/{Path(v).name}" for v in VIGENTES})
    assert not sin_decidir, (f"documentos sin decidir si hablan del presente: {sin_decidir}. "
                             "Van a `VIGENTES` o a `fechados`, con su motivo.")


# Los numeros que un documento dice de si mismo, escritos como palabra y como cifra. Llega hasta el 30 porque
# antes llegaba hasta el 15 y la herramienta numero 16 no habria fallado: habria reventado con un `KeyError`,
# que es lo que no se quiere de un guardian. Si alguna vez se pasa de 30, `palabra()` lo dice en una linea.
# Empieza en el 3 desde la 9.0, que trajo un recuento de tres (las funciones del IGV).
PALABRAS = {3: "tres", 4: "cuatro", 5: "cinco",
            6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez", 11: "once", 12: "doce", 13: "trece",
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

    # Y ningun recuento viejo sobrevive en otra frase. Por PALABRA ENTERA: con un `in` pelado, «13 recursos»
    # contiene «3 recursos» y el guardian senalaria como viejo el recuento bueno. No saltaba porque la tabla
    # empezaba en el 6, que es una propiedad de la tabla y no de la comprobacion; la 9.0 bajo la tabla al 3.
    for numero, _ in PALABRAS.items():
        if numero not in (herramientas, recursos):
            for cosa in ("herramientas", "recursos"):
                assert not re.search(rf"\b{numero} {cosa}\b", readme), f"queda un recuento viejo: {numero} {cosa}"


# Los documentos que dicen cuántas funciones reciben el eje del libro, y los contextos en que lo dicen. Un número
# escrito en palabra se busca por lo que va DETRÁS, que es lo que lo convierte en una afirmación —«veinte
# funciones», «catorce de ellas», «tres del IGV»— y, sobre todo, lo que dice CUÁL de los cuatro recuentos es.
#
# Cada contexto admite solo el suyo, y eso no es rigor de más: con los cuatro válidos en cualquier hueco, «catorce
# funciones de `asiento`» pasaba, y es justo el error que hubo. Lo descubrió mutar el documento a mano.
DICEN_EL_RECUENTO_DEL_EJE = ("ARQUITECTURA.md", "CLAUDE.md", "INTEGRAR.md")
CONTEXTOS_DEL_EJE = {
    # lo que va detrás del número        : qué recuentos caben ahí
    r"funciones": ("total", "asiento"),
    r"de ellas": ("publicas",),
    r"del IGV|de `tributos\.igv`": ("igv",),
}


def _cuentas_del_eje() -> dict[str, int]:
    """Cuántas funciones reciben los rasgos del libro, contadas del código y no de la cabeza.

    Se cuenta con `ast` y por la ANOTACIÓN del parámetro, que es la definición de «recibe el eje»: una función que
    lo reciba sin anotarlo no está en la cuenta, y eso es correcto —lo que un documento promete a quien integra es
    una firma—."""
    import ast

    paquete = RAIZ / "contaperu"
    recibe: dict[str, list[str]] = {"asiento": [], "igv": []}
    for fichero in sorted(paquete.rglob("*.py")):
        if not str(fichero).replace("\\", "/").endswith(("tributos/igv.py",)) and "asiento" not in fichero.parts:
            continue
        donde = "igv" if fichero.name == "igv.py" else "asiento"
        for nodo in ast.walk(ast.parse(fichero.read_text("utf-8"))):
            if not isinstance(nodo, ast.FunctionDef) or nodo.name.startswith("_"):
                continue
            if any(a.annotation is not None and "Rasgos" in ast.unparse(a.annotation)
                   for a in nodo.args.args + nodo.args.kwonlyargs):
                recibe[donde].append(nodo.name)

    # Y cuántas de las de `asiento` están en la superficie congelada, que es de donde salía el «catorce».
    import json

    superficie = json.loads((RAIZ / "tests/fixtures/superficie/1.0.json").read_text("utf-8"))
    publicas = [n for n in recibe["asiento"] if n in superficie.get("contaperu.asiento", {})]
    return {"total": len(recibe["asiento"]) + len(recibe["igv"]), "asiento": len(recibe["asiento"]),
            "publicas": len(publicas), "igv": len(recibe["igv"])}


@pytest.mark.parametrize("doc", DICEN_EL_RECUENTO_DEL_EJE)
def test_ningun_documento_dice_a_ojo_cuantas_funciones_reciben_el_eje_del_libro(doc):
    """El hermano del recuento de herramientas, y su caso real es de la propia 9.0.

    Los cinco documentos de esa versión dijeron «catorce funciones» porque catorce son las que están en la
    superficie congelada —y son veinte las que cambian: diecisiete de `asiento` y tres del IGV—. Lo encontró un
    `ast` escrito para otra cosa; la batería no lo vio, porque de los módulos de extensión congela los nombres y
    no las firmas, así que nada se puso rojo.

    No exige que cada documento dé los cuatro números: exige que **el que dé sea el que va en ese hueco**. Así
    caen las dos formas de equivocarse: la que envejece sola —el día que el eje llegue a un libro más, todo lo que
    diga «veinte» se pone rojo— y la de hoy, poner el recuento de las públicas donde va el de todas."""
    cuentas = _cuentas_del_eje()
    palabras = set(PALABRAS.values())
    contenido = texto(doc)
    alguno = False

    for detras, cuales in CONTEXTOS_DEL_EJE.items():
        caben = {en_palabra(cuentas[c]) for c in cuales}
        dichas = {m.group(1).lower() for m in re.finditer(rf"\b([a-záéíóú]+) (?:{detras})\b", contenido)}
        dichas &= palabras
        alguno = alguno or bool(dichas)
        mal = sorted(dichas - caben)
        assert not mal, (
            f"{doc} dice «{mal[0]} {detras.split('|')[0]}» y ahí va {' o '.join(sorted(caben))}. Hoy son "
            f"{cuentas['total']} funciones: {cuentas['asiento']} de `asiento`, {cuentas['publicas']} de ellas en la "
            f"superficie congelada, y {cuentas['igv']} del IGV.")

    assert alguno, f"{doc} está en DICEN_EL_RECUENTO_DEL_EJE y no da ninguno: sácalo de la lista o escríbelo"


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


# Las palabras que el motor retiró y que un documento VIGENTE no puede seguir usando como si existieran. Cada una
# con la que la sustituye, para que el error diga qué poner.
#
# Esto existe porque al renombrar los canales en la 8.0 nos dimos cuenta de que **ningún test vigilaba el
# vocabulario de los documentos**: este fichero comprueba nombres de driver, versión del estándar, rutas citadas y
# los recuentos del README, y nada más. Un `tributario` olvidado en `ARQUITECTURA.md` no habría puesto roja la
# batería — exactamente el mismo despiste que dio origen a este fichero, y por el mismo motivo: la guarda del
# renombrado fue un `grep` a mano.
#
# Solo los VIGENTES, y es la pareja de la exclusión del CHANGELOG: un documento que habla del presente no puede
# nombrar algo que ya no existe; uno fechado cuenta lo que había su día y se deja en paz.
RETIRADAS = {
    "tributario": "`sunat`, el canal (ojo: «régimen tributario» y «registro tributario» son otra cosa y valen)",
    "intercambio": "`erp`, el canal",
}


@pytest.mark.parametrize("doc", VIGENTES)
def test_ningun_documento_vigente_usa_una_palabra_retirada(doc):
    """Un documento del presente no nombra un valor que el motor ya no admite.

    Se busca de **dos** formas, y la segunda la pagó esta misma guarda: entre acentos graves, que es como se escribe
    un valor del contrato, y precedida de «canal», que es como se escribe cuando a alguien se le olvidan los acentos.
    Con solo la primera, la versión que estrenó este test dejó pasar «de canal tributario» y «el CSV de canal
    intercambio» en `HOJA-DE-RUTA.md` — **en el mismo documento que se estaba editando**, y en la tabla que resume el
    repositorio entero.

    Las dos formas y no una barrida a secas, porque «los regímenes tributarios del Perú» y «un registro tributario»
    son correctos y conviven con el canal en el mismo repositorio. Distinguirlos es el trabajo del test."""
    contenido = texto(doc)
    usadas = {palabra: con_que for palabra, con_que in RETIRADAS.items()
              if f"`{palabra}`" in contenido or f"canal {palabra}" in contenido}
    assert not usadas, (f"{doc} usa como valor una palabra que el motor retiró: "
                        + "; ".join(f"`{p}` → usa {c}" for p, c in sorted(usadas.items())))


# ── Las promesas de versión, que envejecen solas si nadie las mira ──────────────────────────────────────────────

# Dónde promete cada documento su estabilidad, con la frase EXACTA y qué número le toca. `{mayor}` es la mayor en
# curso y `{siguiente}` la que viene, que es hasta donde llega la promesa.
#
# Va como frase exacta y no como patrón a propósito: «hasta la 3.10» aparece treinta y seis veces en el repositorio
# y casi todas son historia —«hasta la 3.10 la sigla la traía el núcleo»—, así que un patrón genérico cazaría el
# pasado. Lo que esta tabla sabe es dónde se promete, y eso hay que escribirlo.
PROMESAS_DE_VERSION = (
    ("INTEGRAR.md", "qué promete la {mayor}.x"),
    ("INTEGRAR.md", "## Lo que promete la {mayor}.x"),
    ("INTEGRAR.md", "no cambia de nombre ni de firma** hasta la {siguiente}.0"),
    ("INTEGRAR.md", "sigue resolviendo durante toda la {mayor}.x"),
    ("INTEGRAR.md", "hasta la {siguiente}.0 (`_obsoleto.RETIRO`)"),
    ("README.md", "lo que pide cada una no cambian\nhasta la {siguiente}.0."),
    ("README.md", "misma firma hasta la {siguiente}.0."),
    ("CLAUDE.md", "lo que promete la {mayor}.x"),
    ("contaperu/api/__init__.py", "estable durante toda la {mayor}.x"),
    ("contaperu/api/__init__.py", "sigue su firma hasta la {siguiente}.0"),
    ("ARQUITECTURA.md", '`RETIRO` dice ahora `"{siguiente}.0"`'),
)


@pytest.mark.parametrize("doc, frase", PROMESAS_DE_VERSION,
                         ids=[f"{d}:{f[:34]}" for d, f in PROMESAS_DE_VERSION])
def test_ninguna_promesa_de_version_queda_atras(doc, frase):
    """Una promesa de estabilidad que cita una versión ya pasada no promete nada, y envejece sin que nada avise.

    **Es la lección de `_obsoleto.RETIRO`, que la cometió tres veces**: decía «3.0» con el paquete en la 3.8, y
    luego «6.0» durante toda la 6.x. Nada lo vigilaba hasta que la 6.2.0 le puso un test, y desde entonces ese test
    ha movido el número en la 7.0, la 8.0 y la 9.0 —las tres veces en rojo primero, que es su trabajo—.

    Lo que lo trae aquí: la 10.0 encontró cinco sitios con el mismo defecto y nadie los vigilaba. `INTEGRAR.md`
    titulaba «Lo que promete la 7.x» y prometía firmas estables «hasta la 8.0» con el paquete en 9.2.0; el
    `README.md` y `contaperu/api/__init__.py` decían «hasta la 2.0», que quedó atrás hace ocho mayores; y
    `CLAUDE.md` hablaba de «la 2.x».

    El día que el paquete suba de mayor, estas once afirmaciones se ponen rojas de golpe y hay que moverlas. Que
    sea molesto es el punto: una promesa que se mueve sola no es una promesa."""
    from contaperu import __version__

    mayor = int(__version__.split(".")[0])
    esperada = frase.format(mayor=mayor, siguiente=mayor + 1)
    contenido = texto(doc)
    assert esperada in contenido, (
        f"{doc} no dice {esperada!r}. El paquete está en la {mayor}.x, así que lo que promete llega hasta la "
        f"{mayor + 1}.0: mueve la frase, o esta tabla si la frase cambió de forma.")
