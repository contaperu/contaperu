# Integrar ContaPerú en un ERP

ContaPerú convierte comprobantes de SUNAT en asientos y en los archivos que importan los sistemas contables peruanos,
sin estado: todo entra por parámetro y sale por retorno. Esta guía es para quien construye un ERP, un portal contable o
un agente y quiere usarlo. Dice qué puerta elegir, cómo se llama cada una y qué promete la 13.x. Los ejemplos se
ejecutan en la batería del repositorio (`tests/test_integrar.py`): si uno deja de funcionar, la batería falla.

**Lo que se integra no es un conversor, es una base.** El motor no está hecho para que tu ERP exporte a CONCAR y ahí
acabe: está hecho para que **no tengas que escribir la contabilidad peruana**. El IGV y sus destinos, las
detracciones en sus dos tiempos, los sub-diarios, la validación contra las reglas de SUNAT, los catálogos oficiales
con su fuente y la partida doble sin tolerancia ya están, con un test por regla y la norma citada al lado de cada
una. Tu ERP pone lo que es suyo —la pantalla, los usuarios, la base de datos, el periodo y su cierre— y recibe lo
demás resuelto. La capa hacia los sistemas que ya existen sigue ahí, intacta, para quien la necesite.

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

Entra un **documento `open-accounting` 3.3** (`estandar/LEEME.md`): la cabecera del libro (RUC, periodo, ventas o
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

## Quién aporta cada variable, y cómo añades las tuyas

Todo dato tiene un dueño, y saber cuál es responde la pregunta que llega siempre: «¿dónde meto lo mío?». Son cuatro
sitios, y **solo dos aceptan variables que el motor no conoce**:

| Lo que añades | Dónde va | ¿Caben las tuyas? |
|---|---|---|
| Un hecho del comprobante | el documento | **No.** Una clave que el estándar no conoce se rechaza en vez de ignorarse: un dato que se cuela sin error es un dato que se pierde sin aviso |
| La decisión contable de un documento | `imputaciones`, o el argumento `imputacion` | **No.** Cuatro campos exactos: `cuenta_contable`, `centro_costo`, `cuenta_tercero` y `reparto`. Un quinto no se ignora, se rechaza |
| El vocabulario de tu sistema contable | tu sección de la configuración | **Sí, libres.** Tu driver declara sus campos con tipo, patrón y ayuda; el motor los valida y `describir_configuracion` los pinta |
| Lo que el motor no entiende | `datos_originales` del comprobante, y las claves `_` de la raíz | **Sí, pero solo viajan.** Se transportan sin interpretar, y ningún driver las lee |

**La imputación está cerrada a propósito.** Sus campos son las decisiones que un contador toma sobre **un
comprobante** —la cuenta, el centro, la del tercero, el código de la detracción, si una nota la anuló, y el reparto
cuando la base se parte— y son pocas porque el motor **resuelve la cuenta una sola vez para todos los drivers**
(`asiento.partes_de`, `asiento.cuenta_tercero`): la que decide tu Revisión sale igual en el Excel de CONCAR y en la
columna de un sistema que importa registros. Si el objeto fuera libre, dos aplicaciones llamarían distinto a lo mismo y
esa resolución única dejaría de existir.

**Y hay una segunda imputación, la de un movimiento de tesorería**, en su propio bloque y con sus propios campos:
`imputaciones_de_movimientos`. Es un bloque aparte y no una extensión del anterior porque tu ERP tiene secuencias
de id independientes para sus facturas y sus movimientos —el mismo `id_externo` puede ser las dos cosas— y porque
un movimiento no tiene base, ni IGV, ni nota de crédito que lo anule. Está en «El dinero», más abajo.

**Lo que es de tu sistema va en tu sección**, y se configura **por contribuyente, no por comprobante**: así viven el
medio de pago de CONTASIS, el código de área de la detracción de CONCAR y sus códigos de moneda. La prueba para saber
si un dato es configuración es esa: si cambia de un comprobante a otro, no lo es.

**Si te falta de verdad un dato por comprobante**, hay dos caminos y ninguno es un campo libre:

- **Es un hecho del comprobante** —algo que SUNAT informa o que el documento dice—: entra en el estándar, con su
  fuente y su enmienda. No es un trámite raro: en septiembre de 2026 entraron así `tipo_nota` y `estado_sunat`
  (columnas que la propuesta del SIRE ya traía y se descartaban al leer), `dscto_otros` y `medio_pago`. Lo que se
  pide es el archivo real que lo trae.
- **Es una dimensión analítica tuya** —obra, proyecto, área, presupuesto— más allá del centro de costo: **el nombre
  ya está reservado**. Es `dimensiones`, `[{tipo, codigo}]`, con el centro de costo como la primera, y va **en la
  imputación y no en el documento**, porque es una decisión de cada entorno y no un hecho del comprobante. Está
  esperando un caso real; cuando lo tengas, es lo que hay que traer.

Mientras uno de los dos llegue, `datos_originales` transporta el dato sin perderlo.

**Y las variables del SIRE no son el modelo.** El motor lee las 40 columnas del RVIE y las 41 del RCE, tipa como
campos del documento las que son hechos y guarda la fila entera en `datos_originales`; de ahí en adelante nadie
vuelve a mirar el TXT. Tu driver no lee columnas del SIRE: lee el documento, o las líneas de diario que el núcleo
armó con él. Por eso, el día que SUNAT cambie una columna, cambian el lector y el driver `sire`, y ningún driver de
asientos se entera.

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
    # El nombre NO dice a qué sistema va: desde la 6.0, CONCAR y CONTASIS escriben los dos
    # `COMPRAS_<periodo>_<RUC>.xlsx`. Si guardas los dos, el driver lo pone quien llama, no el nombre.
    print(archivo.driver, archivo.archivo, len(archivo.contenido), "bytes")   # listo para escribir o servir
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
from contaperu.modelo import Comprobante, Libro

config = api.config_aplicada(configuracion, driver="concar", documento=documento)   # desde la 1.2
comprobantes = [Comprobante.de_dict(c) for c in documento["comprobantes"]]
libro = Libro.de_dict(documento["libro"]).rasgos          # desde la 9.0: los rasgos, no un booleano

faltan = asiento.faltantes_para(comprobantes, config, libro, exige=("cuenta_contable",))
print(sorted(faltan))                                     # ['sin_cuenta'] si nadie eligió la cuenta
print(asiento.sub_diario(comprobantes[0], config, libro))  # el sub-diario que llevará esa fila
print(asiento.cuenta_tercero(comprobantes[0], config, libro))  # la cuenta del total que usará el archivo
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
    "open_accounting": "3.3",
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
(`contaperu-mcp --transporte http --dominio …`). Las diecisiete herramientas se anuncian de solo lectura y sin salir a la red,
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

## El dinero: registrar movimientos bancarios

Un libro de tipo `tesoreria` tiene **una sola entrada**, igual que una compra o una venta tienen `comprobantes[]`:
el bloque `movimientos[]`. Venga de una línea de un extracto o de una constancia de pago, al motor llega con la
misma forma, y lo que dice de dónde salió es su `origen`.

```json
{
  "open_accounting": "3.3",
  "libro": { "ruc": "20601234567", "periodo": "202608", "tipo": "tesoreria" },

  "extractos": [
    { "cuenta": "bbva-soles", "desde": "2026-08-01", "hasta": "2026-08-31",
      "saldo_inicial": "1000.00", "saldo_final": "1299.80",
      "total_cargos": "200.20", "total_abonos": "500.00" }
  ],

  "movimientos": [
    { "id_externo": "mov-881", "cuenta": "bbva-soles", "fecha": "2026-08-05",
      "descripcion": "ABONO POR TRANSFERENCIA", "importe": "500.00", "sentido": "abono",
      "moneda": "PEN", "saldo": "1500.00", "referencia": "000001", "origen": "archivo" },

    { "id_externo": "mov-882", "cuenta": "bbva-soles", "fecha": "2026-08-14",
      "descripcion": "PAGO DETRACCION", "importe": "200.00", "sentido": "cargo",
      "moneda": "PEN", "saldo": "1299.80", "referencia": "000002", "itf": "0.20",
      "constancia": "00012345678", "medio_pago": "003",
      "contraparte_doc": "20602222226", "contraparte_nombre": "PROVEEDOR SAC",
      "origen": "pdf_texto", "confianza": "0.92",
      "referencias": [ { "clase": "comprobante",
                         "datos": { "tipo_cp": "01", "serie": "F001", "numero": "123" } } ] }
  ],

  "imputaciones_de_movimientos": {
    "mov-881": { "cuenta_contable": "1212100", "contraparte_doc": "20607777773" },
    "mov-882": { "cuenta_contable": "4212100", "contraparte_doc": "20602222226", "centro_costo": "OBRA01" }
  }
}
```

Y el **maestro de cuentas**, que no es parte del documento sino un argumento —el motor no lo guarda—:

```json
[ { "id": "bbva-soles", "banco": "BBVA", "numero": "0011-0999-0000000001",
    "cci": "01199900000000000100", "moneda": "PEN", "cuenta_contable": "10411100" } ]
```

### Lo que aportas tú y lo que resuelve el motor

| Qué | Dónde |
|---|---|
| El movimiento, tal como lo imprime el banco o el papel | `movimientos[]` — solo `cuenta`, `fecha`, `importe` y `sentido` son obligatorios |
| **La cuenta 104 de cada cuenta bancaria** | el **maestro**, en `cuenta_contable`. El motor **no la deriva**: cada cuenta corriente tiene su divisionaria, y la de soles no es la de dólares |
| **La contrapartida** —la otra cara del asiento— | `imputaciones_de_movimientos`, por el `id_externo` del movimiento. Igual que la cuenta de un gasto llega en la imputación de su comprobante |
| Qué cancela el pago, **si el papel lo dice** | `movimiento.referencias[]`, con cuatro clases: `comprobante`, `tributo`, `cuenta_propia`, `libre` |
| Un traspaso entre tus propias cuentas | `imputaciones_de_movimientos` → `cuenta_propia`. **Es la única vía para declararlo**, y hace falta porque la NIC 7 §9 excluye esos traspasos de los flujos de efectivo |
| **La glosa que se escribe en el libro** | `imputaciones_de_movimientos` → `glosa`, y **una por parte** cuando hay reparto. La decide el contador: `descripcion` es el texto del banco |
| La deduplicación, los contrastes con la cabecera y qué falta | el motor, en `revisar_tesoreria` |

### Las cuatro cosas que conviene no confundir

1. **`cuenta` no es una cuenta contable.** Es el `id` con que tú nombras esa cuenta en tu maestro. La contable sale
   de ahí.
2. **`referencia` y `constancia` son dos números distintos y los dos valen.** `referencia` es el que le da el banco
   (`N° OPER`, `REFERENCIA`) y es la llave con la que una relectura no duplica; `constancia` es el del papel que
   prueba el pago, como el vóucher del Banco de la Nación. Una detracción pagada desde un banco tiene los dos.
3. **El importe va siempre positivo** y el signo lo lleva `sentido`: `cargo` sale, `abono` entra. Es el
   `CdtDbtInd` de camt.053 y el subcampo C/D del tag 61 de un MT940.
4. **Un cargo del banco es un movimiento, no un campo.** Una comisión, los portes o el mantenimiento llegan como
   un movimiento más, con su propia imputación. El `itf` es la excepción y existe por un motivo concreto: hay
   bancos que lo descuentan **sin darle fila** —BBVA lo pone en una columna—, y entonces no hay movimiento que lo
   represente. Vacío no es cero: es «el banco no lo dice». Y cuando el motor asiente, un pago de 2 000 con 0,50
   de ITF serán **dos asientos**.

### La glosa: la decide el contador, no el banco

`descripcion` es lo que imprimió el banco —«TRANSFERENCIA A CUENTAS DE TERCEROS BCP LOCAL»—, y además **entra en
la clave de deduplicación**, así que no puede ser lo que alguien reescriba al revisar. La glosa del libro va en
la imputación, y **en cada parte cuando hay reparto**: un cargo que paga tres facturas necesita tres, que es la
«Glosa Detalle» de CONCAR frente a su «Glosa Principal».

```json
"imputaciones_de_movimientos": {
  "mov-881": {"cuenta_contable": "4212100", "glosa": "Pago fact F001-123 PROVEEDOR SAC"},
  "mov-882": {"glosa": "Pago a proveedores de agosto",
              "reparto": [{"importe": "3000.00", "cuenta_contable": "4212100", "glosa": "Pago F001-123"},
                          {"importe": "1500.00", "cuenta_contable": "4212100", "glosa": "Pago F001-124"}]}
}
```

Si no la mandas, el motor cae a la descripción del banco y, en su defecto, al nombre de la contraparte: **ninguna
línea sale sin glosa**, que es la misma regla que ya tiene la del comprobante. Va en mayúsculas y **sin cortar**
—el largo lo decide cada destino, y CONCAR corta a 40 la principal y a 30 la del detalle—. Lo que saldría lo
puedes ver con `tesoreria.glosa_de_movimiento(movimiento, imputacion, parte)`.

La piden los cuatro destinos: es el campo 16 del Diario 5.1 del PLE y una columna obligada en CONCAR, CONTASIS y
STARSOFT.

### La moneda: ISO en el documento, tu alias en tu casa

En el documento la moneda va **en ISO 4217 y nada más** (`PEN`, `USD`, `EUR`…). Las que el motor reconoce son las
del catálogo —`catalogos_sunat.monedas`, del Anexo 1 de la RS 112-2021—, y es contra ésas contra las que se valida
una cuenta bancaria: una moneda que no esté ahí se rechaza al declarar la cuenta, y añadir una es añadirla al
catálogo con su fuente.

**Cómo la llames tú por dentro, o con qué letra la escriba tu sistema contable, es tuyo.** Eso es configuración
del contribuyente, no del estándar: `monedas_codigo` en la sección de tu destino.

```python
print(api.configuracion_por_defecto("concar")["concar"]["monedas_codigo"])     # {'PEN': 'MN', 'USD': 'US'}
print(api.configuracion_por_defecto("contasis")["contasis"]["monedas_codigo"])  # {'PEN': 'S', 'USD': 'D'}
```

Los valores de fábrica son los que dice la plantilla de cada sistema —CONCAR usa `US` y no `ME`; CONTASIS, `S` y
`D`—, y si tu instalación escribe otra letra, la declaras y manda la tuya.

### Lo que el motor te responde

```python
# El maestro es un argumento: el motor no lo guarda.
mi_maestro = [{"id": "bbva-soles", "banco": "BBVA", "numero": "0011-0999-0000000001",
               "cci": "01199900000000000100", "moneda": "PEN", "cuenta_contable": "10411100"}]

mes = {"open_accounting": api.OPEN_ACCOUNTING,
       "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC",
                 "periodo": "202608", "tipo": "tesoreria"},
       "extractos": [{"cuenta": "bbva-soles", "saldo_inicial": "1000.00", "saldo_final": "1500.00"}],
       "movimientos": [{"id_externo": "mov-881", "cuenta": "bbva-soles", "fecha": "2026-08-05",
                        "descripcion": "ABONO POR TRANSFERENCIA", "importe": "500.00", "sentido": "abono",
                        "moneda": "PEN", "saldo": "1500.00", "referencia": "000001", "origen": "archivo"}]}

r = api.revisar_tesoreria(mes, cuentas=mi_maestro)
print(r["totales_por_cuenta"][0]["abonos"], r["sin_imputar"])   # 500.00 ['000001']
print([a["codigo"] for a in r["avisos"]])                        # ['MOVIMIENTO_SIN_IMPUTAR']

# Con su contrapartida, el movimiento deja de esperar nada.
mes["imputaciones_de_movimientos"] = {"mov-881": {"cuenta_contable": "1212100",
                                                  "contraparte_doc": "20607777773"}}
r = api.revisar_tesoreria(mes, cuentas=mi_maestro)
print(r["imputados"], r["sin_imputar"], r["avisos"])      # 1 [] []
```

`r["totales_por_cuenta"]` es un **resumen** —cuántos movimientos trae cada cuenta, cuánto suman sus cargos y sus
abonos, lo que el banco descontó por ITF y la cuenta contable que sale del maestro—: **no afirma que nada cuadre**.
`r["sin_imputar"]` dice qué movimientos **esperan su contrapartida**, que es el `sin_cuenta` del dinero.
`r["sin_atribuir"]` dice cuánto de un pago no reclama ninguna referencia —y **no se cierra**: qué es ese resto lo
decides tú al imputar—. `r["de_lectura_asistida"]` marca lo que leyó un modelo, para que alguien lo mire.

**Lo único que el motor comprueba de los saldos es lo que el banco DECLARÓ contra lo que le mandaste**: si pones
la cabecera en `extractos[]`, sus dos totales contra la suma de tus líneas y su saldo final contra la aritmética
de esos mismos números (`TOTAL_DECLARADO_NO_COINCIDE`, `SALDO_FINAL_DECLARADO_NO_COINCIDE`). No necesita que
ninguna línea traiga su `saldo`, y **caza una línea entera perdida**, que es lo que la cadena de saldos no caza.

### Comprobar tu propia lectura: `tesoreria.cuadra`

Si tú parseas un extracto —de un PDF, de un Excel pegado, de un export del banco— tienes algo que el motor no
tiene: la **columna de saldo corrido**. Encadenarla es lo que convierte «leí un PDF» en «lo leí bien», y para eso
está publicada `tesoreria.cuadra`:

```python
from contaperu import tesoreria

leidas = [{"cuenta": "bbva-soles", "fecha": "2026-08-05", "importe": "500.00", "sentido": "abono",
           "saldo": "1500.00"}]
chequeo = tesoreria.cuadra(leidas, saldo_inicial="1000.00", saldo_final="1500.00")
print(chequeo.cuadra, chequeo.rompe_en)                 # True 0
```

**Y la trampa que hay que conocer**: `cuadra` significa «ninguna línea contradijo la cadena», así que **si ninguna
trae `saldo`, devuelve `True` sin haber comprobado nada**. Mira cuántas lo traían antes de creerte el verde. Por
eso `revisar_tesoreria` ya no la llama: un ERP que manda operaciones estructuradas no trae saldos, y recibía un
verde que no significaba nada. Aquí sí vale, porque aquí sí hay columna.

### El efecto sobre el efectivo, para tu estado de flujos (NIC 7)

Un movimiento, por sí solo, solo puede decir dos cosas: el dinero **entra** o **sale**. El tercer efecto del
catálogo, `transferencia`, no se deduce — **se declara**, porque una línea sola no puede saber que es la mitad de
un traspaso entre dos cuentas tuyas. Quien lo compone es `efecto_de`, juntando el movimiento con lo que imputaste:

```python
from contaperu import tesoreria

pago = tesoreria.Movimiento(cuenta="bbva-soles", fecha="2026-08-14", importe="4711.00", sentido="cargo")
print(tesoreria.efecto_de(pago))                                       # salida
print(tesoreria.efecto_de(pago, {"cuenta_contable": "4212100"}))       # salida: imputar no es traspasar
print(tesoreria.efecto_de(pago, {"cuenta_propia": "bbva-dolares"}))    # transferencia, porque TÚ lo declaraste
```

Para qué sirve: la **NIC 7 §9** deja fuera de los flujos de efectivo los traspasos entre partidas que ya son
efectivo, porque son gestión de tesorería y no actividad de la empresa. Si los cuentas como salida y entrada, el
mismo dinero aparece dos veces en tu estado de flujos. Llama a esto para excluirlos.

La otra forma de saberlo es casar las dos patas, que es `conciliar` (el hito D3) — y ésa **propone y nunca
confirma**, así que lo que afirma un traspaso es siempre tu `cuenta_propia`.

### El asiento del dinero (12.9)

**`revisar_tesoreria` no asienta, y seguirá sin asentar: mirar y asentar son dos preguntas.** El asiento lo arma
`generar_asiento`, igual que el de una compra, y lo que cambia es de dónde salen las líneas: de `movimientos[]` en
vez de `comprobantes[]`, que es lo que dice el tipo de libro. Quien integra solo nota tres cosas:

| | |
|---|---|
| El **maestro de cuentas** deja de ser un argumento | va en la configuración, en `cuentas_bancarias`, porque es lo que la empresa **es** y no lo que un periodo dijo. `describir_configuracion` lo publica, así que tu pantalla de ajustes lo puede pintar |
| Lo que `revisar_tesoreria` **avisa**, asentar lo **para** | sin la contrapartida (`movimiento_sin_imputar`) o sin la cuenta contable de la 104 (`sin_cuenta_de_efectivo`) no hay línea que escribir. Mira primero y asienta después |
| En `_asiento` la respuesta trae **`movimientos`** | con la misma forma que `comprobantes` —identidad, tramo de líneas y huella—, y la otra clave vacía. Las dos van siempre |

**Y antes de asentar, `diagnosticar` (12.12).** El camino normal —`diagnosticar` antes de `exportar`— vale igual
para el dinero, con la respuesta de la forma de su libro: `totales` cuenta `movimientos`, `repetidos` —las
relecturas del mismo extracto, que no se asientan— y `saldrian`, y `faltantes` trae las cinco faltas del dinero
por la misma clave con que se niega la excepción. Dos diferencias que conviene saber: **`saldrian` es todo o
nada**, porque el asiento de un libro de tesorería se arma entero o no se arma; y **las claves que son de un
comprobante no están** —ni `bloqueantes`, ni `avisos`, ni las detracciones, ni los sub-diarios, ni el resumen por
contraparte, ni `exige`—, porque un cero diría que se miró algo que aquí no existe. El esquema de la respuesta
(`GET /v1/esquemas/diagnostico.schema.json`) publica las dos formas en un `oneOf`.

Las cinco formas, y ninguna necesita una regla que no esté publicada: un **pago** deja la contrapartida al debe y
el efectivo al haber; un **cobro** al revés y **sin línea de IGV**, porque el débito fiscal se reconoció en la
venta; un **cargo del banco** es un gasto contra el efectivo; un **reparto** da una línea por parte y una sola de
efectivo; y un **traspaso** es el único con sus dos patas declaradas, que es por lo que no lleva imputación. Si el
banco descontó el **ITF** sin darle su propia línea, sale su propio asiento —`6412` contra el efectivo— por el
importe que dice el banco: no se calcula, porque un asiento se sustenta en la constancia o en el extracto.

### El archivo, y lo que promete el ida y vuelta (12.10)

`exportar` con el driver **`asiento_contable`** escribe el documento del estándar con **cuatro bloques**: el
`libro`, los `movimientos`, sus `imputaciones_de_movimientos` y el `asiento`, más `_exportacion` en la raíz. El
nombre sale de la convención de siempre: `ASIENTO_CONTABLE_TESORERIA_202610_<RUC>.json`.

**Con los cuatro el archivo se basta, y eso es más de lo que promete el de compras.** El ida y vuelta vale en los
dos sentidos, y los dos están en la batería:

- **reexportarlo** da el mismo archivo **byte a byte** — el bloque `asiento` que trae manda y no se rearma, así
  que si tú llevas el asiento, tus cuentas son las que salen;
- **rearmarlo** —quitándole el `asiento`— da la **misma huella** y las mismas líneas, porque los movimientos y su
  imputación están dentro. El documento de una compra no puede prometer esto: no escribe su bloque `imputaciones`,
  y el porqué está en el propio driver.

En la respuesta, `movimientos` dice cuántos salieron y `_exportacion.movimientos` lo que salió de cada uno
—identidad, tramo de líneas y huella—. `comprobantes` va en cero, y las dos claves van siempre.

### Lo que todavía NO hace

**No lo lleva a un sistema legacy.** Eso es el hito D6c y espera un archivo del sub-diario de bancos que un sistema
contable haya aceptado, con el que vendrán su clave de sub-diario y su numeración. Mientras no esté, pedir el
asiento con un destino de vocabulario legacy se para con `libro_que_todavia_no_se_numera`: el libro **se arma y no
se numera**, que son dos cosas distintas. El CSV entra con ellos, aunque su canal sea `erp`: escribe la columna
`rol`, que es vocabulario de un destino.

**Tampoco concilia.** Casar un pago con lo que cancela cuando el papel no lo dice es el hito D3, y lo que se decidió
de él importa: `conciliar` **propone y nunca confirma**.

### Qué está pagado: `aplicaciones` y `estado_de_cuenta` (12.3 y 12.4)

El puente entre tus tres libros. En el documento mandas **qué cancela qué, y por cuánto**:

```json
"aplicaciones": [
  {"de": {"clase": "movimiento",  "datos": {"id_externo": "mov-7"}},
   "a":  {"clase": "comprobante", "datos": {"tipo_cp": "01", "serie": "F001",
                                            "numero": "123", "contraparte_doc": "20602222226"}},
   "importe": "400.00", "moneda": "PEN", "fecha": "2026-03-10", "origen": "manual"}
]
```

y `estado_de_cuenta` te devuelve el **pendiente** de cada documento y la suma por contraparte. Cinco cosas que
conviene saber antes de integrarlo:

1. **No hay ninguna columna de estado, y no la va a haber.** El número que manda es `pendiente`; «por pagar» o
   «pagado» es una lectura suya. Si tu interfaz necesita la palabra, derívala del número **al pintarla** y no la
   guardes: un marcador al lado del número se desincroniza, y está medido fuera
   ([`REFERENCIAS.md`](REFERENCIAS.md), «La aplicación de un pago»).
2. **Tres pagos para una factura son tres aplicaciones**, y el tercero no es especial. No hay nada que marcar
   cuando se cierra.
3. **`origen` separa el hecho de la conjetura**, y una `propuesto` **no cuenta para ningún saldo**. Es donde
   encajará lo que proponga `conciliar` cuando exista: lo que convierte una candidata en un hecho es que alguien
   la elija, y entonces pasa a `manual`.
4. **Lo que viene de otros meses lo pones tú**, en `partidas_previas`: el libro es mensual y una factura de enero
   pagada en marzo vive en dos documentos. Es el mismo molde que `claves_previas` — un argumento que el motor
   recibe y no guarda. Si aplicas un importe a un comprobante que no viaja en el documento y no declaras su
   partida, sale igual, con su total en blanco y su aviso: el pago no desaparece.
5. **La fecha de corte también la pones tú.** Deja fuera las aplicaciones posteriores y te da los `dias` contra el
   vencimiento, negativos si aún no vence. **Los tramos de antigüedad no se calculan**: 30/60/90 es una convención
   de gestión sin norma detrás, y la aplicas tú sobre `dias`.

Y lo que no hace: **no convierte monedas**. Lo aplicado en una moneda distinta de la del documento viene aparte,
en `en_otra_moneda`, y no se resta del pendiente.

## ¿Te hace falta un driver? Casi seguro que no

Antes de escribir nada, mira cuál de estos tres eres. Solo el tercero pide código.

| | Qué necesitas | ¿Driver? |
|---|---|---|
| **1** | Leer asientos que otro armó | **No.** Te basta el esquema; ni siquiera instalas el paquete |
| **2** | Que el motor te dé el asiento, en el estándar | **No.** `exportar(documento, driver="asiento_contable")` y ya |
| **3** | Que el motor escriba **tu formato propio** | **Sí**, y va en tu paquete, sin pasar por aquí |

**Un driver existe para traducir a un formato que no podemos cambiar** — el Excel que importa un CONCAR instalado, el
TXT que pide SUNAT. Un sistema que puede adoptar el estándar no tiene nada que traducir: el estándar ya es su
formato, y para eso está el driver `asiento_contable`. Si escribes un driver que no te hacía falta, has creado un
traductor más que mantener.

Y el canal lo dice del formato, no de la edad del software: si tu importador pide siglas y correlativos es `legacy`
aunque el sistema sea de este año, y si acepta las líneas del estándar es `erp`.

## Un driver para tu sistema contable

Esto es el nivel 3: tu sistema importa un archivo con una forma suya. El contrato está en
`contaperu/drivers/contrato/` y la guía paso a paso, en `CONTRIBUTING.md`. Lo esencial:

- **Declara a quién entrega** (`CANAL`): `legacy` si es un sistema contable instalado que importa un archivo,
  `sunat` si es un registro o un libro que se presenta a SUNAT —por el SIRE o por el PLE, que son dos regímenes y
  un solo canal—, `erp` si entrega el formato neutral del estándar. `drivers_disponibles` dice el de cada driver.
- **Compruébalo antes de registrarlo**: `contaperu verificar-driver mi_paquete.mi_driver` dice si cumple el contrato y
  qué le falta (desde Python, `api.verificar_driver`).
- **Un driver de asientos recibe las líneas ya armadas** (`desde_lineas`), numeradas y cuadradas, con el índice de cada
  comprobante y su cabecera. Solo traduce: no puede equivocarse en una cuenta ni en un sentido.
- **Dos niveles.** *De serie*, dentro de este repositorio, con un archivo real que ese ERP haya aceptado. *Comunidad*,
  en un paquete tuyo que se registra por el grupo de entry points `contaperu.drivers`, sin esperar a nadie.
- **Si tu ERP tiene una API moderna** en vez de un archivo, escribir en ella es un hito reservado (canal `api_erp`, A5
  de la hoja de ruta). Mientras tanto, tu aplicación pide el asiento a `generar_asiento` con `driver="asiento_contable"` —las líneas del
  estándar, sin siglas, sub-diarios ni correlativos de ningún sistema legacy— y lo envía; el envío y los
  reintentos son suyos, con la identidad y la huella de cada comprobante como clave para no repetir.

## Si NO usas el motor: construir sobre el estándar

Todo lo de arriba supone que llamas a `contaperu`. No hace falta: `open-accounting` es un estándar publicado y
puedes construir sobre él, en el lenguaje que sea. Esta sección es para eso, y es el espejo de la anterior —allí se
escribe un driver contra el contrato del motor; aquí se lee el documento contra el contrato del estándar—.

**Qué recibes.** El documento que produce el driver `asiento_contable` tiene cinco claves, y desde la 3.9 lleva los
**tres bloques** del estándar: el libro, los comprobantes tal como los informa SUNAT y su asiento.

```json
{
  "open_accounting": "3.3",
  "libro": {"ruc": "…", "razon_social": "…", "periodo": "202601", "tipo": "compra"},
  "comprobantes": [{"tipo_cp": "01", "serie": "F001", "numero": "45680", "fecha_emision": "2026-01-10",
                    "contraparte_doc": "20677777771", "contraparte_nombre": "MAYORISTA NACIONAL SAC",
                    "concepto": "…", "base_gravada": "1000.00", "igv": "180.00", "exonerado": "50.00",
                    "total": "1230.00", "destino_igv": "DGNG", "id_externo": "f1"}],
  "asiento": [{"cuenta": "631101", "debe_haber": "D", "importe": "1050.00", "clase": "gasto", "rol": "principal"}],
  "_exportacion": {"driver": "asiento_contable", "motor": "3.10.0", "huella": "…", "comprobantes": [{"…"}]}
}
```

**Qué te garantiza, y es lo que ahorra el trabajo:** las cuentas ya están decididas, el asiento **cuadra** —el motor
se niega a producirlo si no— y el orden de las líneas es estable. Cada línea dice qué es por su `rol` y trae el
código SUNAT de su documento, no la sigla de ningún sistema.

**Y se basta**, que es lo que el bloque `comprobantes` añadió: el asiento por sí solo no puede decirte qué parte de
una compra mixta estaba exonerada —100 gravado más 50 exonerado son una sola línea de gasto de 150—, ni cómo se llama
tu proveedor, ni por qué se emitió una nota de crédito. Por eso **el documento puede volver a entrar al motor y dar
el mismo asiento, con la misma huella**, pasándole la misma imputación que la primera vez.

**Ojo con las dos claves que se llaman `comprobantes`** y no son lo mismo: la de la raíz son los hechos de cada
comprobante —el bloque del estándar— y la de `_exportacion` es su identidad, el tramo de líneas que le toca y su
huella. La segunda se llama así desde la 3.1 y no se renombra; la primera es la del estándar desde su 0.1.

**Cómo lo enlazas con lo tuyo.** Por dos vías, y conviene usar las dos:

- `linea.documento.id_externo` — el identificador que pusiste tú en el comprobante, en cada línea suya.
- `_exportacion.comprobantes` — por comprobante, su identidad, el tramo `[desde, hasta)` de líneas que le toca y la
  huella de ese tramo. **Esa huella es la clave para no repetir**: si la de un comprobante no cambió, es el mismo
  asiento que ya importaste. Los tramos parten las líneas sin dejar hueco ni solaparse.

**Qué NO lleva, y por qué.** Ni `fecha` de exportación ni nombre de archivo: no son hechos del asiento, y quien
llama al API los recibe en su respuesta. Tampoco sub-diarios ni correlativos: son vocabulario de un sistema legacy y
el documento del estándar no los tiene (`sub_diarios` sale vacío a propósito), ni el comodín `999999999` de una
constancia de detracción que nadie ha depositado todavía: **sin depósito, la clave no viaja**. Tampoco el bloque
`imputaciones`, y es a propósito: el esquema exige entonces `id_externo` en todos los comprobantes, y un mes cuyo
productor no los puso daría un documento que falla su propio esquema. Y ni una línea ni un comprobante **llevan las
claves que están vacías**: cuenta con que el juego de campos varíe de uno a otro, porque el estándar distingue «no lo
sé» de «es esto» omitiendo la clave.

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

**8. Y qué se lee de cada columna, lo dice el motor.** `api.campos_del_sire()` devuelve el formato columna a
columna: de cada campo del anexo —40 en el RVIE, 41 en el RCE— su número, el nombre que le da SUNAT, el campo
del documento donde cae o **el motivo por el que no cae**, y si el TXT de reemplazo lo devuelve con dato,
presente y vacío, o no lo manda. De las 81 columnas, 63 son campos del documento; **ninguna de las otras 18 se
pierde**, porque la fila entera del TXT viaja en `datos_originales["sire"]` del comprobante. Úsalo para
contestar «¿de dónde salió este dato?» en tu pantalla de revisión, y para saber qué te llega antes de escribir
una línea de código contra el registro.

**9. La detracción del SIRE: SUNAT dice QUE, tú dices CUÁL.** Si tu mes entra por la propuesta y no por los XML, la
detracción llega a medias, y conviene saber qué mitad:

- **SUNAT sí dice SI hay detracción.** El RCE trae una columna propia, el campo 38 del Anexo 8 de la RS
  040-2022, con una `D` en las filas sujetas al SPOT. En un RCE real de un mes (3018 filas) venía marcada en 221.
- **SUNAT no dice CUÁL.** No hay código del Catálogo 54, ni tasa, ni monto, ni cuenta del Banco de la Nación, ni
  constancia. Eso es del comprobante, no del registro.
- **Desde la 4.1 el motor lee la marca** y la guarda en `detraccion._marca_sire`, sin código. Y **se niega a exportar**
  esos comprobantes hasta que llegue el código, con la falta `sin_codigo_detraccion`: antes salían sin su línea de
  detracción y en silencio, con la cuenta por pagar al proveedor inflada.

Así que tu conector tiene dos cosas que hacer, y las dos por canales que ya usas:

```python
d = api.diagnosticar(documento, driver="concar", configuracion=config, imputacion=imputacion)
# La clave está cuando el destino exige la detracción: los cinco que escriben un asiento, el `sire` no.
faltan_codigo = d["faltantes"].get("sin_codigo_detraccion", [])
print(len(faltan_codigo), "marcados por SUNAT sin código de detracción")
```

Esa lista es la que **filtra la tabla donde el contador los completa**: no la imprimas entera, que un mes real trae
miles de filas. Y cuando la complete, el código viaja en la imputación de cada documento, al lado de su cuenta:

```python
con_detraccion = {"f1": {"cuenta_contable": "659999", "detraccion_codigo": "037"}}
print(con_detraccion["f1"]["detraccion_codigo"])
```

Con eso el motor saca la tasa de su tabla y el monto de `total × tasa`, y la detracción sale completa —sus dos líneas y
su código interno en cada destino— **igual que si el comprobante hubiera entrado por su XML**. Lo que traiga el
comprobante manda sobre la imputación, así que mandarlo siempre no rompe nada.

Un detalle de alcance: esto es **solo compras**. El RVIE no tiene columna de detracción en ninguno de sus 40 campos. Y
el driver `sire` no se detiene nunca por esto: el registro que se declara a SUNAT no lleva detracción.

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
- **Por HTTP**, la ruta `/v1/` no cambia mientras la mayor sea la misma, y `info.version` de `/openconta.json` dice qué versión
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

## Lo que promete la 13.x

- **`contaperu.api` no cambia de nombre ni de firma** hasta la 14.0 (`tests/test_superficie_publica.py`). Pueden llegar
  parámetros opcionales, claves nuevas en las respuestas y anotaciones `_*`; nunca irse.
- **Un nombre que cambia sigue resolviendo durante toda la 13.x**, y avisa con `contaperu.RutaObsoleta` diciendo
  cuál usar, hasta la 14.0 (`_obsoleto.RETIRO`). Ahora mismo no hay ninguno, y conviene saber por qué: la 7.0
  cumplió los seis que avisaban y de la 8.0, la 9.0, la 10.0 y la 12.0 no salió ninguno nuevo. La 9.0 rompió **sin** pasar
  por aquí, a propósito —un puente que siguiera aceptando el `es_venta: bool` mantendría vivo justo el camino que
  la mayor cerraba—, y la 10.0 retiró la maquinaria de las rutas de módulo, que llevaba tres mayores sin usarse.
  Lo que no se retiró es esto: corre tu batería con `-W error::contaperu._obsoleto.RutaObsoleta` y te sale cada
  sitio donde uses un nombre deprecado.
- **Si vienes de una 6.x y usabas el núcleo directamente**, la 7.0 retiró los seis atajos que la 6.4.0 dejó en la raíz
  al agrupar el núcleo. El cambio es de import y nada más: lo que devuelve cada función es idéntico.

  | Hasta la 6.5 | Desde la 7.0 |
  |---|---|
  | `contaperu.igv` | `contaperu.tributos.igv` |
  | `contaperu.detracciones` | `contaperu.tributos.detracciones` |
  | `contaperu.validar` | `contaperu.tributos.validar` |
  | `contaperu.comparar_sire` | `contaperu.tributos.comparar_sire` |
  | `contaperu.partida_doble` | `contaperu.contable.partida_doble` |
  | `contaperu.resumen` | `contaperu.contable.resumen` |

  **Quien solo usa `contaperu.api` no cambia una línea.** Y si usas el núcleo, el camino corto es instalar la 6.5.0
  antes de la 7.0 y correr tu batería con `-W error::contaperu._obsoleto.RutaObsoleta`: ahí las rutas viejas todavía
  resuelven y cada una te dice la suya. Con una advertencia: **el aviso sale al USAR el nombre, no al importar el
  módulo**, así que una línea que ningún test tuyo toque no saldrá. Haz también un `grep` de las seis.
- **Si llamas al paquete `asiento` o a `tributos.igv`, la 9.0 cambia un parámetro** y es el único cambio que
  rompe. Las que recibían `es_venta: bool` ahora reciben **los rasgos del libro**, y hoy el eje viaja por
  veintiuna funciones —dieciocho de `asiento`, quince de ellas en su superficie congelada, y tres de
  `tributos.igv`, que no congela nada—:

  | Hasta la 8.x | Desde la 9.0 |
  |---|---|
  | `asiento.faltantes_para(cs, config, True, exige)` | `asiento.faltantes_para(cs, config, libro.rasgos, exige)` |
  | `asiento.sub_diario(c, config, libro.es_venta)` | `asiento.sub_diario(c, config, libro.rasgos)` |
  | `asiento.cuenta_tercero(c, config, False)` | `asiento.cuenta_tercero(c, config, RASGOS["compra"])` |
  | `asiento.faltantes_para(cs, config)` *(sin decirlo)* | **ya no vale**: hay que decir el libro |

  Con un `Libro` delante es siempre `libro.rasgos`; sin él, `modelo.RASGOS["venta"]` o `["compra"]`. Y vale
  cualquiera de las tres formas: unos rasgos, un `Libro` o el tipo por su nombre.

  **Un booleano no se interpreta: para, y el error dice qué escribir.** Es a propósito — un `True` que se colara
  elegiría la rama equivocada en silencio, que es lo que esta mayor viene a quitar. Lo mismo con **omitirlo**:
  hasta la 8.x no decir nada significaba «compra», y ése era el error.

  **Por qué cambia.** El motor decidía casi todo con ese booleano y usaba `not es_venta` para decir «es compra»:
  el sentido debe/haber, el crédito frente al débito fiscal, cliente frente a proveedor, el sub-diario. Correcto
  con dos libros y un error silencioso con tres — un libro nuevo salía tratado como una compra, con el debe y el
  haber al revés. Ahora cada tipo de libro declara lo que el motor necesita saber de él (`modelo.RASGOS`), y
  añadir uno es añadir una fila.

  **Ojo con una cosa, y la decimos nosotros**: el test de superficie pública **no caza este cambio**, porque de
  los módulos de extensión congela los nombres y no las firmas. Los catorce nombres siguen ahí, y de las otras
  seis no sabe nada. Así que la comprobación es un `grep` de `es_venta` en tu código, no la batería.
- **El `libro` ya no se traga una clave que no es suya** (7.0). Son exactamente cuatro —`ruc`, `razon_social`,
  `periodo`, `tipo`— y cualquier otra detiene la lectura diciendo su nombre; tampoco pasan las anotaciones `_`, que
  van en la raíz del documento. Hasta la 6.5 se ignoraban en silencio, aunque el esquema las rechazara: si mandabas
  una clave de más creyendo que el motor la leía, **no la leía**.
- **OpenConta crece sin romper**: una ruta o un campo que está, sigue.
- **La 2.0 retiró las rutas de la 0.10** (`contaperu.operaciones`, `contaperu.generar`, `contaperu.cli`,
  `contaperu.servidor_mcp`, `contaperu.formato` y `drivers.concar.construir`). **Quien integró con la 1.x no cambia
  una línea**: la superficie pública de la 1.0 sigue entera y su test pasa sin regenerarse. Lo que desapareció es lo
  que ninguna versión publicada llegó a ofrecer — la 0.x nunca estuvo en PyPI.
- **El estándar es `open-accounting` 3.3**, y eso es un compromiso: nada de lo que existe se quita ni cambia de
  significado hasta una 4.0. Un valor nuevo de catálogo y un bloque opcional no suben la versión; los catálogos
  se leen de [`estandar/catalogos.json`](estandar/catalogos.json) y **una línea se contabiliza con `cuenta`,
  `debe_haber`, `importe` y `clase`**, que son los cuatro que exige. Si vienes de la 1.0, que el motor ya no
  acepta: [`estandar/MIGRAR-A-2.0.md`](estandar/MIGRAR-A-2.0.md) — son cuatro claves que se quitan y nada que
  rellenar. De la 0.3, [`estandar/MIGRAR-A-1.0.md`](estandar/MIGRAR-A-1.0.md) sigue ahí, y hay que pasar por las
  dos.
