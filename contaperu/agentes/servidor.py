"""La base MCP sobre el SDK del protocolo: un servidor al que se le registran catálogos, el del motor o el de otro.

Es el ÚNICO módulo de la base que importa el SDK (`mcp` 2.x, `MCPServer`), y por eso es una puerta más —está en esa
capa—: cuando cambie la versión mayor del SDK, cambia esto y no el catálogo.

Lo que añade al `MCPServer` del SDK, y que todo servidor montado encima necesita igual:

- **`Servidor`**, por el que pasa cada llamada en este orden: el nombre retirado (que contesta dónde está ahora, o se
  atiende si la retirada lo permite), la `guarda` de la aplicación —que es donde pone su autenticación: contaperu no
  guarda identidades ni estado—, la herramienta, la traducción de los nombres de operación al de esta puerta y el
  error dicho con su clave. Y `visibles`, que filtra lo que `tools/list` enseña según quién llama.
- **`registrar`**, que proyecta un `Catalogo` en herramientas: una función por herramienta, o una `familia` de
  funciones —una por modo— detrás de una sola con `que`. Un nombre repetido es un error (`ChoqueDeNombres`), no el
  aviso del SDK, que se queda con la primera y tapa la segunda sin que se vea. Y **`Servidor.declarar`** (16.1), para el
  servidor que escribe sus herramientas a mano con los decoradores del SDK: pone su catálogo bajo la base sin volver a
  registrarlas, con la misma traducción, las mismas retiradas y el mismo modo en curso.
- **`crear_servidor`** y **`registrar_del_motor`**, que publican las herramientas y los recursos del motor en un servidor
  nuevo o en el de otro. Una FÁBRICA, y no una instancia que se modifica: dos servidores no comparten nada.
- **`servir`**, el arranque por entrada y salida estándar o por HTTP, sin sesiones y con la defensa del `Host`.
"""
from __future__ import annotations

import contextvars
import functools
import inspect
import json
import sys
from dataclasses import dataclass
from typing import Annotated, Any, Awaitable, Callable, Iterable, Mapping, get_type_hints

import anyio.to_thread
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp.types import BlobResourceContents, CallToolResult, EmbeddedResource, TextContent, ToolAnnotations
from pydantic import Field, TypeAdapter, WithJsonSchema

from .. import _datos, api
from ..api import textos
from ..api.tabla import PARAMETROS
from ..errores import ErrorContaperu
from ..puertas.comun import MAXIMO_ARCHIVO, hosts_permitidos, origenes_permitidos, peso_de_base64
from .catalogo import MIRA, Catalogo, CatalogoInvalido, Herramienta, Retirada, nombre_valido
from .del_motor import DEL_MOTOR, catalogo_del_motor
from .despacho import EntradaInvalida, operacion_del_modo, solo_los_de_su_modo

__all__ = ["SOLO_LECTURA", "ChoqueDeNombres", "Familia", "Servidor", "como_problema", "contesta", "crear_servidor",
           "en_curso", "familia", "registrar", "registrar_del_motor", "seguridad", "servir"]


class ChoqueDeNombres(ErrorContaperu, ValueError):
    """Dos herramientas, o dos recursos, con el mismo nombre en un servidor. El SDK se queda con la primera y solo lo
    dice en el log, así que la segunda desaparecería sin que nadie lo viera: se publica con un prefijo."""


# --- cómo se dice lo que devuelve una herramienta -----------------------------------------------------------------

def _adjunto(nombre: str, b64: str, mime: str) -> EmbeddedResource:
    """Devuelve un archivo COMO ARCHIVO, no como una tira de texto dentro de un campo.

    El protocolo habla JSON y un `.xlsx` es un ZIP: no cabe tal cual, hay que meterlo en base64.
    Pero eso no es «otro formato» —al decodificarlo vuelve el mismo archivo, byte a byte—, y la
    diferencia entre que el cliente lo ofrezca para guardar o lo enseñe como un muro de letras
    está en el envoltorio: un recurso incrustado con su `blob` y su `mimeType`, en vez de un
    campo `contenido_base64` que nadie sabe reconocer.
    """
    return EmbeddedResource(
        type="resource",
        resource=BlobResourceContents(
            uri=f"contaperu://salida/{nombre}",
            mime_type=mime.split(";")[0].strip() or "application/octet-stream",
            blob=b64,
        ),
    )


def _dicho(valor: Any) -> CallToolResult:
    """Lo que devuelve una operación, como el JSON que el agente lee."""
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(valor, ensure_ascii=False, indent=1))])


