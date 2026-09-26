# Integrar ContaPerú en un ERP

ContaPerú convierte comprobantes de SUNAT en asientos y en los archivos que importan los sistemas contables peruanos,
sin estado: todo entra por parámetro y sale por retorno. Esta guía es para quien construye un ERP, un portal contable o
un agente y quiere usarlo. Dice qué puerta elegir, cómo se llama cada una y qué promete la 1.x. Los ejemplos se
ejecutan en la batería del repositorio (`tests/test_integrar.py`): si uno deja de funcionar, la batería falla.

## Qué puerta elegir

| Si tu sistema… | Usa | Instala |
|---|---|---|
| está escrito en Python (Odoo, Frappe, un servicio propio) | la librería, `contaperu.api` | `contaperu[excel]` |
| procesa lotes de archivos sin programar | la línea de comandos, `contaperu` | `contaperu[excel]` |
| es un agente de IA o un cliente MCP | el servidor MCP, `contaperu-mcp` | `contaperu[mcp,excel]` |
| está escrito en otro lenguaje | la puerta HTTP, `contaperu-http`, con el contrato OpenConta | `contaperu[http,excel]` o la imagen de Docker |

Las cuatro dan lo mismo: son adaptadores de la misma api, y un test comprueba que el mismo XML da el mismo documento y
el mismo mes, el mismo diagnóstico, por cualquiera de ellas.

## Lo que entra y lo que sale

Entra un **documento `open-accounting` 1.0** (`estandar/LEEME.md`): la cabecera del libro (RUC, periodo, ventas o
compras) y los comprobantes tal como los emite SUNAT, con los importes en positivo y como texto exacto. Si tienes los
XML o la propuesta del SIRE, el motor arma el documento por ti (`leer_xml`, `leer_propuesta_sire`).

Aparte del documento llegan dos cosas que son de tu aplicación y no del comprobante:

- **La configuración contable** de cada empresa: lo general en la raíz y una sección por sistema. `describir_configuracion`
  dice qué se configura, para pintar la pantalla, y `configuracion_por_defecto` da un punto de partida. **Pásale el
  `driver` cuando ya sepas a qué sistema exporta esa empresa**: las cuentas de fábrica son las del PCGE a seis
  dígitos, y un sistema que numera de otra forma declara las suyas (`contrato.cuentas_por_defecto`). Sembrar la de
  todos le da a un contribuyente de STARSOFT las cuentas de CONCAR.
- **La imputación** de cada documento, por su `id_externo`: la cuenta, el centro de costo, la cuenta del total o un
  reparto de la base. Lo que no traiga sale de la configuración.

El camino normal es siempre el mismo: **`diagnosticar` antes de `exportar`**. El diagnóstico dice si el mes está listo
para ese destino y, si no, qué falta y a quién pedírselo (`pedir_a`: el contador o el sistema).

## Desde Python

```python
import json
from pathlib import Path

from contaperu import api

documento = json.loads(Path("tests/fixtures/golden/compras_202601.json").read_text(encoding="utf-8"))
configuracion = {"usa_centros_costo": False}
# La cuenta de cada comprobante es SUYA y llega por su `id_externo`: la configuración no la suple (3.0).
imputacion = {c.setdefault("id_externo", f"fila-{n}"): {"cuenta_contable": "659999"}
              for n, c in enumerate(documento["comprobantes"], 1)}

diagnostico = api.diagnosticar(documento, driver="concar", configuracion=configuracion, imputacion=imputacion)
for falta in diagnostico["que_falta"]:
    print(falta["pedir_a"], "·", falta["texto"], falta["comprobantes"])

if diagnostico["listo_para_exportar"]:
    archivo = api.exportar_archivo(documento, driver="concar", configuracion=configuracion,
                                   imputacion=imputacion)
    print(archivo.archivo, len(archivo.contenido), "bytes")      # el .xlsx, listo para escribir o servir
```

Cada función recibe el documento primero y todo lo demás por su nombre; las que van hacia un sistema piden `driver`,
sin valor por defecto. Los que hay los dice `api.drivers_disponibles()`.

### Si haces tu propio pre-vuelo

