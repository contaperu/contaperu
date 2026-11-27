"""El kit de vigilantes de un servidor MCP: lo que hay que comprobar de lo que publica, como funciones puras.

Lo que un servidor le enseña al agente —el nombre de cada herramienta, su descripción, su esquema, sus anotaciones y
las instrucciones— es una API pública, aunque no lo parezca: un modelo elige por esos textos, un cliente guarda esos
nombres y lo que pesan sale de la ventana de contexto de cada conversación. Así que se vigila como una API: con una
foto congelada, un presupuesto que solo se mueve a propósito y reglas que no dependen de la buena voluntad.

Cada vigilante recibe lo que el servidor publica **tal como viaja** —la lista de `tools/list` en JSON, con sus claves
en camelCase— y devuelve **la lista de faltas**, en castellano y vacía si no hay ninguna. Así cada prueba es un
`assert not vigilante(...)` y el mensaje dice qué falló sin que la prueba lo redacte. No importan el SDK: dan lo mismo
se pregunte el servidor por el protocolo, en memoria o por HTTP.

Lo que el catálogo ya garantiza al construirse —un nivel de riesgo, un grupo y un perfil por herramienta— no se repite
aquí. Lo que se mira aquí es que el servidor VIVO diga lo que el catálogo declara.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable, Mapping, Sequence

from .catalogo import Catalogo, nombre_valido

__all__ = ["PISTAS", "RECORTE_DEL_CLIENTE", "anotaciones_distintas", "descripciones_largas", "diferencias", "fantasmas",
           "foto", "fuera_de_presupuesto", "huella_sin_confirmo", "lo_que_lee_el_cliente", "nombres_invalidos",
           "numero_distinto", "peso", "que_distinto_de_la_tabla", "reglas_ausentes", "reglas_cortadas",
           "titulos_distintos"]

Herramientas = Sequence[Mapping[str, Any]]

# Lo que Claude Code lee de las instrucciones de un servidor: los primeros 2 048 caracteres, y nada más (medido el
# 21-nov-2026). Se corta en unidades UTF-16, que son las de una cadena de JavaScript: en castellano coinciden con los
# caracteres, y se cuenta así para que una letra fuera del plano básico no las separe sin que se vea.
RECORTE_DEL_CLIENTE = 2048

# Un nombre citado entre comillas invertidas, que es como un texto para un agente nombra una herramienta.
_CITADO = re.compile(r"`([a-z][a-z0-9_]*[a-z0-9])`")


def lo_que_lee_el_cliente(texto: str, recorte: int = RECORTE_DEL_CLIENTE) -> str:
    return (texto or "").encode("utf-16-le")[:2 * recorte].decode("utf-16-le", errors="ignore")


# --- la foto -------------------------------------------------------------------------------------------------------

def foto(herramientas: Herramientas, recursos: Sequence[Mapping[str, Any]] = (),
         servidor: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Lo que el servidor publica, entero y en una forma que se puede congelar en un JSON:

    - cómo se presenta (`servidor`, tal como lo da quien llama);
    - el ORDEN de herramientas y recursos, porque `tools/list` es una lista y un cliente la enseña así;
    - de cada herramienta, su título, su descripción, su esquema de entrada, el de salida y sus anotaciones, y **sus
      modos** si tiene `que`, que es lo que una familia promete;
    - de cada recurso, su nombre, su título, su descripción y su tipo.
    """
    salida: dict[str, Any] = {}
    if servidor is not None:
        salida["servidor"] = dict(servidor)
    salida["orden"] = {"herramientas": [h["name"] for h in herramientas],
                       "recursos": [str(r["uri"]) for r in recursos]}
    salida["herramientas"] = {}
    for h in herramientas:
        ficha = {"titulo": h.get("title"), "descripcion": h.get("description"), "entrada": h.get("inputSchema"),
                 "salida": h.get("outputSchema"), "anotaciones": h.get("annotations")}
        modos = _modos(h)
        if modos is not None:
            ficha["modos"] = modos
        salida["herramientas"][h["name"]] = ficha
    salida["recursos"] = {str(r["uri"]): {"nombre": r.get("name"), "titulo": r.get("title"),
                                          "descripcion": r.get("description"), "mime": r.get("mimeType")}
                          for r in recursos}
    return salida