def como_problema(error: BaseException) -> str:
    """Un rechazo dicho como lo dice la puerta HTTP: un «problem details» del RFC 9457, con su `clave` estable.

    Es la misma `api.problema` que responde por HTTP, y por dos motivos. El primero es que una `clave` se
    puede ramificar y una frase no: un cliente que recibe «Error executing tool exportar: 3 comprobantes
    tienen observaciones que bloquean» no sabe distinguir eso de que el motor haya reventado. El segundo
    pesa más: un error que NO es del motor puede llevar pegada una ruta o un dato interno, y `api.problema`
    lo enmascara. Sin esto, lo que la puerta HTTP se cuida de no enseñar salía entero por la puerta MCP,
    que además es la que está publicada sin autenticación.
    """
    return json.dumps(api.problema(error), ensure_ascii=False, indent=1)


def _rechazo(texto: str) -> CallToolResult:
    return CallToolResult(is_error=True, content=[TextContent(type="text", text=texto)])


def contesta(funcion: Callable[..., Any]) -> Callable[..., CallToolResult]:
    """Hace que una herramienta conteste con esa forma, pase lo que pase.

    La firma se conserva tal cual —es lo que el agente ve como `inputSchema`— y solo se cambia lo que
    devuelve, porque `CallToolResult` es la anotación con la que el SDK entrega la respuesta sin tocarla.
    Que la firma siga intacta después de decorar no es confianza: lo comprueba
    `test_la_puerta_mcp_recibe_lo_mismo_que_la_http`, que las compara contra `api.OPERACIONES`.
    """
    @functools.wraps(funcion)
    def herramienta(*posicionales: Any, **argumentos: Any) -> CallToolResult:
        try:
            resultado = funcion(*posicionales, **argumentos)
        except Exception as error:      # cualquiera se dice igual: `api.problema` decide cuánto se enseña
            return _rechazo(como_problema(error))
        return resultado if isinstance(resultado, CallToolResult) else _dicho(resultado)

    # La firma se entrega ya resuelta. Este módulo aplaza las anotaciones (`from __future__ import annotations`),
    # así que `inspect.signature` las devuelve como texto, y un alias declarado aquí —lo fue `FECHA` hasta la
    # 15.15.0— deja de resolverse al mirarlas desde el envoltorio. Con las pistas resueltas, el SDK ve exactamente los
    # mismos tipos que veía antes de decorar.
    firma = inspect.signature(funcion)
    pistas = get_type_hints(funcion, include_extras=True)
    parametros = [p.replace(annotation=pistas.get(p.name, p.annotation)) for p in firma.parameters.values()]
    herramienta.__signature__ = firma.replace(parameters=parametros, return_annotation=CallToolResult)
    return herramienta


# Hito 0.2: cada herramienta del motor se anuncia de solo lectura y sin salir a ningún sitio —no guarda nada, no toca el
# disco ni la red—, así que un cliente puede llamarla sin pedir confirmación por un efecto que no tiene. Desde la 16.0
# es lo que dice su riesgo en el catálogo (`MIRA`), y se conserva con su nombre porque se importa.
SOLO_LECTURA = ToolAnnotations(**MIRA.anotaciones())


# --- el servidor --------------------------------------------------------------------------------------------------

# Qué herramienta se está atendiendo y con qué modo: lo pone `Servidor.call_tool` y lo lee quien lo necesite dentro de
# la petición —una guarda, una herramienta—, porque el contexto del SDK no lo trae.
_EN_CURSO: contextvars.ContextVar[tuple[str, str]] = contextvars.ContextVar("herramienta_en_curso", default=("", ""))


def en_curso() -> tuple[str, str]:
    """La herramienta que se está atendiendo, con el nombre con que se publicó, y su modo (vacío si no tiene)."""
    return _EN_CURSO.get()


@dataclass(frozen=True)
class _Publicada:
    catalogo: Catalogo
    herramienta: Herramienta
    prefijo: str


Guarda = Callable[[str, str, dict[str, Any]], "None | Awaitable[None]"]


