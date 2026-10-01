# Libros y cuentas: el PLE como suelo del estándar, y el modelo de cuentas de los ERP abiertos

**Estado: documento de trabajo, escrito el 1-oct-2026 sobre la librería 4.1.0 y `open-accounting` 1.0.** Nada de lo
que aquí se propone está implementado, y este documento **no es normativo**: lo normativo es
[`estandar/LEEME.md`](estandar/LEEME.md) y lo que valide su esquema. Lo que está comprobado contra fuente primaria se
cita con su norma o su URL; lo que falta por comprobar va marcado **`[por confirmar]`** y no se usa para sostener
ninguna conclusión. Pasa a documento vigente, o se reparte entre
[`INTEROPERABILIDAD.md`](INTEROPERABILIDAD.md) y [`API-DE-REGISTRO.md`](API-DE-REGISTRO.md), el día que se cierre el
refinado y cada candidata tenga su caso real.

---

## 0 · De dónde nace

De una objeción de John, y es buena: **si cada cuenta del PCGE ya trae su dinámica, ¿para qué un `rol` en la línea?**
La cuenta `421203` es de detracción, la `421201` es la obligación con el proveedor, y el PCGE ya dice qué representa
cada una. ¿Para qué declarar encima un papel?

Y de tres casos que el motor hoy no cubre, y que la pregunta destapa: **una planilla** (renta de 5ta, ONP,
remuneración), **una depreciación** (que se relaciona con el elemento 3) y **un asiento de cuentas de destino** no
tienen ningún rol asignado, porque el catálogo de roles solo tiene los seis de compras y ventas.

La investigación salió a ver cómo lo resuelve el software de EE. UU. —abierto y cerrado— y volvió con algo que no
esperaba: **la respuesta estaba en el Perú, en el PLE**, y el modelo de roles no era el problema.

---

## 1 · La objeción es correcta, y el motor ya le da la razón a medias

**El PCGE no dice que la `421203` sea de detracción.** Se comprueba contra el catálogo del propio motor
(`api.buscar_cuenta_pcge`):

```
421201  →  4212 «Emitidas»   exacta: false
421203  →  4212 «Emitidas»   exacta: false
```

El PCGE 2026 **termina en `4212 «Emitidas»`**. Las dos son la **misma cuenta del plan**, y el `exacta: false` es el
motor diciendo «esto ya no es una cuenta del PCGE, es una subdivisión por debajo». Que el `-01` sea el proveedor y el
`-03` la detracción es una convención del **plan de cuentas de fábrica**
([`configuracion.py`](contaperu/configuracion.py), `cxp` y `cxp_detraccion`), configurable por cada empresa, y en
STARSOFT la misma línea es `42120003` porque ese sistema numera a ocho dígitos.

**Y el motor ya aplica la objeción donde es válida:** la `clase` de cada línea **se deriva de la cuenta**, del primer
dígito, que es el elemento del PCGE ([`pcge/clases.py`](contaperu/pcge/clases.py)). Ahí no hay nada declarado. La
prueba de que la distinción es real está en la huella del asiento
([`asiento/huella.py`](contaperu/asiento/huella.py)): `SIN` excluye `clase` **con este argumento**, que es el de John:

> **`clase`** — es función total de `cuenta`, que sí entra. No aporta información, así que excluirla no puede hacer que
> dos asientos distintos compartan huella.

`rol` **no** está excluido. Los dos campos pasaron por la misma prueba y cayeron en lados distintos.

### Por qué `rol` no se deduce: el caso que lo decide

No es el IGV ni el gasto. Es éste, en una compra con detracción:

```
tercero             421201  H  11800.00
detraccion_tercero  421201  D   1180.00
```

**Misma cuenta, los dos signos, el mismo comprobante.** Cuenta + signo + importe dice que en la `421201` hubo dos
movimientos; no dice que el `D 1180` está **recortando** el `H 11800`, que es el hecho económico. Eso no está en el
plan de cuentas: está en el SPOT.

Y hay código real que depende de ello: [`drivers/starsoft/proyeccion.py:296`](contaperu/drivers/starsoft/proyeccion.py)
descarta las dos líneas de la detracción por su rol, porque STARSOFT no la asienta; `:298` ordena las filas por rol,
porque su manual pone el IGV antes del proveedor en compras y al revés en ventas; y `:166` decide nueve columnas según
si la línea es la del total. Sin `rol`, ese archivo sale **mal, no vacío**.

### Lo que el repositorio ya tenía decidido

Nada de esta sección es nuevo. `API-DE-REGISTRO.md`, «El papel de cada línea: `rol` y `clase`», ya fijó los dos ejes;
`estandar/LEEME.md` ya escribió la regla de degradación —«con `clase`, `debe_haber` e `importe` se puede contabilizar
una línea aunque no se conozca su `rol`»—; y el esquema ya la cumple: el `required` de una línea es
`["cuenta", "debe_haber", "importe", "clase"]` y **`rol` no está**.

**Conclusión de la capa:** el `rol` es opcional, ignorable y no deducible de la cuenta. La objeción no obliga a
quitarlo. Pero tampoco justifica usarlo como el sitio donde aterrizan los hechos nuevos — y eso es lo que el resto del
documento corrige.

---

## 2 · Cómo lo resuelve el mundo: tres capas, no una

