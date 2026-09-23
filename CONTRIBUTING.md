# Contribuir a ContaPerú

Gracias por mirar. Este proyecto lo usa gente para presentar declaraciones reales, así que la barra es alta
en una sola cosa: **ninguna regla contable entra sin una fuente**.

## La regla que manda

Cada regla del motor lleva al lado **la norma, la resolución o el archivo real** que la justifica. En un
comentario, en el docstring o en el JSON de datos. Si no se puede citar de dónde sale, no entra — aunque sea
«así se hace siempre». Media docena de las decisiones más finas de este código (el redondeo de la detracción
a soles enteros, el recibo por honorarios sin crédito fiscal, la fecha del asiento del comprobante
extemporáneo) salieron de un archivo real que un sistema contable aceptó, y así es como se validan las que
vengan.

Lo mismo al revés: si encuentras una regla mal puesta, **abre un issue con el caso real** — el comprobante
(anonimizado), lo que el motor produjo y lo que tu sistema esperaba. Vale más que un parche.

## Nunca subas datos reales

Ni comprobantes de clientes, ni RUC de empresas que existen, ni razones sociales reales, ni claves. Para los
tests hay dos RUC seguros:

- `20131312955` — el de la propia SUNAT, el que usa en sus ejemplos.
- `20601234567` — inventado, con dígito verificador válido.

El `.gitignore` bloquea `privado/` y `*.privado.*`, pero el filtro que importa eres tú: lo que entra en la
historia de un repositorio público no sale nunca más.

## Añadir un driver de salida

Un driver traduce el asiento al formato que importa un sistema contable. El contrato completo está en
[`contaperu/drivers/contrato.py`](contaperu/drivers/contrato.py); para un driver de **asientos** nuevo
(SISCONT, STARSOFT…) la forma es `desde_lineas`: el núcleo arma las líneas neutrales de
`open-accounting`, las numera y exige que cuadren, y tu driver solo las traduce. No tienes que reimplementar
ni una cuenta, ni un sentido, ni la detracción.

```python
from contaperu.asiento.configuracion import CONFIGURACION_DEL_ASIENTO
from contaperu.configuracion import Campo
from contaperu.drivers.kit import Opciones

NOMBRE = "siscont"
# A quién se entrega: "legacy" es un sistema contable instalado que importa un archivo.
CANAL = "legacy"
FORMATOS = {"compra": "siscont_asiento", "venta": "siscont_asiento"}
OPCIONES = Opciones(fecha="DD/MM/AAAA", extension=".txt")
CONTENT_TYPE = "text/plain; charset=utf-8"
# Lo que tu ERP no puede importar sin, de entre lo que el núcleo deja pasar: "centro_costo", "moneda".
# La cuenta contable y la equivalencia del tipo las exige el núcleo por ti.
EXIGE = frozenset()
# Lo que se configura en tu sección: lo que el núcleo lee al armar el asiento, y lo propio de tu formato.
CONFIGURACION = (*CONFIGURACION_DEL_ASIENTO,
                 Campo("libro", "texto", "01", titulo="Libro de tu sistema", patron=r"^[0-9]{2}$"))

def nombre(libro, opciones=OPCIONES) -> str:
    return f"SISCONT_{libro.ruc}_{libro.periodo}{opciones.extension}"

def desde_lineas(libro, lineas, config, opciones=OPCIONES, *, indice=()) -> tuple[bytes, dict]:
    # Cada línea trae `rol` (principal, igv, tercero, detraccion…), `cuenta`, `debe_haber`, `importe`
    # como texto exacto, `documento.tipo_cp` (el código SUNAT), la glosa entera… `indice` dice qué tramo
    # de líneas es de qué comprobante, con su cabecera (glosa, base, IGV, total, contraparte). Tradúcelas
    # y devuelve los bytes del archivo y un resumen.
    ...
```

El driver CSV ([`contaperu/drivers/csv`](contaperu/drivers/csv/__init__.py)) es el ejemplo más corto de
esta forma.

