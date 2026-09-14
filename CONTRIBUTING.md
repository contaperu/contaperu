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
from contaperu.formato import Opciones

NOMBRE = "siscont"
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

def desde_lineas(libro, lineas, config, opciones=OPCIONES) -> tuple[bytes, dict]:
    # Cada línea trae `rol` (principal, igv, tercero, detraccion…), `cuenta`, `debe_haber`, `importe`
    # como texto exacto, `documento.tipo_cp` (el código SUNAT), la glosa entera… Tradúcelas y devuelve
    # los bytes del archivo y un resumen.
    ...
```

El driver CSV ([`contaperu/drivers/csv`](contaperu/drivers/csv/__init__.py)) es el ejemplo más corto de
esta forma.

Si tu sistema no importa asientos sino su **registro** de compras y de ventas, y arma el asiento él mismo
(CONTASIS), la forma es `desde_comprobantes(libro, comprobantes, config, opciones)`: recibes los comprobantes y la
configuración, y cada cuenta la lees de `asiento.partes_de` (la de la base, o una por parte si hay reparto) y de
`asiento.cuenta_tercero` (la del total), que la resuelven igual que para el asiento, con la imputación de cada
documento dentro. El núcleo exige la cuenta antes de llamarte. Las otras dos formas —`linea` para un TXT por
comprobante, como el SIRE, y `construir` para un archivo armado desde los comprobantes, como CONCAR— siguen
existiendo.

**Dos maneras de publicarlo:**

- **Como paquete propio**, sin esperar a nadie: declara en tu `pyproject.toml`
  `[project.entry-points."contaperu.drivers"]` → `siscont = "contaperu_siscont"` y, con los dos
  instalados, tu driver aparece en la CLI, en la fachada y en el servidor MCP.
- **Dentro de este repositorio**, en `contaperu/drivers/<sistema>/` y en `DE_SERIE` de
  `contaperu/drivers/__init__.py`.

Esté donde esté, `tests/test_contrato_drivers.py` lo examina: cumple el contrato y exporta el golden de
compras con el asiento cuadrado. Requisitos para que un driver entre **al repositorio**:

1. **Un test con un caso real** que el sistema de destino haya aceptado de verdad. Un driver que nadie ha
   importado en su ERP no se publica: sería prometer algo que no consta.
2. **El asiento debe cuadrar.** Con `desde_lineas` lo exige el núcleo antes de llamarte; con `construir`,
   el driver llama a `partida_doble.exigir()` antes de escribir bytes.
3. **Nada de red, nada de disco, nada de estado.** Entra por parámetro, sale por retorno.
4. **Un tipo de comprobante sin equivalente detiene la exportación**, no se inventa uno. Es la regla más
   importante: es preferible un error claro a un asiento silenciosamente mal.
5. **Declara en `EXIGE` lo que tu ERP no puede importar sin** (`centro_costo`, `moneda`; en uno de registro, `centro_costo` y `cuenta_unica`), y nada más: es
   lo que `diagnosticar` usa para decir si un mes está listo para tu destino, y lo que el núcleo hace
   cumplir antes de llamarte. Un requisito fuera de ese catálogo no pasa el contrato.
6. **Lo que tu formato no puede llevar, en `no_caben`** (una moneda que no tiene, un código más largo que su
   columna), por motivo: en un driver que lleva cuentas, `diagnosticar` lo dice antes. El núcleo se niega con
   `NoCabe` antes de llamarte solo en la forma `desde_comprobantes`; en las demás, lo informa `diagnosticar` y no
   te detiene nadie, así que tu driver no escribe lo que no cabe. Un código no se corta y una moneda no se inventa.
7. **Declara lo que se configura en tu sección** (`CONFIGURACION`, con `configuracion.Campo`) y, si tu formato
   puede llevar un dato en más de una columna, **en cuáles** (`COLUMNAS_ELEGIBLES`, con `configuracion.Columna`:
   una fija y las demás a elegir). Un driver de asientos incluye `asiento.CONFIGURACION_DEL_ASIENTO`. Lo que
   declaras es lo que el motor valida, lo que una aplicación pinta en su pantalla y lo único que tu driver puede
   leer: `tests/test_contrato_drivers.py` lo comprueba con una configuración espía y leyendo tu código.

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
pytest
```

Los tests corren sin red y sin credenciales. Si el tuyo necesita algo de eso, está mal planteado.