def diferencias(congelada: Mapping[str, Any], hoy: Mapping[str, Any]) -> list[str]:
    """Qué cambió entre dos fotos, en frases: lo que sobra, lo que falta y, de lo que está en las dos, qué campo."""
    faltas: list[str] = []
    for seccion in sorted(set(congelada) | set(hoy)):
        a, b = congelada.get(seccion), hoy.get(seccion)
        if isinstance(a, Mapping) and isinstance(b, Mapping) and seccion in ("herramientas", "recursos"):
            faltan, sobran = sorted(set(a) - set(b)), sorted(set(b) - set(a))
            if faltan:
                faltas.append(f"{seccion}: faltan {', '.join(faltan)}")
            if sobran:
                faltas.append(f"{seccion}: sobran {', '.join(sobran)}")
            for nombre in sorted(set(a) & set(b)):
                cambiados = sorted(k for k in set(a[nombre]) | set(b[nombre]) if a[nombre].get(k) != b[nombre].get(k))
                if cambiados:
                    faltas.append(f"{seccion}: en `{nombre}` cambió {', '.join(cambiados)}")
        elif a != b:
            faltas.append(f"cambió «{seccion}»")
    return faltas


# --- lo que pesa ---------------------------------------------------------------------------------------------------

def peso(herramienta: Mapping[str, Any]) -> int:
    """Lo que de una herramienta llega al modelo en cada conversación: su nombre, su descripción y sus parámetros."""
    entrada = json.dumps(herramienta.get("inputSchema") or {}, ensure_ascii=False, separators=(",", ":"))
    return len(herramienta["name"]) + len(herramienta.get("description") or "") + len(entrada)


def fuera_de_presupuesto(herramientas: Herramientas, presupuesto: Mapping[str, int],
                         grupo_de: Mapping[str, str] | Callable[[str], str] | None = None,
                         holgura: int = 1000) -> list[str]:
    """Cada grupo dentro de su presupuesto, y no muy por debajo: **un trinquete en los dos sentidos**. Lo que crece sin
    que nadie lo vea es lo que se quiere evitar, y un presupuesto que se quedó alto deja crecer sin que se vea.

    `grupo_de` dice el grupo de cada herramienta por su nombre; sin él, todas van en uno, el `""`. (Su valor por defecto
    era una `lambda` hasta la 16.2, y una firma que lleva una dirección de memoria no se puede congelar.)
    """
    de: Callable[[str], str | None] = ((lambda _: "") if grupo_de is None
                                       else grupo_de.get if isinstance(grupo_de, Mapping) else grupo_de)
    por_grupo: dict[str, list[tuple[int, str]]] = {}
    for h in herramientas:
        por_grupo.setdefault(de(h["name"]) or "", []).append((peso(h), h["name"]))
    faltas = [f"el grupo «{g}» no tiene presupuesto" for g in sorted(set(por_grupo) - set(presupuesto))]
    for grupo, tope in presupuesto.items():
        pesos = sorted(por_grupo.get(grupo, []), reverse=True)
        medido = sum(p for p, _ in pesos)
        if medido > tope:
            pesadas = " · ".join(f"{n} {p}" for p, n in pesos[:5])
            faltas.append(f"el grupo «{grupo}» pesa {medido} y su presupuesto es {tope}: las que más pesan, {pesadas}. "
                          "O se adelgaza, o se sube el presupuesto a propósito")
        elif tope - medido > holgura:
            faltas.append(f"el grupo «{grupo}» bajó a {medido} y su presupuesto sigue en {tope}: bájalo, que es un "
                          "trinquete")
    return faltas


def descripciones_largas(herramientas: Herramientas, tope: int, margen: int = 200) -> list[str]:
    """Ninguna descripción pasa del tope, y el tope no se queda lejos de la más larga: también es un trinquete."""
    largos = sorted(((len(h.get("description") or ""), h["name"]) for h in herramientas), reverse=True)
    faltas = [f"`{n}` mide {largo} caracteres y el tope es {tope}" for largo, n in largos if largo > tope]
    if largos and tope - largos[0][0] > margen:
        faltas.append(f"la descripción más larga mide {largos[0][0]} y el tope sigue en {tope}: bájalo")
    return faltas