class Servidor(MCPServer):
    """El `MCPServer` del SDK, con el recorrido que toda llamada de la base hace. Ver el docstring del módulo.

    - `guarda(herramienta, modo, argumentos)` corre antes de cada llamada y niega lanzando una excepción, que se dice
      con `decir_error`. Es el gancho de la autenticación: lee el token de la petición, comprueba la grada, y no deja
      nada guardado. Puede ser asíncrona.
    - `visibles(nombres)` recibe los nombres y devuelve los que quien llama puede ver. Lo oculto tampoco se puede
      llamar, porque el SDK, a propósito, sí deja llamar a lo que no lista.
    - `decir_error(excepcion)` dice un error de una herramienta; por defecto, como el «problem details» del motor.
    - `decir_retirada(retirada, prefijo)` dice dónde está ahora un nombre retirado.

    Lo demás va tal cual al SDK (`token_verifier`, `auth`, `website_url`, `icons`…).
    """

    def __init__(self, nombre: str, *, instrucciones: str | None = None, version: str | None = None,
                 guarda: Guarda | None = None, visibles: Callable[[list[str]], Iterable[str]] | None = None,
                 decir_error: Callable[[BaseException], str] = como_problema,
                 decir_retirada: Callable[[Retirada, str], str] | None = None, **del_sdk: Any):
        super().__init__(nombre, instructions=instrucciones, version=version or "", **del_sdk)
        self._guarda = guarda
        self._visibles = visibles
        self._decir_error = decir_error
        self._decir_retirada = decir_retirada or (lambda retirada, prefijo: retirada.frase(prefijo))
        self._nombres: set[str] = set()
        self._uris: set[str] = set()
        self._publicadas: dict[str, _Publicada] = {}
        self._retiradas: dict[str, tuple[Retirada, str]] = {}

    # Lo que se registra pasa por aquí, también con los decoradores del SDK (`@servidor.tool()`), que llaman a estos
    # dos: así un choque se ve venga de donde venga.
    def add_tool(self, fn: Callable[..., Any], name: str | None = None, *args: Any, **kwargs: Any) -> None:
        nombre = name or fn.__name__
        if nombre in self._nombres:
            raise ChoqueDeNombres(f"Ya hay una herramienta `{nombre}` en este servidor: publica la otra con un prefijo.")
        super().add_tool(fn, nombre, *args, **kwargs)
        self._nombres.add(nombre)

    def add_resource(self, resource: Any) -> None:
        uri = str(resource.uri)
        if uri in self._uris:
            raise ChoqueDeNombres(f"Ya hay un recurso `{uri}` en este servidor.")
        super().add_resource(resource)
        self._uris.add(uri)

    def declarar(self, catalogo: Catalogo, *, prefijo: str = "") -> list[str]:
        """Pone bajo la base las herramientas de `catalogo` que ya están registradas en este servidor (16.1). Desde ahí,
        lo que contestan cita las operaciones con el nombre de esta puerta, sus nombres retirados contestan dónde están
        ahora y `en_curso()` dice con qué modo se las llamó. Devuelve los nombres declarados.

        Es para el servidor que escribe sus herramientas a mano, cada una con su firma y su modelo de salida, con los
        decoradores del SDK (`@servidor.tool(...)`), y no puede pasarlas por `registrar`, que las arma desde funciones y
        declara las suyas solo. Una herramienta del catálogo que no esté registrada, o que ya esté declarada, es un
        error: un catálogo que dice más de lo que el servidor sirve, o lo dice dos veces, es un catálogo equivocado.
        """
        faltas = [f"`{prefijo}{nombre}` no está registrada en este servidor" for nombre in catalogo.herramientas
                  if prefijo + nombre not in self._nombres]
        faltas += [f"`{prefijo}{nombre}` ya está declarada" for nombre in catalogo.herramientas
                   if prefijo + nombre in self._publicadas]
        if faltas:
            raise CatalogoInvalido(faltas)
        for nombre, h in catalogo.herramientas.items():
            self._publicadas[prefijo + nombre] = _Publicada(catalogo, h, prefijo)
        for retirada in catalogo.retiradas.values():
            self._retiradas.setdefault(prefijo + retirada.nombre, (retirada, prefijo))
        return [prefijo + nombre for nombre in catalogo.herramientas]

    def _visible(self, nombres: list[str]) -> set[str]:
        return set(nombres) if self._visibles is None else set(self._visibles(nombres))

    async def list_tools(self) -> Any:
        todas = await super().list_tools()
        vistas = self._visible([h.name for h in todas])
        return [h for h in todas if h.name in vistas]

    async def call_tool(self, name: str, arguments: dict[str, Any], context: Any = None) -> Any:
        arguments = dict(arguments or {})
        if name not in self._nombres and name in self._retiradas:
            retirada, prefijo = self._retiradas[name]
            if not retirada.ejecuta:
                return _rechazo(self._decir_retirada(retirada, prefijo))
            name = prefijo + retirada.herramienta
            if retirada.modo:
                arguments["que"] = retirada.modo
        if name not in self._visible([name]):
            # Lo mismo que contesta el SDK de un nombre que no tiene: lo oculto no se distingue de lo que no existe.
            return _rechazo(f"Unknown tool: {name}")
        publicada = self._publicadas.get(name)
        modo = ""
        if publicada is not None and publicada.herramienta.tiene_modos:
            modo = str(arguments.get("que") or publicada.herramienta.por_defecto)
        testigo = _EN_CURSO.set((name, modo))
        try:
            if self._guarda is not None:
                try:
                    negado = self._guarda(name, modo, arguments)
                    if inspect.isawaitable(negado):
                        await negado
                except Exception as error:      # la guarda negó: se dice como cualquier error de una herramienta
                    return self._traducido(_rechazo(self._decir_error(error)), publicada)
            resultado = await super().call_tool(name, arguments, context)
        except MCPError:
            raise                               # un error del protocolo no es de la herramienta: sigue su camino
        except UnexpectedToolError as error:
            # La v2 del SDK solo copia el texto de un `ToolError`: de cualquier otra excepción, el agente leería
            # «Error executing tool X» y nada más. Aquí se dice la causa, con su clave.
            resultado = _rechazo(self._decir_error(error.__cause__ or error))
        except ToolError as error:
            resultado = _rechazo(str(error))
        finally:
            _EN_CURSO.reset(testigo)
        return self._traducido(resultado, publicada)

    @staticmethod
    def _traducido(resultado: Any, publicada: _Publicada | None) -> Any:
        """Los nombres de operación citados en lo que contesta, dichos como se alcanzan por esta puerta: en el texto y
        en lo estructurado. Los adjuntos no se tocan."""
        if publicada is None or not isinstance(resultado, CallToolResult):
            return resultado
        catalogo, prefijo = publicada.catalogo, publicada.prefijo
        contenido = [b.model_copy(update={"text": catalogo.en_la_puerta(b.text, prefijo)})
                     if isinstance(b, TextContent) and "`" in b.text else b for b in resultado.content]
        estructurado = (catalogo.traducido(resultado.structured_content, prefijo)
                        if resultado.structured_content is not None else None)
        return resultado.model_copy(update={"content": contenido, "structured_content": estructurado})