Ningún sistema revisado pone un «rol» en la línea del asiento. Reparten la semántica en tres capas distintas, y
conviene no confundirlas porque cada una responde otra pregunta.

| Capa | Pregunta | Dónde vive | Quién la tiene |
|---|---|---|---|
| **1 · Clasificación de la cuenta** | ¿qué *es* esta cuenta? | en la cuenta, intrínseca | todos |
| **2 · Determinación** | ¿qué cuenta uso para *este papel*? | en la configuración, por organización y dimensión | los ERP completos |
| **3 · Propósito de la línea** | ¿para qué está *esta línea*? | en la línea | casi nadie |

### 2.1 · Clasificación de la cuenta: todos tienen dos niveles

| Sistema | Nivel grueso | Nivel fino |
|---|---|---|
| **Odoo** | 6 `internal_group` | **18 `account_type`** |
| **QuickBooks Online** | 5 `Classification` | 16 `AccountType` → ~250 `AccountSubType` |
| **Xero** | 5 `Class` | 18 `Type`, más `SystemAccount` (`DEBTORS`, `CREDITORS`, `GST`…) |
| **GnuCash** | 5 bases | 12 tipos (6 de activo, 3 de pasivo, y uno cada uno de patrimonio, ingreso y gasto) |
| **Beancount** | 5 raíces estrictas (`Assets`, `Liabilities`, `Equity`, `Income`, `Expenses`) | — |
| **hledger** | ninguna obligatoria | — |
| **`open-accounting` hoy** | **5 `clases`** | **— (no hay)** |

El mecanismo de Odoo merece atención porque es el mismo que ya usa este motor, un nivel más abajo: **`internal_group`
se deriva del prefijo de `account_type`**, cortando por el primer `_` (`account_type.split('_', maxsplit=1)[0]`), igual
que aquí la `clase` se deriva del primer dígito de la cuenta.

**Dato clave para el §4:** los 6 `internal_group` de Odoo son `asset`, `liability`, `equity`, `income`, `expense` y
`off`. Los cinco primeros son **exactamente las cinco `clases` de este estándar**.

Los dos extremos del abanico también enseñan algo. **Beancount** obliga a cinco raíces y se niega a procesar el
fichero si algo no cuadra; **hledger** no obliga a ninguna y deja las convenciones al usuario. El estándar está más
cerca de Beancount, y con motivo: la `clase` es obligatoria desde la 1.0 y el motor rechaza una que contradiga su
cuenta ([`asiento/lineas.py`](contaperu/asiento/lineas.py)).

### 2.2 · La determinación de cuentas: la capa que aquí no se había mirado

Es la que contesta «¿qué cuenta uso para el IGV, para el proveedor, para la detracción?». Y es el hueco real: **OFBiz,
iDempiere, GnuCash, Tryton y ledger-cli no se habían mirado nunca** en este repositorio.

**Apache OFBiz** separa dos cosas que suenan parecidas: `GlAccountClassId` (categorización y reportes) y
`GlAccountTypeId` (el papel). Trae **57 tipos**, de los que su demo mapea **19**, y el mapeo vive en una entidad
aparte, **`GlAccountTypeDefault`**, que lo resuelve **por organización**: `ACCOUNTS_RECEIVABLE` → `120000`,
`ACCOUNTS_PAYABLE` → `210000`, `SALES` → `400000`, `TAX` → `900000`, `COST_OF_GOODS_SOLD` → `500000`… Y su
documentación dice para qué existe, en una frase que describe exactamente lo que hace este motor:

> «The GL Account Type is used to translate **one side** of the journal entry.»

Un lado lo pone quien imputa; el otro sale de la tabla. Es el reparto de
[`asiento/motor.py`](contaperu/asiento/motor.py) entre la imputación y `config["cuentas"]`.

**iDempiere / ADempiere** lleva el patrón al extremo: la tabla `C_AcctSchema_Default` tiene **unas 45 ranuras**
nombradas, con prefijo según a qué entidad se cuelgan —`B_` cuenta bancaria, `C_` cliente, `V_` proveedor, `P_`
producto, `T_` impuesto, `CH_` cargo, `PJ_` proyecto, `W_` almacén—: `C_RECEIVABLE_ACCT`, `V_LIABILITY_ACCT`,
`T_DUE_ACCT`, `T_CREDIT_ACCT`, `P_REVENUE_ACCT`, `P_COGS_ACCT`, `WRITEOFF_ACCT`, `REALIZEDGAIN_ACCT`… Y las resuelve
en **tres niveles, de lo más específico a lo más general**: entidad concreta (este proveedor) → grupo o categoría
(este grupo de proveedores) → defecto del esquema contable (la organización).

**Dynamics 365 Business Central** da la respuesta más limpia a «¿a qué variables está amarrado el papel?». Sus
*posting groups* combinan dos ejes, y su documentación los nombra así:

> «The VAT business posting group is about **who** I'm selling or buying from and the VAT product posting group is
> about **what** I'm selling or buying.»

Para cada combinación de los dos se configuran el porcentaje, el tipo de cálculo y las cuentas de venta, compra e
inversión del sujeto pasivo. El papel no está amarrado a la cuenta: **el papel más las dimensiones determinan la
cuenta.**

### 2.3 · El propósito de la línea: solo XBRL GL