`diagnosticar` responde «qué falta» de una vez, y para la mayoría es suficiente. Pero si tu aplicación tiene una
pantalla de revisión y quiere decidir por su cuenta —marcar la fila a la que le falta el centro de costo, enseñar en
gris la cuenta que se usará, calcular el correlativo sugerido de cada sub-diario—, vas a llamar a las funciones del
paquete `asiento`, y **todas reciben la configuración ya aplicada**:

```python
from contaperu import asiento
from contaperu.modelo import Comprobante

config = api.config_aplicada(configuracion, driver="concar", documento=documento)   # desde la 1.2
comprobantes = [Comprobante.de_dict(c) for c in documento["comprobantes"]]

faltan = asiento.faltantes_para(comprobantes, config, es_venta=False, exige=("cuenta_contable",))
print(sorted(faltan))                                     # ['sin_cuenta'] si nadie eligió la cuenta
print(asiento.sub_diario(comprobantes[0], config))        # el sub-diario que llevará esa fila
print(asiento.cuenta_tercero(comprobantes[0], config))    # la cuenta del total que usará el archivo
```

**Es la misma configuración con la que se genera**, no una aproximación: la arman las dos las operaciones por dentro.
La diferencia con `configuracion_por_defecto` importa y no se ve a simple vista — esa da la forma en que se
**guarda**, anidada por sistema, y `config_aplicada` la forma con la que se **genera**, plana y con la sección de tu
sistema fundida en la raíz. Pasarle la guardada a `asiento.sub_diario` no falla: devuelve vacío.

La imputación va dentro (por el `documento` o por `imputacion=`), con las mismas comprobaciones que al exportar. Y una
imputación exige el documento: sin los comprobantes no hay contra qué casar sus llaves.

### Reconocer lo que ya exportaste

El Excel de CONCAR se suma al importarlo: la misma tanda importada dos veces duplica los asientos. Cada exportación
trae con qué reconocerla, y la identidad de cada comprobante —el RUC y el tipo del libro, el tipo, la serie y el número
sin ceros, y en compras el proveedor— es la clave con que tu aplicación evita repetir un envío.

```python
resultado = api.exportar(documento, driver="concar", configuracion=configuracion, imputacion=imputacion,
                         fecha="2026-09-14")
exportacion = resultado["_exportacion"]
print("tanda", exportacion["huella"], "motor", exportacion["motor"])
for comprobante in exportacion["comprobantes"]:
    print(comprobante["identidad"]["serie"], comprobante["identidad"]["numero"], comprobante["huella"])

# Lo ya anotado en otros periodos del mismo RUC: lo que coincide no se exporta (SUNAT lo rechazaría).
ya_anotados = [["01", "F001", "0000123", "20601234567"]]
revisado = api.revisar(documento, claves_previas=ya_anotados)
print(revisado["_revision"])
```

### Cuando el motor se niega

Todo rechazo es un `api.ErrorContaperu` con una `clave` estable, que es lo que conviene comparar en vez del texto.
`api.problema(error)` lo da como «problem details» del RFC 9457, igual que la puerta HTTP.

```python
try:
    api.exportar(documento, driver="concar", configuracion={}, imputacion=imputacion)
except api.ErrorContaperu as error:
    print(error.clave, "·", api.problema(error)["detail"])          # sin_centro · 3 comprobante(s) sin centro…
```

## Por lotes, con la línea de comandos

```bash
contaperu generar --tipo compra --ruc 20601234567 --razon "EMPRESA DE PRUEBA SAC" --periodo 202601 --driver sire --salida salida comprobantes/*.xml
contaperu diagnosticar mes.json --driver concar --config config.json --imputacion imputacion.json --claves-previas previas.json
contaperu desde-json mes.json --driver concar --config config.json --imputacion imputacion.json --salida salida
contaperu configuracion --driver concar --por-defecto
```

Un código de salida distinto de cero dice que algo no se generó, y el motivo va en la salida de error, sin traceback.

## Desde cualquier lenguaje, por HTTP