def numero_distinto(herramientas: Herramientas, esperado: int) -> list[str]:
    """El número de herramientas, exacto: juntar o abrir una herramienta es una decisión, no un efecto lateral."""
    n = len(herramientas)
    return [] if n == esperado else [f"hay {n} herramientas y se esperaban {esperado}: si es a propósito, cambia el "
                                     "número en el mismo commit"]


def nombres_invalidos(herramientas: Herramientas) -> list[str]:
    """Los nombres que el API de Claude no acepta (1-64 de letras, cifras, `_` y `-`; el protocolo admite el punto)."""
    return [f"`{h['name']}` no vale como nombre de herramienta para Claude" for h in herramientas
            if not nombre_valido(h["name"])]


# --- lo que el servidor vivo dice frente a lo que el catálogo declara ------------------------------------------------

def _modos(herramienta: Mapping[str, Any]) -> list[str] | None:
    que = ((herramienta.get("inputSchema") or {}).get("properties") or {}).get("que")
    if que is None:
        return None
    rama = next((r for r in que.get("anyOf", [que]) if "enum" in r), que)
    return list(rama.get("enum") or [])


# Las pistas del protocolo que salen del riesgo. El título no está aquí: es de la herramienta, y sus anotaciones pueden
# repetirlo o no —el servidor del motor lo repite, otros no—, así que lo mira `titulos_distintos` (16.2).
PISTAS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")


def anotaciones_distintas(herramientas: Herramientas, catalogo: Catalogo, prefijo: str = "") -> list[str]:
    """Las pistas de cada herramienta (`PISTAS`) son las que dice su riesgo en el catálogo. Una clave que el servidor no
    manda vale lo mismo que `null`: así sirve igual con lo que da el SDK que con lo que viaja por el cable.

    Hasta la 16.1 comparaba también el título dentro de las anotaciones, y marcaba entero a un servidor que lo pone en
    la herramienta y no ahí, que es lo que el protocolo pide: lo vio el primero que la adoptó, con sus 51 herramientas."""
    faltas = []
    for h in herramientas:
        declarada = catalogo.herramientas.get(h["name"].removeprefix(prefijo))
        if declarada is None:
            faltas.append(f"`{h['name']}` no está en el catálogo")
            continue
        esperadas, vivas = declarada.riesgo.anotaciones(), h.get("annotations") or {}
        distintas = [k for k in PISTAS if esperadas.get(k) != vivas.get(k)]
        if distintas:
            faltas.append(f"`{h['name']}` anuncia {', '.join(distintas)} distinto de su riesgo")
    return faltas


def titulos_distintos(herramientas: Herramientas, catalogo: Catalogo, prefijo: str = "") -> list[str]:
    """El título de cada herramienta es el del catálogo, y si sus anotaciones lo repiten, dicen el mismo (16.2). Un
    catálogo sin título espera que no haya ninguno."""
    faltas = []
    for h in herramientas:
        declarada = catalogo.herramientas.get(h["name"].removeprefix(prefijo))
        if declarada is None:
            continue
        esperado = declarada.titulo or None
        if h.get("title") != esperado:
            faltas.append(f"`{h['name']}` se titula «{h.get('title')}» y el catálogo dice «{esperado}»")
        anotado = (h.get("annotations") or {}).get("title")
        if anotado is not None and anotado != esperado:
            faltas.append(f"`{h['name']}` repite en sus anotaciones el título «{anotado}», que no es el suyo")
    return faltas


def que_distinto_de_la_tabla(herramientas: Herramientas, catalogo: Catalogo, prefijo: str = "") -> list[str]:
    """Los valores de `que` que ve el agente son los modos del catálogo, en su orden; y una herramienta de una sola
    operación no tiene `que`."""
    faltas = []
    for h in herramientas:
        declarada = catalogo.herramientas.get(h["name"].removeprefix(prefijo))
        if declarada is None:
            continue
        vivos = _modos(h)
        if declarada.tiene_modos and vivos != list(declarada.modos):
            faltas.append(f"`{h['name']}`: `que` ofrece {vivos} y el catálogo dice {list(declarada.modos)}")
        elif not declarada.tiene_modos and vivos is not None:
            faltas.append(f"`{h['name']}` tiene una sola operación y publica `que`")
    return faltas