# --- una familia de operaciones detrás de una herramienta ------------------------------------------------------------

@dataclass(frozen=True)
class Familia:
    """Las funciones de una herramienta con modos, una por valor de `que`, y la descripción de la herramienta."""

    descripcion: str
    modos: Mapping[str, Callable[..., Any]]


def familia(descripcion: str, modos: Mapping[str, Callable[..., Any]]) -> Familia:
    """Una herramienta con `que`, armada con una función por modo. Su firma es la unión de las de sus modos, más `que`;
    lo que el esquema no hace —rechazar el parámetro de otro modo, exigir el obligatorio del modo pedido— lo hace el
    despacho, con `entrada_invalida`."""
    return Familia(descripcion, dict(modos))


_VACIO = inspect.Parameter.empty


def _parametros(funcion: Callable[..., Any]) -> list[inspect.Parameter]:
    pistas = get_type_hints(funcion, include_extras=True)
    return [p.replace(annotation=pistas.get(p.name, p.annotation)) for p in inspect.signature(funcion).parameters.values()]


def _es_el_de_por_defecto(valor: Any, por_defecto: Any) -> bool:
    """Si `valor` es el de por defecto, comparando también el tipo: `0` no es `False`."""
    return valor is por_defecto or (type(valor) is type(por_defecto) and valor == por_defecto)


def _la_familia(nombre: str, h: Herramienta, fam: Familia) -> Callable[..., Any]:
    if set(fam.modos) != set(h.modos):
        raise CatalogoInvalido([f"la familia `{nombre}` trae los modos {sorted(fam.modos)} y el catálogo dice "
                                f"{sorted(h.modos)}"])
    propios = {modo: {p.name for p in _parametros(f)} for modo, f in fam.modos.items()}
    obligatorios = {modo: {p.name for p in _parametros(f) if p.default is _VACIO} for modo, f in fam.modos.items()}
    union: dict[str, inspect.Parameter] = {}
    for modo in h.modos:
        for p in _parametros(fam.modos[modo]):
            # Lo obligatorio de un modo es opcional en la herramienta: el despacho lo exige en su modo.
            tipo = Any if p.annotation is _VACIO else p.annotation
            opcional = p if p.default is not _VACIO else p.replace(default=None, annotation=tipo | None)
            union.setdefault(p.name, opcional.replace(kind=inspect.Parameter.KEYWORD_ONLY))
    que = inspect.Parameter("que", inspect.Parameter.KEYWORD_ONLY, default=h.por_defecto or _VACIO,
                            annotation=Annotated[str, Field(description="Qué se pide",
                                                            json_schema_extra={"enum": list(h.modos)})])

    por_defecto = {p.name: p.default for p in union.values()}

    async def herramienta(**argumentos: Any) -> Any:
        ficha = operacion_del_modo(h, argumentos.pop("que", "") or "")
        # Lo que llega con el valor por defecto de la herramienta no se pasó: lo rellena pydantic con el de la unión,
        # que es el del primer modo que tiene ese parámetro, y cada modo aplica después el suyo.
        pasados = {p: v for p, v in argumentos.items() if not _es_el_de_por_defecto(v, por_defecto.get(p, _VACIO))}
        solo_los_de_su_modo(ficha.modo, propios, **pasados)
        faltan = sorted(p for p in obligatorios[ficha.modo] if p not in pasados)
        if faltan:
            raise EntradaInvalida(f"Con `que: {ficha.modo}` hace falta {', '.join(f'`{p}`' for p in faltan)}.")
        funcion = fam.modos[ficha.modo]
        pasados = {p: v for p, v in pasados.items() if p in propios[ficha.modo]}
        if inspect.iscoroutinefunction(funcion):
            return await funcion(**pasados)
        # Una función síncrona va a un hilo, como hace el SDK con las suyas: no deja esperando a los demás.
        return await anyio.to_thread.run_sync(functools.partial(funcion, **pasados))

    herramienta.__name__ = nombre
    herramienta.__doc__ = fam.descripcion
    # `que` primero; y si no tiene valor por defecto, es lo único obligatorio del esquema.
    parametros = [que, *union.values()]
    herramienta.__signature__ = inspect.Signature(parametros)  # type: ignore[attr-defined]
    herramienta.__annotations__ = {p.name: p.annotation for p in parametros}
    return herramienta


