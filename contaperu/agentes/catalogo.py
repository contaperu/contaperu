"""El catálogo de lo que un servidor MCP publica: cada operación, la herramienta en la que va y lo que arriesga.

Separa dos cosas que un servidor generado una a una desde su tabla confunde:

- **la operación**, que es la capacidad —«los totales del mes», «guardar los centros de costo»—, y
- **la herramienta**, que es lo que ve el agente: un nombre, un título y, si junta varias operaciones de una misma
  familia, un parámetro `que` que elige cuál.

Pocas herramientas pensadas para un flujo rinden más que una por operación, y los servidores grandes convergen en lo
mismo: un registro de operaciones con sus metadatos (riesgo, grupo, a quién se publica, qué nombre se retiró) que se
PROYECTA en herramientas, en vez de publicarse tal cual. Este módulo es ese registro, sin el SDK del protocolo: la
proyección sobre el SDK va aparte, y cuando cambie la versión mayor del SDK solo cambia esa.

Las reglas que hacen segura una familia se comprueban al construir el catálogo, no se confían a la buena voluntad:
**una herramienta, un nivel de riesgo** —sus operaciones miran todas, o escriben todas, y llevan huella todas o
ninguna—, porque un cliente pide permiso por herramienta y no por modo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..errores import ErrorContaperu

__all__ = ["MIRA", "PERFILES", "Catalogo", "CatalogoInvalido", "Ficha", "Herramienta", "Retirada", "Riesgo",
           "nombre_valido"]

# A quién se publica una herramienta (B10). `publico` es lo que sirve el servidor abierto, sin autenticación;
# `integrador`, lo que solo monta quien tiene su propio servidor encima. El perfil `integrador` incluye al público.
PERFILES = ("publico", "integrador")

# El nombre de una herramienta. El protocolo admite además el punto, pero el API de Claude no: este es el patrón que
# aceptan los dos, y por eso un prefijo se une con `_` y no con `.`.
NOMBRE_DE_HERRAMIENTA = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# El de una operación y el de un modo: los que la traducción sabe encontrar entre comillas invertidas.
NOMBRE_DE_OPERACION = re.compile(r"^[a-z][a-z0-9_]*$")


def nombre_valido(nombre: str) -> bool:
    """Si `nombre` vale como nombre de herramienta para el protocolo y para el API de Claude."""
    return bool(NOMBRE_DE_HERRAMIENTA.match(nombre or ""))


class CatalogoInvalido(ErrorContaperu, ValueError):
    """Un catálogo que rompe una regla de la proyección. Dice todas las faltas a la vez, no la primera."""

    def __init__(self, faltas: list[str]):
        self.faltas = faltas
        super().__init__("El catálogo no se puede publicar:\n- " + "\n- ".join(faltas))


@dataclass(frozen=True)
class Riesgo:
    """Lo que una operación arriesga, que es lo que el cliente necesita para decidir si pide permiso.

    - `escribe`: cambia algo. Si no, solo mira.
    - `borra`: lo que cambia no se recupera. Solo tiene sentido si escribe.
    - `huella`: pide dos pasos, una vista previa que devuelve una huella y la confirmación que la trae de vuelta.
    - `sale_a_la_red`: habla con un sistema de fuera. `None` es «no se declara»: el protocolo lo deja sin decir.
    """

    escribe: bool = False
    borra: bool = False
    huella: bool = False
    sale_a_la_red: bool | None = False

    def faltas(self) -> list[str]:
        salida = []
        if self.borra and not self.escribe:
            salida.append("borra sin escribir")
        if self.huella and not self.escribe:
            salida.append("pide huella sin escribir: una confirmación de algo que no cambia nada")
        return salida

    def anotaciones(self) -> dict[str, Any]:
        """Las pistas del protocolo (`ToolAnnotations`), como viajan. `destructiveHint` solo se dice de lo que escribe:
        con `readOnlyHint` puesto no significa nada."""
        return {"readOnlyHint": not self.escribe, "destructiveHint": self.borra if self.escribe else None,
                "idempotentHint": None, "openWorldHint": self.sale_a_la_red}


MIRA = Riesgo()


@dataclass(frozen=True)
class Ficha:
    """Una operación tal como se publica: en qué herramienta va, con qué modo, lo que arriesga y a quién se enseña.

    `modo` es el valor de `que` que la elige, y va vacío si la herramienta tiene una sola operación. `titulo` es el de
    la operación: el de la herramienta lo pone el catálogo, y si no lo dice, es el de su primera ficha. `grupo` junta
    herramientas para que un servidor publique solo algunas.
    """

    operacion: str
    herramienta: str
    modo: str = ""
    titulo: str = ""
    riesgo: Riesgo = MIRA
    grupo: str = ""
    perfil: str = "publico"


@dataclass(frozen=True)
class Herramienta:
    """Lo que ve el agente: un nombre, un título y las fichas que elige su `que`, la de por defecto primero."""

    nombre: str
    titulo: str
    fichas: tuple[Ficha, ...]

    @property
    def tiene_modos(self) -> bool:
        return len(self.fichas) > 1

    @property
    def modos(self) -> tuple[str, ...]:
        return tuple(f.modo for f in self.fichas if f.modo)

    @property
    def principal(self) -> Ficha:
        """La primera: la que se llama como la herramienta, si la hay, que es la del modo por defecto."""
        return self.fichas[0]

    @property
    def por_defecto(self) -> str:
        """El valor de `que` cuando no se dice, o vacío si la herramienta obliga a decirlo: lo tiene la que conserva el
        nombre de una de sus operaciones, para que las llamadas de siempre sigan valiendo."""
        return self.principal.modo if self.principal.operacion == self.nombre else ""

    @property
    def riesgo(self) -> Riesgo:
        return self.principal.riesgo

    @property
    def grupo(self) -> str:
        return self.principal.grupo

    @property
    def perfil(self) -> str:
        return self.principal.perfil

    def anotaciones(self) -> dict[str, Any]:
        return {"title": self.titulo or None, **self.riesgo.anotaciones()}

    def de_modo(self, que: str) -> Ficha | None:
        """La ficha de un modo, o `None` si la herramienta no lo tiene."""
        return next((f for f in self.fichas if f.modo == que), None)


@dataclass(frozen=True)
class Retirada:
    """Un nombre que fue una herramienta y ya no lo es: ahora es `herramienta`, con `que: modo` si lo tiene.

    Un cliente guarda la lista de herramientas hasta que se reconecta, así que una conversación abierta antes de juntar
    una familia sigue llamando al nombre viejo. Sin esto recibiría «herramienta desconocida» y no sabría qué hacer.
    `ejecuta` dice si el servidor lo atiende como antes (un alias) o solo contesta dónde está ahora: para lo que solo
    mira, ejecutar no tiene riesgo; para lo que escribe, una confirmación dada bajo otro nombre no se reaprovecha.
    """

    nombre: str
    herramienta: str
    modo: str = ""
    ejecuta: bool = False

    def frase(self, prefijo: str = "") -> str:
        donde = f"`{prefijo}{self.herramienta}`" + (f" con `que: {self.modo}`" if self.modo else "")
        return f"`{prefijo}{self.nombre}` ya no es una herramienta: ahora es {donde}."


_CITADO = re.compile(r"`([a-z][a-z0-9_]*)`")


class Catalogo:
    """Las fichas de un servidor, agrupadas en herramientas y comprobadas.

    El orden de las fichas es el de publicación. Dentro de una herramienta, la que se llama como ella va primero
    (la ordenación es estable): es la de por defecto. Se comprueba al construirlo y no cambia después.
    """

    def __init__(self, fichas: Iterable[Ficha], *, titulos: Mapping[str, str] | None = None,
                 retiradas: Iterable[Retirada] = ()):
        self.fichas: tuple[Ficha, ...] = tuple(fichas)
        self.titulos: dict[str, str] = dict(titulos or {})
        self.retiradas_declaradas: tuple[Retirada, ...] = tuple(retiradas)
        grupos: dict[str, list[Ficha]] = {}
        for f in self.fichas:
            grupos.setdefault(f.herramienta, []).append(f)
        self.herramientas: dict[str, Herramienta] = {
            nombre: Herramienta(nombre, self.titulos.get(nombre) or fs[0].titulo,
                                tuple(sorted(fs, key=lambda f, n=nombre: f.operacion != n)))
            for nombre, fs in grupos.items()}
        self.por_operacion: dict[str, Ficha] = {f.operacion: f for f in self.fichas}
        faltas = self._faltas()
        if faltas:
            raise CatalogoInvalido(faltas)

    # --- lo que se comprueba al construirlo ------------------------------------------------------------------------

    def _faltas(self) -> list[str]:
        faltas: list[str] = []
        vistas: set[str] = set()
        for f in self.fichas:
            if f.operacion in vistas:
                faltas.append(f"la operación `{f.operacion}` está dos veces")
            vistas.add(f.operacion)
            if not NOMBRE_DE_OPERACION.match(f.operacion):
                faltas.append(f"`{f.operacion}` no vale como nombre de operación (minúsculas, cifras y `_`)")
            if f.perfil not in PERFILES:
                faltas.append(f"`{f.operacion}`: el perfil «{f.perfil}» no es uno de {', '.join(PERFILES)}")
            faltas.extend(f"`{f.operacion}` {falta}" for falta in f.riesgo.faltas())
        for h in self.herramientas.values():
            if not nombre_valido(h.nombre):
                faltas.append(f"`{h.nombre}` no vale como nombre de herramienta (1-64 de letras, cifras, `_` y `-`)")
            modos = [f.modo for f in h.fichas]
            if h.tiene_modos:
                if not all(modos):
                    faltas.append(f"`{h.nombre}` junta varias operaciones y no todas dicen su modo")
                if len(set(modos)) != len(modos):
                    faltas.append(f"`{h.nombre}` repite un modo: {', '.join(modos)}")
                faltas.extend(f"`{h.nombre}`: el modo «{m}» no vale (minúsculas, cifras y `_`)"
                              for m in modos if m and not NOMBRE_DE_OPERACION.match(m))
            elif modos[0]:
                faltas.append(f"`{h.nombre}` tiene una sola operación y le pone modo: `que` no tendría qué elegir")
            for rasgo, decir in (("riesgo", "un nivel de riesgo"), ("grupo", "un grupo"), ("perfil", "un perfil")):
                if len({getattr(f, rasgo) for f in h.fichas}) > 1:
                    faltas.append(f"`{h.nombre}` mezcla operaciones de más de {decir}: un cliente pide permiso por "
                                  "herramienta, no por modo")
        for r in self.retiradas_declaradas:
            h = self.herramientas.get(r.herramienta)
            if r.nombre in self.herramientas:
                faltas.append(f"`{r.nombre}` se declara retirada y sigue siendo una herramienta")
            elif h is None:
                faltas.append(f"la retirada `{r.nombre}` apunta a `{r.herramienta}`, que no es una herramienta")
            elif (r.modo or h.tiene_modos) and h.de_modo(r.modo) is None:
                faltas.append(f"la retirada `{r.nombre}` pide `que: {r.modo}`, y `{r.herramienta}` no lo tiene")
        return faltas

    # --- lo que se le pregunta ---------------------------------------------------------------------------------------

    def herramienta(self, nombre: str) -> Herramienta:
        return self.herramientas[nombre]

    @property
    def retiradas(self) -> dict[str, Retirada]:
        """Las declaradas y las que se deducen solas: una operación que es un MODO de una herramienta de otro nombre fue,
        por su nombre, una herramienta propia antes de juntarse con su familia. Una que solo se publica con otro nombre
        —`leer_xml` como `leer_xml_ubl`— no: ese nombre nunca fue de una herramienta. Las declaradas mandan."""
        deducidas = {f.operacion: Retirada(f.operacion, f.herramienta, f.modo) for f in self.fichas
                     if f.modo and f.operacion != f.herramienta and f.operacion not in self.herramientas}
        return {**deducidas, **{r.nombre: r for r in self.retiradas_declaradas}}

    def elegir(self, *, perfil: str = "integrador", grupos: Iterable[str] | None = None,
               herramientas: Iterable[str] | None = None, solo_lectura: bool = False) -> Catalogo:
        """El catálogo con solo lo que un servidor publica, en el mismo orden.

        `perfil="publico"` deja fuera lo que es de un integrador; `grupos` y `herramientas` acotan a los que se nombran
        (un nombre que no existe es un error, no un filtro que no filtra); `solo_lectura` deja fuera lo que escribe.
        """
        if perfil not in PERFILES:
            raise CatalogoInvalido([f"el perfil «{perfil}» no es uno de {', '.join(PERFILES)}"])
        grupos = None if grupos is None else set(grupos)
        nombres = None if herramientas is None else set(herramientas)
        faltas = [f"`{n}` no es una herramienta" for n in sorted(nombres or ()) if n not in self.herramientas]
        faltas += [f"«{g}» no es un grupo" for g in sorted(grupos or ())
                   if g not in {h.grupo for h in self.herramientas.values()}]
        if faltas:
            raise CatalogoInvalido(faltas)

        def queda(h: Herramienta) -> bool:
            return ((perfil == "integrador" or h.perfil == "publico") and (grupos is None or h.grupo in grupos)
                    and (nombres is None or h.nombre in nombres) and not (solo_lectura and h.riesgo.escribe))

        quedan = {n for n, h in self.herramientas.items() if queda(h)}
        return Catalogo([f for f in self.fichas if f.herramienta in quedan], titulos=self.titulos,
                        retiradas=[r for r in self.retiradas_declaradas if r.herramienta in quedan])

    def en_la_puerta(self, texto: str, prefijo: str = "") -> str:
        """El texto con cada operación citada entre comillas invertidas dicha como se alcanza por esta puerta: la de un
        modo, como «`herramienta` (`que: modo`)», y con el prefijo del servidor si lo lleva.

        Quien escribe una frase de error o un dato que nombra una operación la escribe una vez, con el nombre de la
        operación, y cada puerta la dice en su idioma: así juntar una familia no obliga a reescribir frases.
        """
        def traducido(m: re.Match[str]) -> str:
            nombre = m.group(1)
            f = self.por_operacion.get(nombre)
            if f is not None:
                if f.operacion != f.herramienta and f.modo:
                    return f"`{prefijo}{f.herramienta}` (`que: {f.modo}`)"
                return f"`{prefijo}{f.herramienta}`" if (prefijo or f.operacion != f.herramienta) else m.group(0)
            if prefijo and nombre in self.herramientas:
                return f"`{prefijo}{nombre}`"
            return m.group(0)
        return _CITADO.sub(traducido, texto or "")

    def traducido(self, valor: Any, prefijo: str = "") -> Any:
        """`en_la_puerta` aplicado a cada texto de un valor, a cualquier profundidad: diccionarios, listas y tuplas. Lo
        que no es texto, y el texto sin comillas invertidas, pasa tal cual."""
        if isinstance(valor, str):
            return self.en_la_puerta(valor, prefijo) if "`" in valor else valor
        if isinstance(valor, dict):
            return {k: self.traducido(v, prefijo) for k, v in valor.items()}
        if isinstance(valor, list):
            return [self.traducido(v, prefijo) for v in valor]
        if isinstance(valor, tuple):
            return tuple(self.traducido(v, prefijo) for v in valor)
        return valor