```bash
contaperu-http --host 127.0.0.1 --puerto 8080
curl -s http://localhost:8080/openconta.json -o openconta.json
curl -s -X POST http://localhost:8080/v1/diagnosticar -H "Content-Type: application/json" -d @peticion.json
```

`/openconta.json` es el contrato, en formato OpenAPI 3.1: cada operación con su cuerpo, su respuesta y sus rechazos.
Cualquier generador que lea OpenAPI 3.1 arma el cliente de tu lenguaje a partir de él. El cuerpo de una petición lleva
los mismos nombres que los parámetros de la api:

```json
{
  "documento": {
    "open_accounting": "1.0",
    "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202601", "tipo": "compra"},
    "comprobantes": [{
      "tipo_cp": "01", "serie": "F001", "numero": "123", "fecha_emision": "2026-01-15",
      "contraparte_tipo_doc": "6", "contraparte_doc": "20131312955", "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
      "base_gravada": "100.00", "igv": "18.00", "total": "118.00", "id_externo": "fila-1"
    }]
  },
  "driver": "csv",
  "configuracion": {"usa_centros_costo": false},
  "imputacion": {"fila-1": {"cuenta_contable": "636301"}}
}
```

Lo que conviene saber antes de publicarla:

- **Sin estado y sin autenticación**: no guarda nada de nadie. Si hace falta autenticar, lo hace el proxy que la
  publica. No responde a peticiones de un navegador de otro origen (sin CORS).
- **El `Host` se comprueba**: detrás de un proxy hay que declarar el nombre público con `--dominio`; si no, responde
  421. Es la defensa contra el DNS rebinding, la misma del servidor MCP.
- **Los rechazos** son `application/problem+json`: 400 si el cuerpo no es un objeto JSON, 413 si pasa de 10 MiB, 422 si
  el motor no puede hacerlo (con la `clave` del error) o los parámetros no cuadran, y 500 sin detalle. El archivo que
  devuelve `exportar` tiene un tope de 4 MiB: un periodo más grande se divide en lotes.
- **Las conexiones también tienen tope.** Atiende a lo sumo 16 peticiones a la vez (503 si llegan más) y cierra a los 5
  segundos una conexión inactiva. El tiempo máximo para leer una petición lenta lo pone el proxy, porque uvicorn no lo
  tiene: en Caddy, las opciones globales `servers { timeouts { read_header 10s read_body 30s } }`.
- Con Docker: `docker run --rm -p 8080:8080 contaperu-mcp contaperu-http --host 0.0.0.0 --dominio contaperu.ejemplo.com`.

## Para un agente de IA, por MCP

Un cliente MCP local lo arranca por entrada y salida estándar; uno remoto, por Streamable HTTP
(`contaperu-mcp --transporte http --dominio …`). Las catorce herramientas se anuncian de solo lectura y sin salir a la red,
y sus nombres son los de siempre: `diagnosticar`, `exportar`, `generar_asiento`, `validar_comprobantes`… Cómo
conectarlo a Claude está en el `README.md`.

### Tu propio MCP con el del motor debajo

Si tu ERP quiere su capa de agente —que configure, saque reportes, analice tus datos o cargue una factura—, **eso no
va aquí**. Lo que decide dónde va cada herramienta es una sola pregunta: **¿necesita TUS datos?**

| Herramienta | ¿Tus datos? | De quién es |
|---|---|---|
| Qué se configura y con qué valores se parte | No | **del motor** — `configuracion_por_defecto`, y el recurso `contaperu://configuracion` |
| Guardar la configuración de un RUC | Sí | **tuya** |
| **Reportes sobre TUS filas**: qué meses hay, qué entró en la subida de las 11:19, un histórico | Sí | **tuya.** El motor no tiene ni una fila: no las busca, no las guarda y no sabe cuáles hay |
| **Sumar, agrupar o cuadrar un documento que LE DAS** | No | **del motor** — `resumen`, `por_cuenta`, `cuadrar`. El dato entra en la llamada y sale en la llamada |
| Leer un XML de SUNAT | No | **del motor** — `leer_xml_ubl` |
| Leer un PDF o una foto con un modelo | Sí (red y una clave) | **tuya.** El motor no sale a la red, y eso lo vigila un test |
| Guardar la factura | Sí | **tuya** |