**XBRL GL** (Global Ledger, de XBRL International) es el único que pone algo así en la línea. Su `entryDetail` lleva
`account`, `documentType`, `debitCreditCode` y `amount` —la misma forma que la línea de este estándar— y además
**`accountPurposeCode`**. Pero su oficio es otro: permite que un mismo `entryDetail` lleve **varias estructuras de
cuenta**, una para US GAAP, otra para IFRS, otra para la fiscal, cada una etiquetada con su propósito.

Eso confirma lo que `REFERENCIAS.md` ya había escrito —«el `rol` de la línea no lo tiene nadie»— y, a la vez, enseña
el patrón del §3.4: **varias proyecciones de la cuenta en la misma línea**, que es la forma general de lo que aquí
hacen los drivers reescribiendo `cuenta`.

### 2.4 · El puente con un plan de cuentas nacional

**SAF-T no es peruana.** Es de la OCDE y la adoptaron Portugal, Noruega, Lituania, Polonia y otros; **el Perú no**.
Aquí el equivalente son el PLE y el SIRE. Lo que sí aporta es un patrón: cada cuenta lleva un **`StandardAccountID`**
que la empareja con el plan de cuentas oficial del país. En Lituania ese código estándar es de **2 y 4 caracteres**;
en Noruega se mapea a la lista de cuentas estándar o al estado de resultados; en Portugal, a la taxonomía S o M.

Y hay un precedente directo para el Perú, aunque no sea norma: **la localización peruana de Odoo (`l10n_pe`) ya mapeó
el PCGE**, con del orden de 1 100 cuentas tipadas, y lo hizo **al nivel de divisionaria de cuatro dígitos** —`1211`,
`4211`, `3331`, `7011`—. La misma profundidad a la que llega el catálogo de este motor, por su cuenta. *(Qué
`account_type` asigna a cada elemento, y en particular qué hace con el elemento 9: **`[por confirmar]`**, leyendo su
CSV.)*

---

## 3 · El suelo es el PLE, y ya define lo que falta

Aquí está el hallazgo que reordena el documento, y vino de una corrección de John: **el SIRE solo cubre compras y
ventas; el PLE envía el Libro Diario y los demás libros.** El motor habla dos libros porque lee el SIRE. Ése es el
universo del SIRE, no el de SUNAT.

### 3.1 · La cuenta contable ya tiene nivel normativo obligatorio

**RS 234-2006/SUNAT, artículo 6, literal b), inciso (iii)** — citado literal:

> «Utilizando el Plan Contable General Revisado vigente en el país, a cuyo efecto emplearán cuentas contables
> desagregadas a nivel de: (iii.1) **Tres (3) dígitos como mínimo**, para los deudores tributarios que en el ejercicio
> anterior hayan obtenido ingresos brutos hasta cien (100) UITs; y, (iii.2) **Cuatro (4) dígitos como mínimo**, para
> los deudores tributarios que en el ejercicio anterior hayan obtenido ingresos brutos mayores a cien (100) UITs.»

Dos cosas que esto zanja:

1. **El nivel de la cuenta no es opinable: es normativo**, y depende del tamaño del contribuyente. Tres dígitos hasta
   100 UIT, cuatro por encima.
2. **SUNAT misma distingue el nivel normativo de la expansión de cada empresa.** Es exactamente la distinción entre
   `cuenta` (la del plan del contribuyente, `421201` o `42120001`) y la divisionaria del PCGE (`4212`), que
   `api.buscar_cuenta_pcge` **ya deriva hoy** sin ningún dato nuevo.

*(La norma dice «Plan Contable General **Revisado**», que era el vigente en 2006; hoy rige el PCGE 2026. La
equivalencia entre ambos es el pendiente que `CLAUDE.md` ya tiene anotado —«Equivalencias del PCGE 2026: con la cita
del artículo al lado de cada mapeo»—, y el cargador rechaza un mapeo sin fuente.)*

### 3.2 · El Formato 5.1 «Libro Diario» ya tiene la forma de nuestra línea

Comparado campo a campo:

| Formato 5.1 del PLE (RS 234-2006) | La línea de `open-accounting` hoy |
|---|---|
| Número correlativo o **código único de la operación** (CUO) | `correlativo` (y `sub_diario`) |
| **Fecha** de la operación | `fecha` |
| **Glosa** o descripción de la operación *(opcional)* | `glosa` |
| **Referencia de la operación**: código del libro, número correlativo, documento sustentatorio | `documento{}` y `referencia{}` |
| **Código de la cuenta contable**, con el mínimo del artículo 6 | `cuenta` — **sin nivel normativo declarado** |
| **Denominación de la cuenta** *(opcional si usa más de 4 dígitos de subcuenta)* | **no existe** |
| **Movimiento: Debe / Haber** | `debe_haber` + `importe` |
| Totales | `cuadrar()` / `_asiento.cuadre` |

**La línea de este estándar ya es, casi exactamente, una línea del Libro Diario de SUNAT.** Le faltan dos cosas, y las
dos son la misma propuesta: el nivel normativo de la cuenta y su denominación.

Eso cambia de sitio la idea del §2.4: **no es un préstamo de SAF-T, es lo que SUNAT exige.** Y es mejor sitio, porque
la regla del repositorio es que ninguna regla contable entra sin fuente, y la fuente peruana existe.

