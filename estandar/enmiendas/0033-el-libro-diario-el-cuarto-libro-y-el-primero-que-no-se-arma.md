# 0033 · El Libro Diario: el cuarto libro, y el primero que no se arma sino que se recibe

| | |
|---|---|
| **Estado** | final |
| **Compatibilidad** | **aditiva**: entra un valor en el catálogo `tipos_de_libro` y no cambia ningún campo ni ninguna forma. Un documento 3.3 vale exactamente igual, y quien no conozca el libro nuevo lo rechaza por donde ya lo rechazaba — su destino |
| **Nivel** | estándar |
| **Versión** | `open-accounting` 3.3 (el catálogo pasa a su `1.1`: un valor nuevo **no sube la versión del documento**, que es lo que la [0011](0011-rol-y-tipo-de-libro-en-catalogo.md) prometió y `tesoreria` ya demostró) |
| **Test** | `tests/test_libro_diario.py` entero, y `tests/test_vocabulario.py::test_el_catalogo_crece_solo_a_proposito` |

## Motivación

El estándar transportaba tres libros —`venta`, `compra` y `tesoreria`— y con ellos **un ERP no tenía con qué
nombrar un asiento de planilla, de depreciación o de destino**. No es un hueco pequeño: medido sobre un Libro
Diario 5.1 presentado y aceptado de un mes real, son 12 094 líneas en 1 441 asientos repartidos en 19
sub-diarios, de los que alrededor de 530 no vienen del registro de compras ni del de ventas.

El hueco no era de producción. El driver `ple` ya escribe el Formato 5.1; lo que faltaba era **recibir**: que un
sistema pudiera mandar su diario y que el documento supiera decir qué es.

## Por qué UN libro y no uno por hecho

La tentación es un valor por cada hecho —`planilla`, `depreciacion`, `destino`— y se descarta por donde el repo
ya la descartó una vez, con el `honorario`: **`libro` es el libro tributario, no una categoría de gasto.**

Cada uno de esos hechos **ya tiene su libro** en la RS 234-2006 —el Libro de Planillas, el Registro de Activos
Fijos (7.1-7.4), el Registro de Costos (10.1-10.3)— y los tres **asientan en el mismo Formato 5.1**, que es el
contenedor genérico. Abrir uno por hecho sería inventar un vocabulario paralelo al de SUNAT y después
mantenerlo; y además rompería la identidad del comprobante, que lleva `libro.tipo` dentro.

Es la misma tesis que ya gobierna el repositorio: **un hecho nuevo entra por su libro, no por un rol nuevo.**

## Lo que lo hace distinto de los otros tres, y es lo que esta enmienda viene a decir

**Sus líneas llegan ya armadas, en el bloque `asiento`.** Los otros tres libros nombran un bloque de hechos que
el motor convierte en asiento: una compra sale de sus `comprobantes` y la tesorería de sus `movimientos`. El
diario sale del bloque `asiento`, que ya existe en el estándar desde la 1.0 y cuya descripción siempre dijo
«líneas de diario ya armadas».

Y **tiene** que ser así: armar una planilla pide las reglas de la planilla, y una depreciación el activo y su
vida útil. Son reglas que un motor contable no puede inventar sin fuente, y este estándar no las transporta.

De ahí dos consecuencias que conviene dejar escritas, porque quien integre las va a encontrar:

- **No se numera.** El CUO del Formato 5.1 lo pone quien produjo el asiento, y renumerar le cambiaría el número
  a un asiento que puede estar presentado. Por eso su fila no declara sub-diario.
- **El `rol` de sus líneas no se deriva**, y sale vacío. La regla publicada lee el lado contra el del libro o la
  cuenta contra el elemento 10 del PCGE; un diario no fija lado y sus líneas pueden ser cualquier cosa, así que
  derivar sería adivinar. Quien las produjo sabe qué papel cumple cada una; el motor no.

## Especificación

En `estandar/catalogos.json`, el catálogo `tipos_de_libro` gana un valor y pasa a su versión `1.1`:

```json
"diario": "El Libro Diario: todo asiento que no sea del registro de compras ni del de ventas —la planilla, la depreciación, el asiento de destino, un ajuste—. …"
```

Un documento de este libro declara `libro.tipo: "diario"` y trae sus líneas en el bloque `asiento`, que ya
existe y no cambia. **No trae `comprobantes` ni `movimientos`**, y no hace falta ninguna regla nueva para
decirlo: esos bloques son opcionales desde la 1.0, como todos.

Nada más. Ni un campo del esquema, ni una forma, ni un `required`.

## Qué NO cambia, y es la mitad de la promesa

- **Ningún documento existente.** Un 3.3 escrito ayer vale igual hoy.
- **La degradación sigue siendo del destino.** `libro.tipo` no degrada —quien recibe un libro que no conoce no
  puede adivinar qué hacer con él—, así que el driver que no lo declara en sus `FORMATOS` lo rechaza limpio
  nombrando los que sí lleva. Es lo que hacen hoy CONCAR, CONTASIS, STARSOFT y el SIRE con este libro.
- **El PLE tampoco lo declara todavía**, y es la ausencia que más dice: es el driver que escribe el 5.1, o sea
  literalmente este libro. Sus filas se construyen recorriendo el índice de comprobantes, y un libro que llega
  armado no tiene índice —sus entradas son sus propias líneas—, así que declararlo hoy habría producido un TXT
  **vacío con pinta de correcto**. Un driver gana un libro cuando sabe escribirlo, no cuando el libro existe.

## Fuente

El catálogo de libros y registros de la **RS 234-2006/SUNAT** y su Formato 5.1, cuyos 21 campos el repositorio ya
tiene publicados campo a campo en `contaperu/datos/sunat/ple_campos.json` con su fuente.

El caso real que lo destrabó: un **Libro Diario 5.1 presentado y aceptado** por un contribuyente peruano, de un
mes de 2026, leído el 16-oct-2026. **No entra al repositorio** —vive en `privado/`, que `.gitignore` bloquea—:
lo que entra son los datos que dejó, que son los recuentos de esta enmienda y la forma que describen.