Las del motor son puras: reciben todo lo que necesitan y devuelven todo lo que producen. Las tuyas necesitan tu base
de datos y tu sesión. **Son dos capas, no una**, y juntarlas obligaría al motor a tener estado.

**Elegir las filas es tuyo; la aritmética de un libro, no** (3.4.0). La fila de los reportes decía «tuya» a secas, y
metía en el mismo saco dos cosas distintas: qué mes, qué registro y qué filtro solo lo sabes tú, pero que una nota de
crédito reste, que dos monedas no se sumen, que una excluida no cuente y que las líneas se agrupen por cuenta es
contabilidad. Hasta la 3.3 el motor no la tenía, así que la escribía cada aplicación — y a la primera que lo hizo le
salió con el `07` donde el motor dice `("07", "87")`: una nota de crédito de no domiciliado le **sumaba** en vez de
restarle, y el total cuadraba con su propia tabla.

Dos formas de combinarlas, y la primera no cuesta nada:

1. **Dos servidores.** Un cliente MCP se conecta a varios: el tuyo y `contaperu-mcp` al lado. Cero trabajo.
2. **Uno solo**, delegando en la api las que son del motor:

```python
from mcp.server.fastmcp import FastMCP

from contaperu import api
from contaperu.puertas.servidor_mcp import INSTRUCCIONES

mio = FastMCP("mi-erp", instructions=INSTRUCCIONES)


@mio.tool()
def mis_meses(ruc: str) -> dict:
    """Los meses de ese RUC. Esta es TUYA: necesita tu base de datos."""
    return {"ruc": ruc, "meses": ["202601"]}


@mio.tool()
def diagnosticar(documento: dict, driver: str) -> dict:
    """Y esta delega en el motor, que es quien sabe si el mes está listo."""
    return api.diagnosticar(documento, driver=driver)


print(f"servidor con las tuyas y las del motor: {mio.name}")
```

**Trae `INSTRUCCIONES`, aunque no traigas nada más.** Es lo que el servidor del motor le dice al agente antes de que
toque nada —que los importes van siempre en positivo, que `tipo_cp` es el código de la Tabla 10 y no la sigla del
sistema, que la retención del IGV del 3 % **no** es una detracción—, y está en el `__all__` a propósito. Sin eso, un
modelo se inventa detracciones con mucha seguridad.

Y si prefieres una sola instancia sin reescribir nada, `contaperu.puertas.servidor_mcp.mcp` es importable y le puedes
añadir tus herramientas con `@mcp.tool()`. Funciona, pero estás mutando la instancia del motor: queda a tu cargo.

## ¿Te hace falta un driver? Casi seguro que no

Antes de escribir nada, mira cuál de estos tres eres. Solo el tercero pide código.

| | Qué necesitas | ¿Driver? |
|---|---|---|
| **1** | Leer asientos que otro armó | **No.** Te basta el esquema; ni siquiera instalas el paquete |
| **2** | Que el motor te dé el asiento, en el estándar | **No.** `exportar(documento, driver="asiento_neutral")` y ya |
| **3** | Que el motor escriba **tu formato propio** | **Sí**, y va en tu paquete, sin pasar por aquí |

**Un driver existe para traducir a un formato que no podemos cambiar** — el Excel que importa un CONCAR instalado, el
TXT que pide SUNAT. Un sistema que puede adoptar el estándar no tiene nada que traducir: el estándar ya es su
formato, y para eso está el driver `asiento_neutral`. Si escribes un driver que no te hacía falta, has creado un
traductor más que mantener.

Y el canal lo dice del formato, no de la edad del software: si tu importador pide siglas y correlativos es `legacy`
aunque el sistema sea de este año, y si acepta las líneas del estándar es `intercambio`, que el motor presenta en su
grupo `erp`.

## Un driver para tu sistema contable

Esto es el nivel 3: tu sistema importa un archivo con una forma suya. El contrato está en
`contaperu/drivers/contrato.py` y la guía paso a paso, en `CONTRIBUTING.md`. Lo esencial:

- **Declara a quién entrega** (`CANAL`): `legacy` si es un sistema contable instalado que importa un archivo,
  `tributario` si es un registro que se presenta a SUNAT, `intercambio` si es un formato neutral. El motor lo presenta
  en uno de sus tres grupos de destinos —SIRE, Legacy o ERP— y `drivers_disponibles` dice el de cada driver.
- **Compruébalo antes de registrarlo**: `contaperu verificar-driver mi_paquete.mi_driver` dice si cumple el contrato y
  qué le falta (desde Python, `api.verificar_driver`).
- **Un driver de asientos recibe las líneas ya armadas** (`desde_lineas`), numeradas y cuadradas, con el índice de cada
  comprobante y su cabecera. Solo traduce: no puede equivocarse en una cuenta ni en un sentido.
- **Dos niveles.** *De serie*, dentro de este repositorio, con un archivo real que ese ERP haya aceptado. *Comunidad*,
  en un paquete tuyo que se registra por el grupo de entry points `contaperu.drivers`, sin esperar a nadie.
- **Si tu ERP tiene una API moderna** en vez de un archivo, escribir en ella es un hito reservado (canal `api_erp`, A5
  de la hoja de ruta). Mientras tanto, tu aplicación pide el asiento a `generar_asiento` con `driver="asiento_neutral"` —las líneas del
  estándar, sin siglas, sub-diarios ni correlativos de ningún sistema legacy— y lo envía; el envío y los
  reintentos son suyos, con la identidad y la huella de cada comprobante como clave para no repetir.

## Si NO usas el motor: construir sobre el estándar

Todo lo de arriba supone que llamas a `contaperu`. No hace falta: `open-accounting` es un estándar publicado y
puedes construir sobre él, en el lenguaje que sea. Esta sección es para eso, y es el espejo de la anterior —allí se
escribe un driver contra el contrato del motor; aquí se lee el documento contra el contrato del estándar—.

**Qué recibes.** El documento que produce el driver `asiento_neutral` tiene cuatro claves:

```json
{
  "open_accounting": "1.0",
  "libro": {"ruc": "…", "razon_social": "…", "periodo": "202601", "tipo": "compra"},
  "asiento": [{"cuenta": "631101", "debe_haber": "D", "importe": "1000.00", "clase": "gasto", "rol": "principal"}],
  "_exportacion": {"driver": "asiento_neutral", "motor": "3.1.0", "huella": "…", "comprobantes": [{"…"}]}
}
```

**Qué te garantiza, y es lo que ahorra el trabajo:** las cuentas ya están decididas, el asiento **cuadra** —el motor
se niega a producirlo si no— y el orden de las líneas es estable. Cada línea dice qué es por su `rol` y trae el
código SUNAT de su documento, no la sigla de ningún sistema.

**Cómo lo enlazas con lo tuyo.** Por dos vías, y conviene usar las dos:

- `linea.documento.id_externo` — el identificador que pusiste tú en el comprobante, en cada línea suya.
- `_exportacion.comprobantes` — por comprobante, su identidad, el tramo `[desde, hasta)` de líneas que le toca y la
  huella de ese tramo. **Esa huella es la clave para no repetir**: si la de un comprobante no cambió, es el mismo
  asiento que ya importaste. Los tramos parten las líneas sin dejar hueco ni solaparse.

**Qué NO lleva, y por qué.** Ni `fecha` de exportación ni nombre de archivo: no son hechos del asiento, y quien
llama al API los recibe en su respuesta. Tampoco sub-diarios ni correlativos: son vocabulario de un sistema legacy y
el documento neutral no los tiene (`sub_diarios` sale vacío a propósito). Y una línea **no lleva las claves que
están vacías**: cuenta con que el juego de campos varíe de una a otra.

**Cómo compruebas lo que produces**, sin escribirle a nadie:

```bash
contaperu verificar-documento mi-documento.json
```

Dice si es conforme con el esquema y, aparte, los **avisos** de lo que el esquema no puede decir porque vive en los
catálogos: un `rol` que no conoces se lee igual —el rol solo dice qué es esa línea—, pero un `tipo` de libro que no
conoces sí rompe, porque de él dependen las columnas de cada registro. Desde Python es `api.verificar_documento`.