**Si tu formato es una tabla simple** —un CSV o un TXT de columnas—, no escribas la proyección: **declárala**. Cada
columna dice qué campo de la línea neutral la llena y de dónde sale que vaya ahí, y `kit.columnas` escribe el archivo:

```python
from contaperu.drivers.kit.columnas import ColumnaDeLinea, escribir_csv

PLANTILLA = "La plantilla de importación de tu sistema, con su versión y su hoja"
COLUMNAS_DE_LINEA = (
    ColumnaDeLinea("CUENTA", "cuenta", PLANTILLA),
    ColumnaDeLinea("DEBE_HABER", "debe_haber", PLANTILLA),
    ColumnaDeLinea("IMPORTE", "importe", PLANTILLA, clase="importe"),
    ColumnaDeLinea("DOCUMENTO", "documento.serie_numero", PLANTILLA),
)

def desde_lineas(libro, lineas, config, opciones=OPCIONES, *, indice=()) -> tuple[bytes, dict]:
    lineas = list(lineas)
    return escribir_csv(lineas, COLUMNAS_DE_LINEA, separador="|", bom=False), {"filas": len(lineas)}
```

El contrato exige que cada columna diga su fuente y lea un campo que existe (`kit.columnas.rutas()`), y
`contaperu verificar-driver` te lo dice antes de proponerlo. El CSV de serie está escrito así. Cuando tu formato mezcla
datos de la cabecera del comprobante, cortes o reglas que una tabla no dice —como el Excel de CONCAR—, escribe la
proyección en código.

Si tu sistema no importa asientos sino su **registro** de compras y de ventas, y arma el asiento él mismo
(CONTASIS), la forma es `desde_comprobantes(libro, comprobantes, config, opciones)`: recibes los comprobantes y la
configuración, y cada cuenta la lees de `asiento.partes_de` (la de la base, o una por parte si hay reparto) y de
`asiento.cuenta_tercero` (la del total), que la resuelven igual que para el asiento, con la imputación de cada
documento dentro. El núcleo exige la cuenta antes de llamarte. Para un TXT por comprobante, como el SIRE, la forma es
`linea`. `construir`, la forma de CONCAR hasta la 0.10, la retiró la 2.0: un driver nuevo no la usa.

**Dos maneras de publicarlo:**

- **Como paquete propio**, sin esperar a nadie: declara en tu `pyproject.toml`
  `[project.entry-points."contaperu.drivers"]` → `siscont = "contaperu_siscont"` y, con los dos
  instalados, tu driver aparece en la CLI, en la api, en el servidor MCP y en la puerta HTTP.
- **Dentro de este repositorio**, en `contaperu/drivers/<sistema>/` y en `DE_SERIE` de
  `contaperu/drivers/__init__.py`.

Esté donde esté, lo que comprueba el contrato es `drivers.contrato.incumplimientos()` (lista vacía = cumple): el
registro lo llama al cargar un driver de terceros y, si le falta algo, lo ignora con un `AvisoDriver`. Para saberlo
antes, en la terminal: `contaperu verificar-driver mi_paquete.mi_driver` (0 si cumple, 1 con la lista de lo que falta).
`tests/test_contrato_drivers.py` se lo pide a cada driver registrado y además le hace exportar el golden de compras
con el asiento cuadrado. Requisitos para que un driver entre **al repositorio**:

1. **Un test con un caso real** que el sistema de destino haya aceptado de verdad. Un driver que nadie ha
   importado en su ERP no se publica: sería prometer algo que no consta.
2. **El asiento debe cuadrar.** Con `desde_lineas` lo exige el núcleo antes de llamarte, y tu driver no decide
   ninguna cuenta ni ningún sentido.
3. **Nada de red, nada de disco, nada de estado.** Entra por parámetro, sale por retorno.
4. **Un tipo de comprobante sin equivalente detiene la exportación**, no se inventa uno. Es la regla más
   importante: es preferible un error claro a un asiento silenciosamente mal.
