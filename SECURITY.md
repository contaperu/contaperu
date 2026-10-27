# Seguridad

## Qué reportar aquí

Este proyecto genera archivos que se presentan ante SUNAT y se importan en sistemas contables. Un
fallo puede significar una declaración mal hecha, no solo un programa que se cae. Trátalo como tal.

Reporta **en privado** —nunca abriendo un issue público— si encuentras:

- Una forma de que el motor produzca un asiento que **cuadra en apariencia pero está mal**, o un TXT
  que SUNAT acepte con importes incorrectos.
- Un XML o un ZIP malicioso que rompa el parser o llegue al sistema de archivos, a la red o a la memoria
  más allá de lo razonable (el núcleo usa `defusedxml` y abre los ZIP con topes de tamaño y de proporción,
  pero el que encuentre el hueco manda).
- Cualquier problema en el **servidor MCP** o en la **puerta HTTP** (`contaperu-http`): se publican **sin
  autenticación a propósito** —no guardan datos, no tienen usuarios y no salen a la red—, así que lo único que pueden
  perder es CPU. Los dos comprueban el `Host` (421) y ponen topes al cuerpo y al archivo, y la puerta HTTP
  además limita las peticiones simultáneas. Si encuentras una forma de
  hacerles algo más que eso —saltarse la defensa del `Host`, leer un archivo del servidor, que un error enseñe su
  detalle—, es exactamente lo que quiero saber.

Un error de contabilidad que no sea explotable —una regla mal puesta, un caso que el motor resuelve
distinto a tu ERP— **no es un problema de seguridad**: ese va a un issue público con el caso real,
como dice `CONTRIBUTING.md`. Se arregla mejor a la vista de todos.

## Cómo reportarlo

Escribe a **globalprocesosai@gmail.com** con el asunto `[seguridad] contaperu`. Incluye qué
encontraste, cómo reproducirlo y qué esperabas — y **datos anonimizados**, nunca comprobantes de un
contribuyente real.

Respondo en un plazo de **5 días hábiles**. Si el fallo es real, acordamos contigo cuándo se publica
el arreglo, y tu nombre va en el CHANGELOG salvo que prefieras lo contrario.

## Versiones

| Versión | Recibe arreglos de seguridad |
|---|---|
| **La última publicada** | sí, como versión de parche |
| Cualquier anterior | no: se actualiza a la última |

**Cuál es la última no se escribe aquí a mano**, y el motivo es este archivo: hasta el 26-oct-2026 esta tabla
decía «2.x, la última publicada» con la 14.2.0 ya fuera —ocho mayores de desfase en la página que alguien abre
justo **cuando acaba de encontrar un fallo**—. Lo dicen la fuente de verdad: el [CHANGELOG](CHANGELOG.md), los
tags del repositorio y [PyPI](https://pypi.org/project/contaperu/).

Un arreglo de seguridad sale como versión de parche de la última publicada, sin cambiar la API pública
(`contaperu.api`) ni el contrato OpenConta. Si un arreglo exigiera romper algo, se dice aquí y en el CHANGELOG antes de
publicarlo.

**Subir de una mayor a otra sí puede pedir tocar código**: el motor ha roto a propósito varias veces, y cada
rotura está contada en el CHANGELOG con su porqué y lo que hay que cambiar. Si estás en una versión vieja porque
migrar no te sale a cuenta y encuentras un fallo de seguridad, escribe igual: se mira el caso.