Y si tu implementación es de otro lenguaje, los casos están publicados: `estandar/conformidad/esquema.json` son 24
casos con la forma de la *JSON Schema Test Suite*, que corres con cualquier validador de draft 2020-12 y sin el
motor. Viajan dentro del paquete, así que `pip install contaperu` te los deja en
`contaperu/estandar/conformidad/`. Los de `diagnosticar.json` **no son portables**: comprueban este motor, no el
tuyo.

## El SIRE, de punta a punta

El motor **no se conecta a SUNAT** —no hay credenciales, no sale ni un paquete a la red, y sus propios tests
lo impiden—, pero sí te da todo lo demás. Esto es lo que hace falta saber, y es lo que más caro cuesta
descubrir a base de rechazos.

**1. El archivo lo generas con `exportar`.** El TXT va dentro de un ZIP, y los dos nombres los pone el motor:

```python
from contaperu import api
from contaperu.drivers import sire
from contaperu.modelo import Libro

exp = api.exportar_archivo(documento, driver="sire")
exp.contenido        # bytes del ZIP: esto es lo que se sube
exp.archivo          # «LE20601234567202512000804000211 12.zip»
exp.texto            # bytes del TXT, por si lo quieres mirar
exp.nombre           # el .TXT — es el que SUNAT espera en la metadata de la subida
```

**2. El nombre lo impone SUNAT y no se toca.** Tablas 6 y 13: con otro nombre, el SIRE rechaza el archivo. Y
es el único driver que no usa el nombre genérico del kit, a propósito — `comparar_sire` deduce del propio
nombre si un archivo es de ventas o de compras. Si necesitas el nombre **antes** de generar nada (para
comprobar si ya lo enviaste), `sire.nombre(Libro(ruc=..., razon_social=..., periodo=..., tipo=...))` te lo da.

**3. Ese nombre es tu idempotencia.** SUNAT responde **1024 — «el archivo fue previamente enviado»** cuando
repites un nombre, y ese es el único mecanismo que ofrece para no duplicar. Trátalo como «ya entró», no como
un fallo. Ojo: el código viene dentro de `errors[]`, no en el `cod` de arriba, que es un «422» genérico.

**4. El ZIP es reproducible.** Dos exportaciones iguales dan los mismos bytes (la entrada del ZIP lleva fecha
fija), así que puedes comparar por hash antes de reenviar.

**5. El SIRE no lleva huella.** `_exportacion` no trae `huella` porque un registro tributario no tiene
asiento. Si esperabas la huella para deduplicar, usa el nombre del archivo o la identidad de los
comprobantes.

**6. Antes de subir, compara.** `api.comparar_sire(nuestro, de_sunat, registro="compra")` contrasta tu TXT
contra la exportación del detalle que devuelve SUNAT, campo a campo. Pasa `registro=` explícito si el archivo
que bajaste por API no conserva el `1404`/`0804` en el nombre.

**7. Y lo que ya devolvió SUNAT, el motor lo lee.** `api.leer_propuesta_sire(contenido, libro,
es_base64=True)` acepta el TXT o el ZIP tal cual, con cabecera o sin ella, y **mira el contenido y no el
nombre**: da igual cómo se llame lo que te bajes.

### Dónde acaba el motor y empieza tu conector

Subir el archivo, pedir un token, sondear un ticket y guardar credenciales es **tuyo**: necesita red, estado
y la Clave SOL de un contribuyente, y nada de eso entra aquí. Lo que sí te damos es el mapa del canal, para
que no tengas que reunirlo desde dos manuales que se contradicen entre sí:

```python
api.catalogos_api_sire()     # GET /v1/catalogos/sire-api · contaperu://catalogos/sire-api
```

Trae los dos caminos de OAuth (el del SIRE pide Clave SOL, el de la consulta de validez no), las rutas **por
libro** —RVIE y RCE no comparten casi ninguna, y cruzarlas devuelve **500 de nginx** y no 404—, los
parámetros obligatorios de cada una, la metadata de TUS, los estados del ticket y los códigos de retorno,
cada bloque con su fuente y su fecha.

