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

Un driver traduce las líneas de diario al formato que importa un sistema contable. Vive en
`contaperu/drivers/<sistema>/` y expone:

```python
NOMBRE = "contasis"
FORMATOS = ("txt",)          # o ("xlsx",), ("csv",)…

def construir(libro, comprobantes, contab, correlativos, op=OPCIONES) -> tuple[bytes, dict]:
    """Devuelve el archivo y un resumen. O bien, para salidas de texto línea a línea:"""

def linea(c, libro, idx, op=OPCIONES) -> str:
    ...
```

Se registra en `contaperu/drivers/__init__.py`. Requisitos para que se acepte:

1. **Un test con un caso real** que el sistema de destino haya aceptado de verdad. Un driver que nadie ha
   importado en su ERP no se publica: sería prometer algo que no consta.
2. **El asiento debe cuadrar.** El driver llama a `partida_doble.cuadra()` antes de escribir bytes.
3. **Nada de red, nada de disco, nada de estado.** Entra por parámetro, sale por retorno.
4. **Un tipo de comprobante sin equivalente detiene la exportación**, no se inventa uno. Es la regla más
   importante: es preferible un error claro a un asiento silenciosamente mal.

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