def _fijado(funcion: Callable[..., Any], fijar: Mapping[str, Any]) -> Callable[..., Any]:
    """La función sin los parámetros fijados en su firma —el agente no los ve ni los puede poner— y con su valor
    inyectado en cada llamada. Un valor que es una función se llama en cada petición: así la aplicación pone el de quien
    llama sin que la base guarde nada."""
    firma = inspect.signature(funcion)
    quedan = [p for n, p in firma.parameters.items() if n not in fijar]
    if len(quedan) == len(firma.parameters):
        return funcion

    def valores() -> dict[str, Any]:
        return {n: (v() if callable(v) else v) for n, v in fijar.items() if n in firma.parameters}

    if inspect.iscoroutinefunction(funcion):
        @functools.wraps(funcion)
        async def asincrona(**argumentos: Any) -> Any:
            return await funcion(**argumentos, **valores())
        envuelta: Callable[..., Any] = asincrona
    else:
        @functools.wraps(funcion)
        def sincrona(**argumentos: Any) -> Any:
            return funcion(**argumentos, **valores())
        envuelta = sincrona
    envuelta.__signature__ = firma.replace(parameters=quedan)  # type: ignore[attr-defined]
    envuelta.__annotations__ = {n: a for n, a in getattr(funcion, "__annotations__", {}).items() if n not in fijar}
    return envuelta


def registrar(servidor: Servidor, catalogo: Catalogo, funciones: Mapping[str, Callable[..., Any] | Familia], *,
              prefijo: str = "", fijar: Mapping[str, Any] | None = None) -> list[str]:
    """Publica en `servidor` las herramientas de `catalogo`, cada una con su función —o su `familia`, si junta varias
    operaciones—, en el orden del catálogo. Devuelve los nombres publicados.

    El título y las anotaciones salen del catálogo; la descripción, de la función (o de la familia), con cada operación
    citada dicha como se alcanza por aquí. Con `prefijo`, cada herramienta lo lleva delante, y las citas también.
    """
    sobran = sorted(set(funciones) - set(catalogo.herramientas))
    faltan = sorted(set(catalogo.herramientas) - set(funciones))
    if sobran or faltan:
        raise CatalogoInvalido([f"las funciones no son las del catálogo: sobran {sobran}, faltan {faltan}"])
    publicadas = []
    for nombre, h in catalogo.herramientas.items():
        publicado = prefijo + nombre
        if not nombre_valido(publicado):
            raise CatalogoInvalido([f"`{publicado}` no vale como nombre de herramienta para Claude"])
        funcion = funciones[nombre]
        if isinstance(funcion, Familia):
            descripcion, funcion = funcion.descripcion, _la_familia(publicado, h, funcion)
        else:
            if h.tiene_modos:
                raise CatalogoInvalido([f"`{nombre}` junta {len(h.fichas)} operaciones: necesita una `familia`"])
            descripcion = funcion.__doc__ or ""
        if fijar:
            funcion = _fijado(funcion, fijar)
        servidor.add_tool(funcion, publicado, title=h.titulo or None,
                          description=catalogo.en_la_puerta(descripcion, prefijo),
                          annotations=ToolAnnotations(**h.anotaciones()))
        publicadas.append(publicado)
    servidor.declarar(catalogo, prefijo=prefijo)
    return publicadas


