# Seguridad

## Qué reportar aquí

Este proyecto genera archivos que se presentan ante SUNAT y se importan en sistemas contables. Un
fallo puede significar una declaración mal hecha, no solo un programa que se cae. Trátalo como tal.

Reporta **en privado** —nunca abriendo un issue público— si encuentras:

- Una forma de que el motor produzca un asiento que **cuadra en apariencia pero está mal**, o un TXT
  que SUNAT acepte con importes incorrectos.
- Un XML malicioso que rompa el parser o llegue al sistema de archivos, a la red o a la memoria más
  allá de lo razonable (el núcleo usa `defusedxml`, pero el que encuentre el hueco manda).
- Cualquier problema en el **servidor MCP** o en la **puerta HTTP** (`contaperu-http`): se publican **sin
  autenticación a propósito** —no guardan datos, no tienen usuarios y no salen a la red—, así que lo único que pueden
  perder es CPU. Los dos comprueban el `Host` (421) y ponen topes al cuerpo y al archivo. Si encuentras una forma de
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
| 1.x, la última publicada | sí, como versión de parche |
| 0.10 y anteriores | no: se actualiza a la 1.x, que conserva sus rutas con aviso |

Desde la 1.0 un arreglo de seguridad sale como versión de parche de la última 1.x, sin cambiar la API pública
(`contaperu.api`) ni el contrato OpenConta. Si un arreglo exigiera romper algo, se dice aquí y en el CHANGELOG antes de
publicarlo.