*(La estructura **electrónica** del 5.1 —el TXT campo a campo del Anexo 2 de la RS 286-2009 y sus modificatorias,
entre ellas la RS 169-2015— confirma esta tabla o la matiza: **`[por confirmar]`**. `INTEROPERABILIDAD.md`, «Modelos
de referencia», ya tiene de ese anexo el CUO, los campos 10-12, el 20 y el 21, pero no el de la cuenta contable.)*

### 3.3 · Los tres casos que no estaban cubiertos ya tienen su libro

El catálogo de libros y registros de la RS 234-2006, por su número de formato:

| | Libro o registro | Formatos |
|---|---|---|
| 1 | Libro Caja y Bancos | 1.1, 1.2 |
| 2 | Libro de Ingresos y Gastos | 2.1, 2.2 |
| 3 | Libro de Inventarios y Balances | 3.1 – 3.20 |
| 4 | Libro de Retenciones (incisos e y f del art. 34 de la LIR) | 4.1 |
| 5 | **Libro Diario** y Libro Diario de Formato Simplificado | **5.1**, 5.2 |
| 6 | Libro Mayor | 6.1 |
| 7 | **Registro de Activos Fijos** | 7.1 – 7.4 |
| 8 | Registro de Compras | 8.1 |
| 9 | Registro de Consignaciones | 9.1, 9.2 |
| 10 | **Registro de Costos** | 10.1 – 10.3 |
| 12 | Registro de Inventario Permanente en Unidades Físicas | 12.1 |
| 13 | Registro de Inventario Permanente Valorizado | 13.1 |
| 14 | Registro de Ventas e Ingresos | 14.1 |
| — | Libro de Planillas *(hoy T-Registro y PLAME)* | — |

*(Los **códigos de 8 dígitos** con los que el PLE nombra cada libro en el fichero TXT —y la nomenclatura
`LE` + RUC + año + mes + día + código + opcionalidad + identificador + estado + moneda— viven en el Anexo 3 de la
RS 286-2009: **`[por confirmar]`**. Las fuentes secundarias consultadas se contradicen entre sí, así que no se copian
de aquí: se leen de la norma.)*

Con ese catálogo delante, los tres casos de la pregunta de John **dejan de necesitar roles nuevos**:

| Hecho | Su sitio en el PLE |
|---|---|
| **Depreciación** | **Registro de Activos Fijos** (7.1-7.4, anual), y el asiento en el **5.1** |
| **Planilla** | **Libro de Planillas**, y el asiento en el **5.1** |
| **Asiento de cuentas de destino** | **Registro de Costos** (10.1-10.3), y el **5.1** |
| Cualquier otro asiento | **Libro Diario 5.1**, que es el contenedor genérico |

Hoy `libro.tipo` tiene **dos** valores. El catálogo del PLE es el superconjunto, y el **5.1 es el comodín legítimo**:
todo asiento que no sea del registro de compras ni del de ventas es una línea del Libro Diario.

**Esto contesta la pregunta original de raíz.** Un hecho nuevo entra por el **libro**, con su formato de SUNAT detrás,
no por el catálogo de roles con un valor inventado. Y así la decisión de John del 18-sep-2026 —«el catálogo de roles se
abre, pero no crece»— deja de ser una preferencia y pasa a tener un motivo estructural.

### 3.4 · Dos detalles del dominio que conviene dejar escritos

- **La depreciación no toca el elemento 3.** El asiento es `68x` al debe contra **`39x` (depreciación acumulada)** al
  haber: la `33` no se mueve, porque la `39` es su cuenta de valuación de signo contrario. El vínculo con el activo
  concreto es un auxiliar, no una línea — el mismo sitio donde hoy viven el centro de costo y el anexo.
- **El asiento de destino es derivable, no es un hecho nuevo.** Se obtiene de las líneas de gasto más su
  `centro_costo`, que ya viaja en todas las líneas. Y hay un motivo normativo para no meterlo en el estándar como
  hecho: **el elemento 9 no está en el PCGE** —`941101` no resuelve en el catálogo, porque el PCGE deja la
  contabilidad analítica de explotación a cada empresa—. Su sitio es un driver o un post-proceso. El motor, además, ya
  acepta imputar directo a una cuenta del elemento 9: `clases.py` la mapea a `gasto` «porque muchas empresas imputan
  el gasto por su destino y no por su naturaleza».

---

## 4 · Odoo como base: qué se le toma, qué se le mejora, y qué no se puede

Decisión de John (1-oct-2026): si Odoo es un destino, **se toma su modelo como base cuando sea bueno y se mejora**
hasta que sea fácil de integrar para cualquier ERP; lo que falte se toma de los ERP abiertos de EE. UU.

### 4.1 · Lo que se le toma, y por qué es bueno

**Sus 18 `account_type`**, como valores del nivel fino que al estándar le falta:

```
asset_receivable · asset_cash · asset_current · asset_non_current · asset_prepayments · asset_fixed
liability_payable · liability_credit_card · liability_current · liability_non_current
equity · equity_unaffected
income · income_other
expense · expense_depreciation · expense_direct_cost
off_balance
```

Tres razones para tomarlos en vez de inventar un enum:

1. **La convergencia ya existe.** Sus 6 grupos derivados son las **cinco `clases` de este estándar** más `off`, y ese
   sexto cae justo donde el motor hoy se niega: los elementos 8 y 0 del PCGE, que `clases.py` deja sin clase porque
   son de cierre y de control. `off_balance` nombra exactamente eso.