# --- el motor como herramientas ---------------------------------------------------------------------------------------
#
# Lo único que se declara de cada parámetro es su TIPO PYTHON, porque es de lo que el SDK deriva el `inputSchema` que ve
# el agente. El nombre, si es obligatorio y su valor por defecto NO se declaran: salen de la firma de la operación en
# `contaperu.api`, que es la misma de la que sale el esquema de la puerta HTTP. Así la pregunta «¿reciben lo mismo las
# dos puertas?» deja de tener respuesta posible.
#
# Un tipo opcional se deriva: con valor por defecto `None` es `T | None`; con cualquier otro —`False`, `""`— es `T` a
# secas, que es lo que estaba escrito a mano en las 14 firmas.
#
# **Y lo que dice cada parámetro tampoco se escribe aquí** (15.15.0): su `description`, su `enum` y su `format` salen de
# `api/tabla.PARAMETROS`, que ya los declaraba para la puerta HTTP y el contrato. Hasta entonces los 52 parámetros de las
# 18 herramientas llegaban al agente con un nombre y un tipo y nada más, mientras la puerta de al lado los describía: un
# agente tenía que adivinar qué era `correlativos` o qué valores admitía `agrupar_por`.
TIPOS: dict[str, Any] = {
    "documento": dict,
    "contenido": str,
    "libro": dict,
    "es_base64": bool,
    "driver": str,
    "configuracion": dict,
    "imputacion": dict,
    "correlativos": dict,
    "claves_previas": list[list[str | int | None]],
    "incluir_observados": bool,
    "lineas": list[dict],
    "cuentas": list[dict],
    "partidas_previas": list[dict],
    "agrupar_por": str,
    "texto": str,
    "codigo": str,
    # Dos fechas que pone quien llama, porque el motor no tiene reloj. Su `format: date` ya no se declara aquí con
    # un alias: lo dice la tabla, como el de cualquier otro parámetro.
    "fecha": str,
    "corte": str,
}

# De lo que la tabla declara de un parámetro, lo que se publica además del tipo. **No se llevan los `$ref`**: apuntan
# a los esquemas publicados por URL, y un cliente MCP no sale a buscarlos —uno estricto, además, rechazaría la
# herramienta entera por un esquema que no puede resolver—. Lo que el agente necesita de un documento está en el
# recurso `contaperu://estandar/open-accounting`, que se lee sin red.
DE_LA_TABLA = ("enum", "format")

# Los destinos, como `enum` de `driver`, contados AL ARRANCAR: son los de `drivers.DRIVERS`, que suma los de serie y
# los de terceros que haya instalados (`drivers_disponibles` los lee de ahí). Por eso no viven en la tabla: el contrato
# OpenConta es un archivo que se publica, y no puede saber qué driver de terceros tendrá instalado quien lo sirva.
# Y la lista es un `enum` del esquema y no una validación: un destino que no existe lo sigue rechazando el motor, con
# su `clave` y la lista de los que hay, en vez de un error del SDK que el agente no sabría leer.
DESTINOS: tuple[str, ...] = tuple(api.drivers_disponibles())
POR_LA_PUERTA = {"driver": {"enum": list(DESTINOS)}}


def _anotacion(nombre: str, opcional: bool) -> Any:
    """El tipo con que se publica un parámetro: el de `TIPOS`, con lo que la tabla dice de él.

    El `enum` y el `format` van en la rama del texto y no al lado del `anyOf`: en un parámetro opcional, un `enum` en
    la raíz del esquema dejaría fuera el `null` que la firma admite. La descripción va en el campo, que es donde la
    lee un cliente.
    """
    declarado = PARAMETROS[nombre]
    tipo = TIPOS[nombre]
    extra = {**{clave: declarado[clave] for clave in DE_LA_TABLA if clave in declarado}, **POR_LA_PUERTA.get(nombre, {})}
    if extra:
        tipo = Annotated[tipo, WithJsonSchema({**TypeAdapter(tipo).json_schema(), **extra})]
    if opcional:
        tipo = tipo | None
    return Annotated[tipo, Field(description=declarado["description"])]


# El nombre con que un parámetro sale por esta puerta, cuando no es el de la api. `lineas` son las líneas del
# asiento, y para un agente «asiento» dice de qué está hablando; la api lo llama por lo que es.
RENOMBRA = {"lineas": "asiento"}

# Los recursos que no sirven JSON. Un esquema se anuncia como esquema para que un cliente sepa que puede
# validar con él.
MIMES = {
    "contaperu://estandar/open-accounting": "application/schema+json",
    "contaperu://esquemas/diagnostico": "application/schema+json",
}

# El nombre de un recurso cuando no es el de su operación: los dos que se nombraron por lo que son y no por la
# función que los devuelve, y el de `drivers`, que tiene que decirlo porque su nombre choca con la herramienta.
NOMBRES_DE_RECURSO = {
    "contaperu://catalogos/pcge2026": "catalogo_pcge2026",
    "contaperu://configuracion": "configuracion_declarada",
    "contaperu://drivers": "drivers_disponibles",
}

