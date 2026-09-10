# Seguridad

## Qué reportar aquí

Este proyecto genera archivos que se presentan ante SUNAT y se importan en sistemas contables. Un
fallo puede significar una declaración mal hecha, no solo un programa que se cae. Trátalo como tal.

Reporta **en privado** —nunca abriendo un issue público— si encuentras:

- Una forma de que el motor produzca un asiento que **cuadra en apariencia pero está mal**, o un TXT
  que SUNAT acepte con importes incorrectos.
- Un XML malicioso que rompa el parser o llegue al sistema de archivos, a la red o a la memoria más
  allá de lo razonable (el núcleo usa `defusedxml`, pero el que encuentre el hueco manda).
- Cualquier problema en el **servidor MCP**: se publica **sin autenticación a propósito** —no guarda
  datos, no tiene usuarios y no sale a la red—, así que lo único que puede perder es CPU. Si
  encuentras una forma de hacerle algo más que eso, es exactamente lo que quiero saber.

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

El proyecto está en `0.x`: se arregla **sobre la última versión publicada**, no hay ramas de soporte
para versiones anteriores. Cuando llegue el `1.0` esto cambiará y quedará escrito aquí.