2. **El mecanismo es el mismo que ya se aceptó aquí**: derivar el grupo del prefijo, como la `clase` sale del primer
   dígito. La `clase` seguiría siendo derivable y seguiría cuadrando.
3. **No nace un vocabulario nuevo**, que es el objetivo: el documento se vuelve cargable en cualquier Odoo sin
   traducción, y se evita el tercer estándar.

Y nótese `expense_depreciation` y `expense_direct_cost`: dos de los casos que la pregunta de John destapó ya tienen su
valor en ese vocabulario.

### 4.2 · Lo que se le mejora, que es el aporte

1. **Anclarlo a una fuente normativa.** El `account_type` de Odoo es una decisión de producto, que renombra entre
   mayores. Aquí cada valor queda **derivado de la divisionaria del PCGE**, con el artículo del PCGE 2026 al lado: no
   se negocia, no se mantiene a mano y no se puede desincronizar sin que un test se ponga rojo.
2. **Conservar el `rol`, que Odoo no tiene para el Perú.** Su `display_type` (`product`, `tax`, `payment_term`…)
   describe su formulario de factura: **no tiene `detraccion` ni `retencion_4ta`**, y no los va a tener.
3. **Añadir el nivel normativo y la denominación** del artículo 6 y del Formato 5.1, que Odoo no necesita porque no
   declara a SUNAT, y aquí son obligatorios.

### 4.3 · Por qué el modelo de un ERP no puede *ser* el estándar

Cinco motivos, y el primero es dirimente:

1. **La licencia.** Odoo es **LGPL**; `contaperu` es **MIT**. El propio repositorio ya lo investigó: de MIT, BSD y
   Apache-2.0 se porta código con su aviso; de LGPL, no. Los **valores de un enum son hechos** y citarlos es
   referencia, pero **empaquetar el CSV de `l10n_pe`** aquí es otra cosa y no se hace. El mapeo se deriva del catálogo
   propio y, si acaso, se *compara* con `l10n_pe` como contraste externo. *(Licencia exacta del módulo:
   **`[por confirmar]`**.)*
2. **Odoo *es* el destino, no el estándar.** El mismo argumento que `INTEROPERABILIDAD.md` ya usó para otra cosa:
   «ERPNext y Odoo lo necesitan porque ellos *son* el destino; ContaPerú escribe hacia un destino que ya guarda esa
   exigencia».
3. **Ningún destino del motor lee Odoo.** CONCAR, CONTASIS, SISCONT y STARSOFT, no. La tesis es «encima, no en lugar
   de»: el contador se queda con su sistema.
4. **Su modelo no es un contrato versionado.** El campo pasó por `user_type_id`, `account.account.type` y
   `account_type` en mayores sucesivas. La promesa de la 1.0 —nada se quita ni cambia de significado hasta una 2.0— no
   se monta sobre eso.
5. **No compiten de capa.** Odoo clasifica un plan de cuentas; `open-accounting` intercambia documentos. Los
   artefactos comparables son SAF-T, XBRL GL y EN 16931, y contra ésos ya se posiciona.

**Y lo que a Odoo le falta se toma de los abiertos de EE. UU.:** la tabla de determinación con dimensiones del §2.2.

---

## 5 · La arquitectura que sale: tres capas, cada una con su fuente

El estándar deja de parecer un tercer estándar y se vuelve **el puente entre los dos que ya existen**: el suelo
normativo lo pone SUNAT; el vocabulario para integrar, el mundo de los ERP abiertos.

| Capa | Qué responde | De dónde sale su autoridad | Qué falta hoy |
|---|---|---|---|
| **1 · El libro** | qué registro es esto | **Catálogo del PLE** (RS 234-2006; códigos en el Anexo 3 de la RS 286-2009) | `libro.tipo` solo tiene `compra` y `venta` |
| **2 · La cuenta** | qué cuenta, a qué nivel, de qué tipo y cómo se llama | **Art. 6 RS 234-2006** (nivel) · **PCGE 2026** (divisionaria) · **`account_type` de Odoo** (tipo) | ni nivel, ni denominación, ni tipo fino |
| **3 · El papel** | para qué está esta línea | **invención propia**, ya documentada y gobernada | nada: los seis se quedan |
| **4 · La determinación** | qué cuenta usa cada papel | **OFBiz · iDempiere · Business Central** | sin dimensiones: hoy solo por moneda |

Dos propiedades de este reparto, y son las que lo hacen escalable:

- **Cada capa crece por su lado y por su motivo.** Un hecho nuevo (planilla, depreciación) es un **libro**, no un rol.
  Un plan de cuentas distinto es la **capa 2**, no el esquema. Un ERP con reglas propias es la **capa 4**, no el
  núcleo.
- **Ninguna capa necesita una tabla de 800 filas.** El rol no es un atributo de la cuenta y no lo va a ser: el motor
  lo escribe en **seis llamadas literales** (`motor.py:295-343`) según el hecho que registra, no consultando nada. La
  relación es de muchos a muchos —`principal` admite cualquiera de las ~800 cuentas; la `421201` lleva dos roles—, y
  por eso una cuenta nueva en el plan de una empresa **no obliga a tocar ningún fichero**.