# De qué claves del resultado sale un archivo: la que lleva los bytes en base64, la que lleva su nombre, y su
# tipo —el de una clave del resultado, o fijo—. Es lo que antes preguntaba `if op.nombre == "exportar"` en las
# dos puertas.
ARCHIVOS = (("contenido_base64", "archivo", "content_type"),
            ("zip_base64", "archivo_zip", "application/zip"))


def _firma_de(operacion: api.Operacion) -> inspect.Signature:
    """La firma con que esta puerta publica una operación: sus nombres y defaults, con el tipo de `_anotacion`."""
    parametros = []
    for p in inspect.signature(operacion.funcion).parameters.values():
        parametros.append(inspect.Parameter(RENOMBRA.get(p.name, p.name), inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                            default=p.default, annotation=_anotacion(p.name, p.default is None)))
    return inspect.Signature(parametros, return_annotation=CallToolResult)


def _llamada(operacion: api.Operacion) -> Callable[..., Any]:
    """La función que llama a la operación por la FACHADA, deshaciendo los renombres de esta puerta.

    Se resuelve `getattr(api, …)` en cada llamada y no se guarda la función: `op.funcion` apunta al módulo
    interno `api.operaciones`, y una puerta habla con `api` y nada más (`tests/test_frontera.py`). Además es
    lo que hacían las catorce escritas a mano, así que quien sustituya una operación de la fachada —la
    batería lo hace— sigue viendo el mismo efecto por esta puerta.
    """
    nombres = tuple(inspect.signature(operacion.funcion).parameters)

    def llamar(**argumentos: Any) -> Any:
        return getattr(api, operacion.nombre)(**{p: argumentos[RENOMBRA.get(p, p)] for p in nombres})
    return llamar


def _con_adjuntos(resultado: dict) -> CallToolResult:
    """El resumen en JSON y, aparte, los archivos como archivos. Rechaza por encima del tope de la llamada."""
    bytes_ = [(resultado.pop(clave, "") or "", nombre, tipo) for clave, nombre, tipo in ARCHIVOS]
    pesa = peso_de_base64(*(b for b, _, _ in bytes_))
    if pesa > MAXIMO_ARCHIVO:
        raise api.DocumentoInvalido(
            f"El archivo pesa {pesa // (1024 * 1024)} MB y el tope por llamada es "
            f"{MAXIMO_ARCHIVO // (1024 * 1024)} MB. Divide el periodo en lotes mas pequenos.")
    adjuntos = [_adjunto(resultado[nombre], b64, resultado.get(tipo) or tipo or "application/octet-stream")
                for b64, nombre, tipo in bytes_ if b64]
    resumen = TextContent(type="text", text=json.dumps(resultado, ensure_ascii=False, indent=1))
    return CallToolResult(content=[resumen, *adjuntos])


def _herramienta_de(operacion: api.Operacion) -> Callable[..., CallToolResult]:
    """Una operación como herramienta: su firma, su texto y, si devuelve un archivo, su adjunto."""
    llamar = _llamada(operacion)

    def herramienta(**argumentos: Any) -> Any:
        resultado = llamar(**argumentos)
        return _con_adjuntos(resultado) if operacion.archivo else resultado

    herramienta.__name__ = operacion.herramienta
    herramienta.__doc__ = textos.PARA_HERRAMIENTA[operacion.herramienta]
    firma = _firma_de(operacion)
    herramienta.__signature__ = firma  # type: ignore[attr-defined]
    herramienta.__annotations__ = {p.name: p.annotation for p in firma.parameters.values()}
    herramienta.__annotations__["return"] = CallToolResult
    return contesta(herramienta)


def _recurso_de(operacion: api.Operacion) -> Callable[[], str]:
    """Una operación sin argumentos como recurso. El esquema del estándar sale tal cual: son sus bytes."""
    if operacion.recurso == "contaperu://estandar/open-accounting":
        def recurso() -> str:
            return _datos.texto_del_esquema()
    else:
        def recurso() -> str:
            return json.dumps(getattr(api, operacion.nombre)(), ensure_ascii=False, indent=1)

    recurso.__name__ = NOMBRES_DE_RECURSO.get(operacion.recurso, operacion.nombre)
    recurso.__doc__ = textos.PARA_RECURSO[operacion.recurso]
    return recurso