5. **Declara en `EXIGE` lo que tu ERP no puede importar sin** (`centro_costo`, `moneda`; en uno de registro, `centro_costo` y `cuenta_unica`), y nada más: es
   lo que `diagnosticar` usa para decir si un mes está listo para tu destino, y lo que el núcleo hace
   cumplir antes de llamarte. Un requisito fuera de ese catálogo no pasa el contrato.
6. **Lo que tu formato no puede llevar, en `no_caben`** (una moneda que no tiene, un código más largo que su
   columna), por motivo: en un driver que lleva cuentas, `diagnosticar` lo dice antes y el núcleo se niega con
   `NoCabe` antes de llamarte, en cualquier forma. Un código no se corta y una moneda no se inventa.
7. **Declara lo que se configura en tu sección** (`CONFIGURACION`, con `configuracion.Campo`) y, si tu formato
   puede llevar un dato en más de una columna, **en cuáles** (`COLUMNAS_ELEGIBLES`, con `configuracion.Columna`:
   una fija y las demás a elegir). Un driver de asientos incluye `asiento.CONFIGURACION_DEL_ASIENTO`. Lo que
   declaras es lo que el motor valida, lo que una aplicación pinta en su pantalla y lo único que tu driver puede
   leer: `tests/test_contrato_drivers.py` lo comprueba con una configuración espía y leyendo tu código.
8. **Lo que tu destino no lleva, en `EXCLUYE_TIPOS`** (códigos SUNAT en texto: el SIRE y CONTASIS dejan fuera el
   recibo por honorarios, `02`). El núcleo lo quita antes de llamarte (`pipeline.seleccion.fuera_de`), así que tu driver no lo
   recibe, y lo cuenta en `fuera_del_destino`, en el resumen y en los totales de `diagnosticar`, para que no parezca
   que se perdió.
9. **Si tu driver se niega con una excepción propia, hereda de `asiento.NoExportable` y lleva su `clave`**, como
   `CorrelativoDesborda` de CONCAR (`sub_diario_desborda`: un sub-diario que pasaría de 9999). De lo que impide
   exportar, la CLI solo atrapa esa base y dice el motivo sin traceback; quien exporta lee su `clave` y sus
   `comprobantes`, y la puerta HTTP la responde como un 422 con esa `clave`.
10. **Declara tu `CANAL`**: `legacy` si tu sistema contable importa un archivo, `tributario` si es un registro que se
    presenta a SUNAT, `intercambio` si es un formato neutral. El contrato hace cumplir sus reglas (un `legacy` lleva
    cuentas y declara `EXIGE`); `api_erp` está reservado para escribir en la API de un ERP moderno y todavía no se
    admite. Cada canal se presenta en uno de los grupos del motor: `tributario` es SIRE, `legacy` es Legacy e
    `intercambio` es ERP.

## Estilo

- El código y los comentarios van **en español**, como el resto del proyecto y como el vocabulario del
  dominio. `asiento`, `sub_diario`, `comprobante` no tienen buena traducción y traducirlos confunde.
- Los comentarios explican **por qué**, no qué. El qué ya lo dice el código.
- Importes en `Decimal`, nunca `float`, salvo en el borde de escritura del archivo.
- Sin dependencias nuevas en el núcleo. Si un driver necesita una librería, va como extra opcional en
  `pyproject.toml`.

## Antes de abrir un PR

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

Los tests corren sin red y sin credenciales. Si el tuyo necesita algo de eso, está mal planteado.

`ruff` solo mira **código muerto y errores** —imports y variables que no usa nadie, redefiniciones, nombres sin
definir—, nunca estilo: aquí los comentarios se escriben en prosa y el largo de línea no es una regla. Si te
molesta una regla suya, es que hemos seleccionado mal; se discute en el issue, no se tapa con un `# noqa`.