---

## 6 · Candidatas a propuesta

Van aquí y **no** en la tabla de `INTEROPERABILIDAD.md` todavía, a propósito: ese inventario es uno y se numera de
corrido, y meter cinco filas que aún van a cambiar lo ensuciaría. Entran ahí, con su número, cuando el refinado cierre
y cada una tenga su caso real. El molde de cada una es el del inventario: nivel, caso real que la destraba, test que la
fijaría, prioridad y hito.

### A · `libro.tipo` crece con el catálogo del PLE

**La central, y la que destraba las otras.** Con ella, planilla, depreciación y asiento de destino tienen sitio sin
tocar el catálogo de roles.

**Lo que hay que respetar.** `tipos_de_libro` **no degrada como `rol`**: quien recibe un libro que no conoce no puede
adivinar qué hacer con él, así que el driver que no lo declare en sus `FORMATOS` lo rechaza limpio diciendo qué libros
lleva. Añadir valores es aditivo y no sube la versión del estándar, pero **cada driver decide qué libros declara** —y
choca con algo que `INTEROPERABILIDAD.md` ya tenía anotado: «`FORMATOS` solo acepta `venta` y `compra`».

| | |
|---|---|
| Nivel | `estándar` |
| Caso real que la destraba | Un libro distinto de compras o ventas que un sistema haya aceptado: el TXT de un 5.1, o el asiento de planilla que CONCAR importó |
| Test que la fijaría | Un documento con un `libro.tipo` del PLE valida; el driver que no lo declara lo rechaza nombrando los que lleva; `compra` y `venta` no cambian de significado |
| Prio | C |
| Hito | `—` |

### B · La cuenta normativa y su denominación en la línea

La línea lleva la cuenta de la empresa y además **su divisionaria del PCGE** (al mínimo del artículo 6) y **su
denominación**, que el Formato 5.1 exige salvo que la empresa use más de cuatro dígitos de subcuenta.

**Qué arregla.** Cuando el destino es STARSOFT, el driver reescribe la cuenta a ocho dígitos (`421201` → `42120001`) y
el asiento deja de ser reconocible para quien no conozca ese plan. Con la divisionaria al lado, un asiento de CONCAR y
uno de STARSOFT se leen igual. Es el patrón del `accountPurposeCode` de XBRL GL —varias proyecciones de la cuenta en
la misma línea— pero con fuente peruana.

**El coste, que decide si es baratísima o carísima.** `rol` entra en la huella; `SIN` solo excluye `correlativo`,
`clase` y `documento.id_externo`. Un campo nuevo en la línea **mueve todas las huellas guardadas** salvo que entre en
`SIN` — y tiene **el mismo argumento que `clase`** para entrar: es función de `cuenta`, que sí entra. Decidirlo es
parte de la propuesta.

| | |
|---|---|
| Nivel | `estándar` |
| Caso real que la destraba | Ya lo tiene: el artículo 6 lo exige y `buscar_cuenta_pcge` ya lo deriva. Falta decidir si entra en `SIN` |
| Test que la fijaría | Cada línea trae su divisionaria y su denominación; la huella no se mueve; un asiento de STARSOFT y uno de CONCAR dan la misma divisionaria; el elemento 9 sale sin ella y no rompe |
| Prio | **B** |
| Hito | C10 |

### C · `tipo_de_cuenta`: los `account_type` de Odoo, derivados de la divisionaria

**La objeción que tiene que responder.** `API-DE-REGISTRO.md`, «Lo que se descartó, y por qué», rechaza copiar los
~250 subtipos de QuickBooks: «cada país fue añadiendo los suyos y el enum dejó de ser un estándar: es el camino del que
no se vuelve». Ésta no cae en eso, por tres motivos: los valores son **18, no 250**; son los de un proyecto abierto
cuyos grupos **ya coinciden** con las cinco clases; y la asignación **no se mantiene a mano**, se deriva de la
divisionaria del PCGE. Entra opcional, nunca `required`, para no tocar la regla de degradación.

| | |
|---|---|
| Nivel | `estándar` |
| Caso real que la destraba | Un ERP que reciba el documento y pida más que las cinco clases |
| Test que la fijaría | Cada `tipo_de_cuenta` es uno de los 18; su prefijo da la misma `clase` que `pcge.clase_de`; una cuenta del elemento 9 sale sin tipo y no rompe |
| Prio | C |
| Hito | `—` (cuelga de C10) |

### D · La tabla de determinación, con dimensiones

Formalizar `configuracion.cuentas` como **papel × quién × qué → cuenta**, resuelto por lo más específico, como OFBiz,
iDempiere y Business Central. **Es la única de las cinco que cubre un hueco de investigación real.**

**Lo que ya existe, y hay que reconocer.** La jerarquía de tres capas **ya está construida** —fábrica
(`configuracion.py`) → driver (`CUENTAS_POR_DEFECTO`) → empresa—, resuelta por `drivers.contrato.cuentas_por_defecto`,
con ocho ranuras: `cxp`, `cxp_detraccion`, `honorarios`, `retencion_4ta`, `igv`, `clientes`, `otros_tributos`,
`icbper`. **Lo que falta son las dimensiones**, y las dos que Perú necesita **ya viajan en los datos**: la
**contraparte** es el «quién», y el **código del Catálogo 54** es literalmente un *product posting group* —clasifica
qué se compra y de ahí sale una tasa—, y ya entra por `imputacion.detraccion_codigo`. Precedente interno:
`cuentas_con_centro = ["62","63","65","70"]` ya es una regla por **prefijo de cuenta**, como las dimensiones por
prefijo de Odoo y por tipo de cuenta de ERPNext que `INTEROPERABILIDAD.md` ya tiene investigadas.