def registrar_del_motor(servidor: Servidor, *, perfil: str = "integrador", grupos: Iterable[str] | None = None,
                        herramientas: Iterable[str] | None = None, solo_lectura: bool = False,
                        fijar: Mapping[str, Any] | None = None, prefijo: str = "contaperu_",
                        recursos: bool = True) -> list[str]:
    """Publica las herramientas del motor —y sus recursos, si `recursos`— en un servidor, el propio o el de otro.

    Lleva el prefijo `contaperu_` por defecto porque en el servidor de otro sus nombres pueden chocar con los suyos
    (`exportar` es un nombre que cualquiera tiene). Los recursos no lo llevan: su dirección `contaperu://` ya es única.
    """
    elegido = catalogo_del_motor().elegir(perfil=perfil, grupos=grupos, herramientas=herramientas,
                                          solo_lectura=solo_lectura)
    por_herramienta = {op.herramienta: op for op in api.OPERACIONES if op.herramienta}
    publicadas = registrar(servidor, elegido, {n: _herramienta_de(por_herramienta[n]) for n in elegido.herramientas},
                           prefijo=prefijo, fijar=fijar)
    if recursos:
        for op in api.OPERACIONES:
            if op.recurso:
                servidor.resource(op.recurso, mime_type=MIMES.get(op.recurso, "application/json"),
                                  name=NOMBRES_DE_RECURSO.get(op.recurso))(_recurso_de(op))
    return publicadas


def crear_servidor(*, nombre: str = "contaperu", instrucciones: str | None = None, perfil: str = "publico",
                   grupos: Iterable[str] | None = None, herramientas: Iterable[str] | None = None,
                   solo_lectura: bool = False, fijar: Mapping[str, Any] | None = None, prefijo: str = "",
                   recursos: bool = True, **del_servidor: Any) -> Servidor:
    """Un servidor nuevo con las herramientas del motor: el que sirve `contaperu-mcp`, o uno propio con lo que se elija.

    Las instrucciones son las del motor si no se dan otras, con los nombres de herramienta dichos con el prefijo. Esas
    instrucciones hablan de todas las herramientas del motor: quien elige solo algunas pasa las suyas. Lo demás va a
    `Servidor` (la guarda, lo visible, cómo se dice un error) y, a través de él, al SDK.
    """
    texto = api.INSTRUCCIONES if instrucciones is None else instrucciones
    servidor = Servidor(nombre, instrucciones=DEL_MOTOR.en_la_puerta(texto, prefijo) if prefijo else texto,
                        version=api.__version__, **del_servidor)
    registrar_del_motor(servidor, perfil=perfil, grupos=grupos, herramientas=herramientas, solo_lectura=solo_lectura,
                        fijar=fijar, prefijo=prefijo, recursos=recursos)
    return servidor


# --- el arranque --------------------------------------------------------------------------------------------------

def seguridad(dominios: Iterable[str]) -> TransportSecuritySettings:
    """Los nombres de host por los que este servidor acepta que le llamen.

    El SDK rechaza con un 421 cualquier peticion cuyo `Host` no reconozca. Es la defensa
    contra el *DNS rebinding*: una pagina cualquiera hace que el navegador de la victima
    resuelva un dominio suyo a la direccion del servidor y le hable como si fuera del mismo
    origen. Por eso publicarlo detras de un proxy obliga a decir el nombre publico: sin
    `--dominio`, el servidor solo se reconoce a si mismo como «localhost» y desde fuera todo
    da 421 aunque el proxy y el certificado esten perfectos.
    """
    dominios = list(dominios)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts_permitidos(dominios),
        allowed_origins=origenes_permitidos(dominios),
    )


def servir(servidor: MCPServer, *, transporte: str = "stdio", host: str = "127.0.0.1", puerto: int = 8000,
           dominios: Iterable[str] = ()) -> None:
    """Arranca el servidor por entrada y salida estándar (`stdio`) o por HTTP (`http`, que es Streamable HTTP).

    Por HTTP, sin sesiones: cada peticion se atiende sola y el servidor no guarda nada entre una y otra, que es lo que
    esta base dice de si misma. Ademas quita de en medio el unico recurso que un desconocido podria ir acumulando en un
    servidor sin autenticacion: sesiones abiertas (el SDK admite 10.000 y las mantiene media hora). Solo vale para los
    clientes que hablan la especificacion 2025: con la 2026-07-28 no hay sesion que abrir.
    """
    if transporte != "http":
        servidor.run(transport="stdio")
        return
    dominios = list(dominios)
    if not dominios and host not in ("127.0.0.1", "localhost", "::1"):
        print("aviso: sin --dominio solo se atienden peticiones cuyo Host sea localhost; "
              "desde fuera responde 421. Al publicarlo detras de un proxy hay que declarar "
              "el nombre publico:  --dominio contaperu.ejemplo.com", file=sys.stderr)
    servidor.run(transport="streamable-http", host=host, port=puerto, stateless_http=True,
                 transport_security=seguridad(dominios))
