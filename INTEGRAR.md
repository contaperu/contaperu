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

Entra un **documento `open-accounting` 0.3** (`estandar/LEEME.md`): la cabecera del libro (RUC, periodo, ventas o
compras) y los comprobantes tal como los emite SUNAT, con los importes en positivo y como texto exacto. Si tienes los
XML o la propuesta del SIRE, el motor arma el documento por ti (`leer_xml`, `leer_propuesta_sire`).

Aparte del documento llegan dos cosas que son de tu aplicación y no del comprobante:

- **La configuración contable** de cada empresa: lo general en la raíz y una sección por sistema. `describir_configuracion`
  dice qué se configura, para pintar la pantalla, y `configuracion_por_defecto` da un punto de partida.
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
configuracion = {"cuentas": {"gasto": "659999"}, "usa_centros_costo": False}

diagnostico = api.diagnosticar(documento, driver="concar", configuracion=configuracion)
for falta in diagnostico["que_falta"]:
    print(falta["pedir_a"], "·", falta["texto"], falta["comprobantes"])

if diagnostico["listo_para_exportar"]:
    archivo = api.exportar_archivo(documento, driver="concar", configuracion=configuracion)
    print(archivo.archivo, len(archivo.contenido), "bytes")      # el .xlsx, listo para escribir o servir
```

Cada función recibe el documento primero y todo lo demás por su nombre; las que van hacia un sistema piden `driver`,
sin valor por defecto. Los que hay los dice `api.drivers_disponibles()`.

### Reconocer lo que ya exportaste

El Excel de CONCAR se suma al importarlo: la misma tanda importada dos veces duplica los asientos. Cada exportación
trae con qué reconocerla, y la identidad de cada comprobante —el RUC y el tipo del libro, el tipo, la serie y el número
sin ceros, y en compras el proveedor— es la clave con que tu aplicación evita repetir un envío.

```python
resultado = api.exportar(documento, driver="concar", configuracion=configuracion, fecha="2026-09-14")
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
    api.exportar(documento, driver="concar", configuracion={"cuentas": {"gasto": "659999"}})
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
    "open_accounting": "0.3",
    "libro": {"ruc": "20601234567", "razon_social": "EMPRESA DE PRUEBA SAC", "periodo": "202601", "tipo": "compra"},
    "comprobantes": [{
      "tipo_cp": "01", "serie": "F001", "numero": "123", "fecha_emision": "2026-01-15",
      "contraparte_tipo_doc": "6", "contraparte_doc": "20131312955", "contraparte_nombre": "PROVEEDOR DE PRUEBA SAC",
      "base_gravada": "100.00", "igv": "18.00", "total": "118.00", "id_externo": "fila-1"
    }]
  },
  "driver": "csv",
  "configuracion": {"cuentas": {"gasto": "659999"}, "usa_centros_costo": false},
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
(`contaperu-mcp --transporte http --dominio …`). Las once herramientas se anuncian de solo lectura y sin salir a la red,
y sus nombres son los de siempre: `diagnosticar`, `exportar`, `generar_asiento`, `validar_comprobantes`… Cómo
conectarlo a Claude está en el `README.md`.

## Un driver para tu sistema contable

Si tu ERP todavía no tiene driver, el contrato está en `contaperu/drivers/contrato.py` y la guía paso a paso, en
`CONTRIBUTING.md`. Lo esencial:

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
  de la hoja de ruta). Mientras tanto, tu aplicación pide el asiento a `generar_asiento` y lo envía; el envío y los
  reintentos son suyos, con la identidad y la huella de cada comprobante como clave para no repetir.

## Versiones: fija la tuya y actualiza cuando decidas

ContaPerú publica versiones con número (SemVer): una de parche arregla, una menor añade sin romper y solo una mayor
rompe. Cada una sale de un tag `vX.Y.Z` como Release de GitHub, con la rueda, el sdist y sus sumas SHA-256, y un commit
en `main` no le llega a nadie hasta que se publica. Tu aplicación **fija una versión exacta** y la cambia cuando
decide, después de leer qué trae.

- **Desde Python**, la versión exacta y su huella. Mientras el repositorio sea privado, la rueda de la Release
  comprobada contra sus sumas, o el commit de su tag:

  ```bash
  sha256sum -c SHA256SUMS --ignore-missing
  pip install "contaperu[excel] @ git+https://github.com/contaperu/contaperu.git@<commit del tag vX.Y.Z>"
  ```

  Cuando esté en PyPI, `contaperu[excel]==X.Y.Z` en tus dependencias, con su hash, y Dependabot o Renovate te abren
  la actualización.
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
seguridad llegan solo a la última versión publicada de la 1.x (`SECURITY.md`).

## Lo que promete la 1.x

- **`contaperu.api` no cambia de nombre ni de firma** hasta la 2.0 (`tests/test_superficie_publica.py`). Pueden llegar
  parámetros opcionales, claves nuevas en las respuestas y anotaciones `_*`; nunca irse.
- **OpenConta crece sin romper**: una ruta o un campo que está, sigue.
- **Las rutas de la 0.10** (`contaperu.operaciones`, `contaperu.generar`, `contaperu.cli`, `contaperu.servidor_mcp`,
  `contaperu.formato`) siguen funcionando con un aviso `RutaObsoleta` que dice qué usar, y se retiran en la 2.0.
- **El estándar sigue en `open-accounting` 0.3**: todo documento que validaba, valida y significa lo mismo.