**Lo que no se toma.** El lenguaje declarativo de requisitos, ya descartado con su motivo. Y las ~45 ranuras de
iDempiere: nombran hechos que el motor no registra —almacén, proyecto, variaciones de costo—. La tabla crece por hecho,
no por completitud.

| | |
|---|---|
| Nivel | `N` + configuración |
| Caso real que la destraba | Un segundo caso donde la cuenta dependa de la contraparte o del código 54, y no solo de la moneda |
| Test que la fijaría | Dos comprobantes iguales con distinta contraparte caen en cuentas distintas; sin dimensión declarada, el asiento es idéntico al de hoy y la huella no se mueve |
| Prio | C |
| Hito | `—` |

### E · `retencion` genérico, con el tributo en un campo

`retencion_4ta` metió el tributo en el nombre del rol. No escala: renta de 5ta, ONP y AFP cumplen **el mismo papel**
—una retención que recorta lo que el tercero cobra— con tributos distintos. El bloque `detraccion` ya lo hace bien: rol
genérico, código y tasa dentro.

**Las tres cosas que la frenan, y van escritas:**

- **John decidió lo contrario** el 18-sep-2026: «el catálogo de roles se abre, pero no crece; los seis se quedan como
  están, y son solo de compras y ventas».
- **Renombrar es carísimo.** `rol` entra en la huella, así que cambiar `retencion_4ta` invalidaría todas las huellas
  guardadas de los asientos que lo lleven, y la fórmula es contrato: obliga a anunciarlo como cambio de
  comportamiento. Solo cabe **aditivo**, con `retencion` al lado y `retencion_4ta` marcado `reemplazada`, que es la
  regla de gobierno: un valor publicado no se quita ni cambia de significado.
- **Y con la candidata A puede que no haga falta.** Si la planilla entra como libro del PLE, su asiento es una línea
  del 5.1, y el **aporte del empleador** —que no es retención, porque al trabajador no se le descuenta nada— tiene
  sitio sin tocar el catálogo de roles. **Es la pregunta abierta de este documento.**

| | |
|---|---|
| Nivel | `estándar` |
| Caso real que la destraba | Una planilla real: su tareo, sus boletas y el asiento que su sistema aceptó |
| Test que la fijaría | Un recibo por honorarios sigue dando `retencion_4ta` byte a byte; una planilla da `retencion` con su tributo |
| Prio | D |
| Hito | J3 |

---

## 7 · Descartes

| Qué | Estado | Motivo |
|---|---|---|
| **Adoptar el modelo de Odoo como el estándar** | descartado | §4.3, cinco motivos; el primero es la licencia |
| **Empaquetar los datos de `l10n_pe`** en este repositorio | descartado | LGPL frente a MIT. Se cita y, si acaso, se compara |
| **Una tabla de cuenta → rol para el PCGE** | descartado | §5: el rol no es atributo de la cuenta; la relación es de muchos a muchos y una cuenta nueva no obligaría a tocar nada |
| **Un rol nuevo por cada hecho nuevo** (planilla, depreciación, destino) | descartado | §3.3: el hecho entra por su **libro** del PLE, que es fuente normativa |
| **Copiar los ~250 `AccountSubType` de QuickBooks** | descartado antes de este documento | «es el camino del que no se vuelve» (`API-DE-REGISTRO.md`) |
| **Escribir un driver del PLE 5.1** | fuera de alcance | Aquí el PLE es **fuente**, no destino. Un driver pide un archivo real que ese sistema haya aceptado, y ya está anotado en negativo que «no consta que ningún legacy importe el Libro Diario 5.1 del PLE» |

---

## 8 · Lo que queda por confirmar

Ninguno de estos puntos sostiene una conclusión de este documento; todos son precisión que falta.

| | Qué falta | Dónde está |
|---|---|---|
| 1 | Los **códigos de 8 dígitos** de cada libro del PLE y la nomenclatura del TXT | Anexo 3 de la RS 286-2009 y modificatorias. Las fuentes secundarias se contradicen (`050000` frente a `050100`) |
| 2 | La **estructura electrónica del 5.1**, campo a campo, para confirmar el de la cuenta contable y el de la denominación | Anexo 2 de la RS 286-2009 / RS 169-2015. El PDF de MINJUS no se deja extraer con las herramientas de esta sesión |
| 3 | El **Formato 5.1 oficial** publicado por SUNAT | `contenido.app.sunat.gob.pe` rechazó la conexión el 1-oct-2026 |
| 4 | La **licencia exacta de `l10n_pe`** y qué `account_type` asigna a cada elemento del PCGE, en especial al 9 | su `__manifest__.py` y su CSV |
| 5 | El **`ReportCode` de Xero**: el único campo de clasificación que no está investigado en ningún documento del repositorio | la API de Xero |
| 6 | Las **equivalencias PCGE Revisado → PCGE 2026** para el artículo 6, con la cita del artículo al lado | pendiente ya anotado en `CLAUDE.md` |