def huella_sin_confirmo(herramientas: Herramientas, catalogo: Catalogo, *, confirmo: str = "confirmo",
                        huella: str = "huella", prefijo: str = "") -> list[str]:
    """Lo que pide huella tiene los dos parámetros del segundo paso, y lo que no la pide no los tiene: una confirmación
    a medias es una escritura de un solo paso que parece de dos."""
    faltas = []
    for h in herramientas:
        declarada = catalogo.herramientas.get(h["name"].removeprefix(prefijo))
        if declarada is None:
            continue
        parametros = set(((h.get("inputSchema") or {}).get("properties") or {}))
        tiene = {confirmo, huella} <= parametros
        if declarada.riesgo.huella and not tiene:
            faltas.append(f"`{h['name']}` pide huella y no tiene `{confirmo}` y `{huella}`")
        elif not declarada.riesgo.huella and parametros & {confirmo, huella}:
            faltas.append(f"`{h['name']}` no pide huella y tiene parámetros de confirmación")
    return faltas


# --- los textos ----------------------------------------------------------------------------------------------------

def reglas_cortadas(instrucciones: str, frases: Mapping[str, str], recorte: int = RECORTE_DEL_CLIENTE,
                    fuera_del_recorte: Iterable[str] = ()) -> list[str]:
    """Cada regla está en las instrucciones y **dentro de lo que el cliente lee**: una regla cortada no existe para su
    modelo. `fuera_del_recorte` es un trinquete de las que todavía no caben, que solo se vacía."""
    leido = lo_que_lee_el_cliente(instrucciones, recorte)
    fuera = set(fuera_del_recorte)
    faltas = []
    for clave, frase in frases.items():
        if frase not in instrucciones:
            faltas.append(f"las instrucciones ya no dicen la regla «{clave}»")
        elif frase not in leido and clave not in fuera:
            faltas.append(f"la regla «{clave}» queda detrás del carácter {recorte}, donde el cliente ya no lee: las "
                          f"instrucciones miden {len(instrucciones)}")
        elif frase in leido and clave in fuera:
            faltas.append(f"la regla «{clave}» ya cabe y sigue entre las que no caben: sácala de ahí")
    return faltas


def reglas_ausentes(herramientas: Herramientas, donde_se_aplica: Mapping[str, tuple[str, Iterable[str]]]) -> list[str]:
    """Cada regla vive en la descripción de la herramienta donde se aplica: el modelo la lee al mirar esa herramienta,
    lea o no el cliente las instrucciones. `donde_se_aplica` es `{regla: (frase, herramientas)}`; se compara sin
    negritas y sin mayúsculas."""
    descripciones = {h["name"]: (h.get("description") or "").replace("*", "").lower() for h in herramientas}
    return [f"`{nombre}` no dice «{frase}» ({regla})"
            for regla, (frase, donde) in donde_se_aplica.items() for nombre in donde
            if frase.replace("*", "").lower() not in descripciones.get(nombre, "")]


def fantasmas(textos: Mapping[str, str], vivas: Iterable[str], sospechoso: Callable[[str], bool],
              exentos: Iterable[str] = ()) -> list[str]:
    """Los textos que mandan al agente a una herramienta que no existe.

    Se mira cada nombre citado entre comillas invertidas. Es un fantasma si **parece** una herramienta —lo dice
    `sospechoso`, que cada servidor arma con sus nombres: los de sus operaciones, sus retiradas, sus prefijos— y no es
    una de las `vivas`. `exentos` son los nombres que se citan y no son herramientas, como los valores de `que`.
    `textos` es `{dónde: texto}`, y la falta dice dónde se citó.
    """
    vivas, exentos = set(vivas), set(exentos)
    donde: dict[str, set[str]] = {}
    for origen, texto in textos.items():
        for nombre in _CITADO.findall(texto or ""):
            if nombre not in vivas and nombre not in exentos and sospechoso(nombre):
                donde.setdefault(nombre, set()).add(origen)
    return [f"`{n}` no es una herramienta y se cita en {', '.join(sorted(d))}" for n, d in sorted(donde.items())]