Tres avisos que te ahorrarán una tarde:

- **`codTipoArchivo` significa cosas distintas en cada libro.** Compras dice `1=csv`; ventas dice `1=excel`.
  No es una errata de esta tabla: está así en los dos PDF de SUNAT.
- **No hay ambiente de pruebas.** El `e-beta` es solo para XML de comprobantes. Toda prueba del SIRE es
  contra producción con un RUC real, así que empieza por las lecturas, que son idempotentes.
- **«Generar el registro» no existe por API** (RS 000040-2022 art. 8.3): esa opción solo se alcanza entrando
  por SOL y la pulsa una persona. El techo de tu integración es dejar el mes en preliminar. Dilo en tu
  producto desde el primer día, para que nadie espere un botón que no puede existir.

## Versiones: fija la tuya y actualiza cuando decidas

ContaPerú publica versiones con número (SemVer): una de parche arregla, una menor añade sin romper y solo una mayor
rompe. Cada una sale de un tag `vX.Y.Z` como Release de GitHub, con la rueda, el sdist y sus sumas SHA-256, y un commit
en `main` no le llega a nadie hasta que se publica. Tu aplicación **fija una versión exacta** y la cambia cuando
decide, después de leer qué trae.

- **Desde Python**, la versión exacta, desde PyPI:

  ```bash
  pip install "contaperu[excel]==X.Y.Z"
  ```

  Con `==` basta: una versión publicada en PyPI no se reemplaza jamás, así que el número ya significa «estos bytes
  exactos». Con su hash en tu archivo de dependencias, Dependabot o Renovate te abren la actualización. Si prefieres
  no pasar por PyPI, cada Release lleva su rueda y sus `SHA256SUMS` (`sha256sum -c SHA256SUMS --ignore-missing`).
- **Por HTTP**, la ruta `/v1/` no cambia durante la 1.x, y `info.version` de `/openconta.json` dice qué versión
  responde. Si usas la imagen de Docker, por su tag exacto, nunca `latest`.
- **Por MCP**, el servidor anuncia su versión al conectarse (`serverInfo`).

Para actualizar:

1. Lee la Release de la versión nueva: su parte del CHANGELOG y, si hay algo que adaptar, su «Cómo migrar».
2. Instálala en una rama tuya y corre tus pruebas, convirtiendo también en error lo que se va a retirar:

   ```bash
   pytest -W error::contaperu._obsoleto.RutaObsoleta
   ```

3. Cuando pasen, cambia la versión fijada y despliega.

Antes de una versión mayor sale una pre-release (`vX.Y.ZrcN`) para probarla así, sin desplegar. Los arreglos de
seguridad llegan solo a la última versión publicada (`SECURITY.md`).

## Lo que promete la 2.x

- **`contaperu.api` no cambia de nombre ni de firma** hasta la 3.0 (`tests/test_superficie_publica.py`). Pueden llegar
  parámetros opcionales, claves nuevas en las respuestas y anotaciones `_*`; nunca irse.
- **OpenConta crece sin romper**: una ruta o un campo que está, sigue.
- **La 2.0 retiró las rutas de la 0.10** (`contaperu.operaciones`, `contaperu.generar`, `contaperu.cli`,
  `contaperu.servidor_mcp`, `contaperu.formato` y `drivers.concar.construir`). **Quien integró con la 1.x no cambia
  una línea**: la superficie pública de la 1.0 sigue entera y su test pasa sin regenerarse. Lo que desapareció es lo
  que ninguna versión publicada llegó a ofrecer — la 0.x nunca estuvo en PyPI.
- **El estándar es `open-accounting` 1.0**, y eso es un compromiso: nada de lo que existe se quita ni cambia de
  significado hasta una 2.0. Un valor nuevo de catálogo y un bloque opcional no suben la versión; los catálogos
  se leen de [`estandar/catalogos.json`](estandar/catalogos.json) y **un `rol` que no conozcas se contabiliza con
  `clase`, `debe_haber` e `importe`**. Si vienes de la 0.3, que el motor ya no acepta:
  [`estandar/MIGRAR-A-1.0.md`](estandar/MIGRAR-A-1.0.md).