---

## 9 · Fuentes

**SUNAT: el PLE como estándar de libros** (consultadas el 1-oct-2026)

- RS 234-2006/SUNAT, libros y registros vinculados a asuntos tributarios: artículo 6 (el Plan Contable General y el
  mínimo de dígitos) y el catálogo de formatos, incluido el 5.1 «Libro Diario» —
  https://www.sunat.gob.pe/legislacion/superin/2006/234.htm
- RS 234-2006/SUNAT, separata especial — https://www.oas.org/juridico/PDFs/mesicic3_per_rs234.pdf
- Formato 5.1 «Libro Diario» publicado por SUNAT —
  http://contenido.app.sunat.gob.pe/insc/Libros+y+Registros/Informacion+m%C3%ADnimo+formatos/FORMATO_5_1.pdf
  *(no accesible el 1-oct-2026)*
- RS 286-2009/SUNAT, sistema de llevado de libros electrónicos: estructuras en el Anexo 2, tablas y códigos en el
  Anexo 3. **`[por confirmar]`**
- RS 169-2015/SUNAT, Anexo 2 (ya citado en `INTEROPERABILIDAD.md`) —
  https://spij.minjus.gob.pe/Graficos/Peru/2015/Junio/30/RS-169-2015-SUNAT-ANX-2.pdf

**La clasificación y la determinación de cuentas en los ERP abiertos** (consultadas el 1-oct-2026)

- Apache OFBiz, `GlAccountTypeDefault` y los tipos de cuenta del mayor —
  https://cwiki.apache.org/confluence/display/OFBENDUSER/12.1.4.1+GL+Account+Type+Defaults
- Apache OFBiz, `UtilAccounting` (`GlAccountClassId`) —
  https://nightlies.apache.org/ofbiz/stable/javadoc/org/apache/ofbiz/accounting/util/UtilAccounting.html
- Apache OFBiz, cuentas del mayor por tercero y por producto —
  https://cwiki.apache.org/confluence/display/OFBENDUSER/12.1.4.12+Party+GL+Accounts ·
  https://cwiki.apache.org/confluence/display/OFBENDUSER/12.1.4.2+Product+GL+Accounts
- iDempiere, uso de las cuentas por defecto (`C_AcctSchema_Default`) —
  https://wiki.idempiere.org/en/Default_Accounts_Usage
- ADempiere, cuentas por defecto — https://wiki.adempiere.net/Default_accounts
- Odoo, `account.account` (`account_type` e `internal_group`) —
  https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_account.py
- Odoo, plan de cuentas — https://www.odoo.com/documentation/18.0/applications/finance/accounting/get_started/chart_of_accounts.html
- Odoo, localización peruana `l10n_pe` (plan alineado al PCGE) —
  https://raw.githubusercontent.com/odoo/odoo/18.0/addons/l10n_pe/data/template/account.account-pe.csv
- GnuCash, tipos de cuenta — https://www.gnucash.org/docs/v5//C/gnucash-manual/acct-types.html
- Beancount, tipos de cuenta y las cinco raíces — https://beancount.io/docs/glossary
- Microsoft, Business Central: *posting groups* y el IVA por grupo de negocio y de producto —
  https://learn.microsoft.com/en-us/dynamics365/business-central/finance-work-with-vat ·
  https://github.com/MicrosoftDocs/dynamics365smb-docs/blob/main/business-central/finance-setup-vat.md

**Los estándares de intercambio** (ya citados en `API-DE-REGISTRO.md` e `INTEROPERABILIDAD.md`; se repiten aquí por lo
que aportan a este documento)

- XBRL Global Ledger, `accountPurposeCode` y `entryDetail` —
  http://www.xbrl.org/int/gl/2007-04-17/glframework-rec-2007-04-17.htm
- SAF-T de la OCDE, `StandardAccountID` y el mapeo al plan nacional: documentación noruega —
  https://www.skatteetaten.no/globalassets/bedrift-og-organisasjon/starte-og-drive/rutiner-regnskap-og-kassasystem/saf-t-regnskap/norwegian-saf-t-financial-data---documentation.pdf
- SAF-T, mapeo del plan de cuentas a las cuentas estándar (ejemplo de implementación) —
  https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_158945469233.html

**Dentro de este repositorio** (no son fuentes externas; son dónde vive cada cosa que el documento cita)

- Los seis roles y su gobierno: `estandar/catalogos.json`, `contaperu/vocabulario.py`, `estandar/LEEME.md`
  («Quién gobierna los catálogos»)
- Los dos ejes `rol` y `clase`: `API-DE-REGISTRO.md` («El papel de cada línea»), con «Cómo lo resuelve el mundo» y
  «Lo que se descartó, y por qué»
- La derivación de la clase: `contaperu/pcge/clases.py`
- Las seis llamadas que escriben el rol: `contaperu/asiento/motor.py`
- Las ocho ranuras de cuenta y sus tres capas: `contaperu/configuracion.py`, `contaperu/drivers/contrato.py`,
  `contaperu/drivers/*/datos.py`
- La huella y lo que excluye: `contaperu/asiento/huella.py`
- Los proyectos abiertos ya investigados: `INTEROPERABILIDAD.md` («Modelos de referencia: ERPs abiertos, ledgers y
  estándares»)
