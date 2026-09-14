# Interoperabilidad: lo que enseña lo abierto, y cómo entrarían el banco y las facturas de proveedores

## 0 · Por qué este documento

[REFERENCIAS.md](REFERENCIAS.md) (11-sep-2026) miró **lo cerrado**: la API de QuickBooks Online, la de Xero y las
APIs unificadas de EE. UU. (Merge, Codat, Rutter, Apideck). De ahí salieron `EXIGE` en el contrato de driver,
`pedir_a` en `diagnosticar`, la huella de `_exportacion` y los nombres reservados del estándar. Este documento es su
continuación y mira **lo abierto**:

- los proyectos de código abierto que resuelven el mismo problema: ERPs, *ledgers*, APIs unificadas abiertas e
  importadores;
- los estándares que ya definen cómo se traza un asiento: el PLE de SUNAT, SAF-T, XBRL GL, EN 16931 e ISO 20022;
- la especificación MCP en sus revisiones de 2025 y 2026;
- dos entradas que el motor todavía no tiene: **el banco** (cuando la contabilidad empieza con un cargo o un abono en
  la cuenta) y **las facturas de proveedores** (cómo llegan hasta el sistema contable).

**Estado: investigación.** Nada de lo que aquí se propone está en la librería 0.10.0 ni en `open-accounting` 0.3. El
proyecto crece con una regla —se afina lo que existe y el estándar crece con casos reales, no por si acaso—, así que
este documento es una **hoja de ruta condicionada**: cada propuesta dice qué caso real la destraba y qué test la
fijaría, y la tabla del §9 las ordena por lo que les falta.

**Lo que no cambia**, y ordena todas las propuestas: el motor no lee PDFs ni fotos, no se conecta a SUNAT ni a ningún
banco, y no guarda nada ([README.md](README.md), «Qué no hace»). Conectarse, recibir correos, leer con IA, aprender
del historial y guardar el estado de una conciliación es trabajo **de la aplicación que consume el motor**. El motor
lee formatos, propone con motivo y arma asientos, siempre como funciones puras.

**Convenciones del documento.**

| Marca | Significado |
|---|---|
| **N** · **D** · **F** · **A** | Nivel donde vive una pieza: **N**úcleo, **D**river, **F**achada o puerta MCP, **A**plicación que consume el motor |
| `nombre*` | Nombre provisional, a decidir por el mantenedor antes de entrar en el código |
| *no verificado* | No se confirmó en una fuente primaria |
| *según terceros* / *según el proveedor* | La fuente es secundaria o es el propio fabricante |
| `ruta:línea` | Código de este repositorio en la 0.10.0 |

Fuentes consultadas el 13-sep-2026. Las URL van junto a cada hallazgo y agrupadas en el §10.

---

## 1 · Proyectos abiertos y modelos canónicos del libro mayor

### Qué hacen

Todos resuelven lo mismo: representar una partida doble sin atarse a un plan de cuentas ni a un ERP concreto. Y la
mayoría separa **tres identidades** que un modelo ingenuo mezcla: el **id técnico** del asiento, el **número de
negocio** del documento que lo soporta y el **puntero a la línea de origen**. Además, la mayoría guarda el
**motivo** de la línea aparte de la cuenta.

| Proyecto | Id técnico del asiento | Número de negocio | Puntero al origen | Motivo aparte de la cuenta | Cómo corrige |
|---|---|---|---|---|---|
| **PLE 5.1, Libro Diario** ([RS 169-2015/SUNAT, Anexo 2](https://spij.minjus.gob.pe/Graficos/Peru/2015/Junio/30/RS-169-2015-SUNAT-ANX-2.pdf)) | Campo 2, **CUO**: «llave única o clave única o clave primaria del software contable que identifica de manera unívoca el asiento contable» | Campos 10-12: tipo, serie y número del comprobante | Campo 20, **dato estructurado**: código del libro & periodo & CUO & correlativo del Registro de Ventas o de Compras | Campo 3: prefijo del correlativo A (apertura), M (movimiento), C (cierre) | Campo 21, estado: 1 del periodo, 8 de un periodo anterior no anotado, 9 corrige uno ya anotado con su CUO original |
| **SAF-T** ([XSD noruego 1.10, derivado del de la OCDE](https://raw.githubusercontent.com/Skatteetaten/saf-t/master/Norwegian_SAF-T_Financial_Schema_v_1.10.xsd)) | `SystemID` | `TransactionID` | `SourceDocumentID` y `RecordID` por línea | — | `CrossReference`: documentos conciliados |
| **XBRL GL** ([anexo del estándar estonio basado en XBRL GL 2015](https://wp.itl.ee/wp-content/uploads/2021/02/ANNEX-I-XBRL-GL-accounting-entry-data-standard.pdf)) | `entryHeader@id` | `documentNumber`, `documentType` | `documentReference`; hacia delante, `documentApplyToNumber` | `sourceJournalID` = el **diario**, equivalente a nuestro sub-diario (no al rol); `amountMemo` marca una línea informativa | — |
| **ERPNext** ([`GL Entry`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/gl_entry/gl_entry.json)) | `name` | `voucher_type` + `voucher_no` | `voucher_detail_no` (la fila del documento); hacia delante, `against_voucher` | — | `is_cancelled`; con [libro inmutable](https://docs.frappe.io/erpnext/user/manual/en/immutable-ledger-in-erpnext), la cancelación se asienta en su propia fecha |
| **Odoo 18** ([`account.move.line`](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_move_line.py)) | `id`, más `inalterable_hash` y secuencia sin huecos | `name` del `account.move` | `move_id`; `matched_debit_ids` hacia la conciliación | `display_type` (product, tax, payment_term…) ≈ nuestro `rol` | `reversed_entry_id` ([`account.move`](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_move.py)) |
| **TigerBeetle** ([Transfer](https://docs.tigerbeetle.com/reference/transfer/)) | `id` (u128; es la clave de idempotencia) | `user_data_128` (quién/qué) | `user_data_64`, `user_data_32` | `code`: «why» | Inmutable: se corrige con transferencias nuevas |
| **Formance Ledger** ([API v2](https://raw.githubusercontent.com/formancehq/ledger/main/openapi/v2.yaml)) | `id` y `reference` («unique within the ledger») | `metadata` | `metadata` | Numscript | `revert`, con `atEffectiveDate` opcional |
| **Beancount / beangulp** ([sintaxis](https://beancount.github.io/docs/beancount_language_syntax/)) | — (texto plano, con `filename` y `lineno`) | metadatos libres | links `^` para unir factura y pago | — | Otra transacción |
| **Panora** ([modelo unificado](https://raw.githubusercontent.com/panoratech/Panora/main/packages/api/src/accounting/journalentry/types/model.unified.ts)) · **Nango** ([records](https://nango.dev/docs/reference/api/sync/records-list)) | `id` propio | `remote_id` | `remote_data` | — | Nango: `_nango_metadata.last_action` ADDED\|UPDATED\|DELETED y `deleted_at` |
| **OCA `edi_oca`** ([`edi.exchange.record`](https://raw.githubusercontent.com/OCA/edi-framework/17.0/edi_oca/models/edi_exchange_record.py)) | `identifier` | `external_identifier` | `model` + `res_id`, `parent_id` | Tipo de intercambio | Estados del intercambio y `ack_exchange_id` |
| **Apache Fineract** ([documentación](https://fineract.apache.org/docs/legacy/)) | `transactionId` | `referenceNumber` | `entityType` | Reglas contables y *financial activity mappings* por producto | `command=reverse` |
| **EN 16931 / UBL** ([BT-19 y BT-133](https://github.com/ConnectingEurope/eInvoicing-EN16931/issues/270)) | — | BT-1, número de factura | — | BT-19 / BT-133 «Buyer accounting reference» (`cbc:AccountingCost`): el vendedor envía la referencia contable **del comprador** | Nota de crédito |

Tres patrones se generalizan:

- **La identidad es una tupla, no un número.** Hacia atrás, (documento, número, fila); hacia delante, (documento que
  se liquida). Nadie usa el correlativo del diario como identidad, porque se reasigna.
- **El motivo va aparte de la cuenta.** La cuenta la elige cada empresa; el motivo (el IGV, el tercero, la comisión)
  es lo que otro sistema necesita para traducir sin adivinar.
- **Las importaciones tienen un protocolo.** El `Importer` de [beangulp](https://raw.githubusercontent.com/beancount/beangulp/master/beangulp/importer.py)
  separa `identify(filepath)`, `extract(filepath, existing)` y `deduplicate(entries, existing)`, y marca los repetidos
  con `__duplicate__` usando una ventana de fechas ([extract.py](https://raw.githubusercontent.com/beancount/beangulp/master/beangulp/extract.py)).
  Es la simetría, del lado de la entrada, de lo que en ContaPerú es el contrato de driver.

### Qué hace ContaPerú hoy

| Identidad | Hoy | Dónde |
|---|---|---|
| Número de negocio | `documento.serie_numero` en cada línea; `Comprobante.clave` = (tipo, serie, número sin ceros, documento de la contraparte) | `contaperu/asiento/motor.py:126-127`, `contaperu/modelo.py:300` |
| Id técnico en el destino | (mes, sub-diario, correlativo): lo numera el motor desde el punto de partida que da quien llama, y **cambia al re-exportar** | `contaperu/asiento/resolucion.py:306`, `contaperu/asiento/huella.py:13-15` |
| Puntero al origen | No existe: la línea no dice de qué comprobante salió más allá de su serie-número | `contaperu/asiento/lineas.py` |
| Motivo | `rol`: `principal`, `igv`, `retencion_4ta`, `tercero`, `detraccion_tercero`, `detraccion` | `contaperu/asiento/motor.py` |

### Qué tomar

Ningún modelo nuevo. `open-accounting` ya separa el motivo de la cuenta —el `rol` no lo tiene ninguna de las APIs
comparadas en `REFERENCIAS.md`— y ya transporta lo que no entiende (`datos_originales`). Las dos identidades que
faltan se resuelven **sin tocar la línea**, con el índice por comprobante del §3. El protocolo de beangulp se usa en
el §5, cuando exista el primer lector de un extracto bancario.

---

## 2 · Validación contextual antes de proyectar

### Qué hacen

`REFERENCIAS.md` §3 ya recoge la idea base: Codat `GET …/options/{dataType}` y Merge `/meta` dicen qué exige el destino
antes de escribir. Lo nuevo está en **dónde se evalúa** la exigencia:

- **ERPNext** declara por empresa qué dimensiones son obligatorias según el tipo de cuenta
  ([`Accounting Dimension Detail`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/accounting_dimension_detail/accounting_dimension_detail.json):
  `mandatory_for_pl`, `mandatory_for_bs`, `default_dimension`), y qué valores permite o restringe cada cuenta
  ([`Accounting Dimension Filter`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/accounting_dimension_filter/accounting_dimension_filter.json):
  `allow_or_restrict`, `accounts`, `dimensions`). El rechazo es por línea: «Cost Center is required for 'Profit and
  Loss' account» ([`gl_entry.py`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/gl_entry/gl_entry.py)).
- **Odoo 18** lo hace por prefijo de cuenta, con puntuación: `account.analytic.applicability` marca un plan analítico
  como `optional|mandatory|unavailable` según `account_prefix` y `business_domain` (factura, compra), y
  `account.analytic.distribution.model` pone valores por defecto por socio, prefijo de cuenta o producto
  ([analytic_plan.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/analytic/models/analytic_plan.py),
  [account_analytic_plan.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_analytic_plan.py),
  [analytic_distribution_model.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/analytic/models/analytic_distribution_model.py)).
- **Codat** devuelve un esquema recursivo `{type, displayName, required, properties, validation{warnings, information},
  options[]}` y, al escribir, `validation.errors[{itemId, message, validatorName}]` ([push](https://docs.codat.io/using-the-api/push)).
- **Merge** tiene esquemas que dependen de una elección previa: con `has_conditional_fields`, `/meta` se llama dos
  veces, primero para elegir la plantilla y después para saber sus campos
  ([plantillas y campos condicionales](https://docs.merge.dev/merge-unified/writing-data/programmatic-writes-with-meta/templates-and-conditional-fields)).

El patrón: **la exigencia se evalúa por línea contra su cuenta**, no por destino entero. Cuando falta el dato, el orden
habitual es: valor por defecto configurado → mapeo → aviso → pedirlo.

### El hallazgo peruano que ordena esta sección

La plantilla oficial de importación de CONCAR, transcrita en este repositorio y verificada contra el archivo, dice lo
mismo que ERPNext y Odoo, **y lo dice por cuenta** (`contaperu/drivers/concar/datos.py:77-103`):

| Columna | Nota literal de la plantilla |
|---|---|
| K · Cuenta Contable | «Debe existir en el Plan de Cuentas» |
| L · Código de Anexo | «Si Cuenta Contable tiene seleccionado Tipo de Anexo, debe existir en la tabla de Anexos» |
| M · Centro de Costo | «Si Cuenta Contable tiene habilitado C. Costo, Ver T.G. 05» |
| R-T · Documento | «Si Cuenta Contable tiene habilitado el Documento Referencia» |
| U · Vencimiento | «Si Cuenta Contable tiene habilitada la Fecha de Vencimiento» |
| V · Área | «Si Cuenta Contable tiene habilitada el Area» |
| Y · Medio de Pago | «Si Cuenta Contable tiene habilitado Tipo Medio Pago» |
| AI-AL · Tasa | «Si la Cuenta Contable tiene configurada la Tasa» |

Y el motor ya lo reconoce: `lleva_centro` explica que «en CONCAR la marca "C. Costo habilitado" vive en cada cuenta del
plan; aquí se declara por prefijo en `cuentas_con_centro`» (`contaperu/asiento/resolucion.py:190-202`). **El prefijo es
un sustituto de un dato que existe en el destino.**

### Qué hace ContaPerú hoy

- Cada driver declara `EXIGE`: CONCAR `{"centro_costo", "moneda"}` (`contaperu/drivers/concar/datos.py:21`), CONTASIS
  `{"cuenta_unica"}` (`contaperu/drivers/contasis/datos.py:24`) y el CSV nada (`contaperu/drivers/csv/__init__.py:33`).
  `contrato.exige()` le suma lo que el núcleo exige a su familia (`contaperu/drivers/contrato.py:155`).
- Una sola tabla de faltas (`FALTAS`, `contaperu/asiento/faltas.py:121`) alimenta las dos caras: `faltantes_para`
  describe sin lanzar y `exigir_requisitos` lanza antes de llamar al driver (`contaperu/asiento/resolucion.py:271`,
  `:293`).
- `centro_costo` falta solo si la cuenta lo lleva, y eso se decide por prefijo (`cuentas_con_centro`, de fábrica
  `["63", "65", "70"]`, `contaperu/configuracion.py:289`). La lista `centros_costo` se declara
  (`contaperu/configuracion.py:280`) pero el motor no comprueba contra ella.
- **La cadena de resolución de una cuenta es corta:** la imputación del documento, si no la cuenta general
  (`cuentas.gasto` o `cuentas.ventas`), y si no la falta `sin_cuenta` (`contaperu/asiento/resolucion.py:92`). No hay
  valor por defecto por prefijo ni por proveedor. Lo que una aplicación sepa de un proveedor lo mete ella en la
  imputación.
- El PCGE 2026 se consulta, pero no valida (`contaperu/pcge/catalogo.py`), y **nada comprueba que una cuenta exista en
  el plan del destino**. Hoy ese error aparece recién al importar el Excel en CONCAR.
- `generar_asiento` no llama a `exigir_requisitos` (`contaperu/operaciones.py:323-345`): sus líneas pueden salir sin
  centro de costo aunque el destino sea CONCAR. Es coherente con que sean «líneas de diario del estándar, sin formato de
  ningún ERP», pero conviene decidirlo explícitamente (pregunta abierta del §9).

### Qué tomar

**1. El plan de cuentas del destino como dato** (`plan_de_cuentas*`, nivel **N** para comprobar y **D** para leerlo).
Una forma neutral, `{codigo: {centro_costo: bool}}`, que la aplicación obtiene del plan exportado de su CONCAR y el
driver traduce. Solo `centro_costo` tiene hoy un caso: el que ya resuelve `lleva_centro`. Las demás marcas de la
plantilla (anexo, documento, vencimiento, área, medio de pago, tasa) entran cada una con el suyo.

**2. Una falta nueva, `cuenta_fuera_del_plan*`, bajo el requisito de núcleo `cuenta_contable`.** Así bloquea en todo
destino que lleva cuentas sin tocar el `EXIGE` de nadie. Se comprueban **todas las cuentas que el destino escribiría**,
no solo la de la imputación: una cuenta de IGV o de proveedores que no existe rechaza igual. `pedir_a` es `contador`
si la cuenta sale de la imputación y `sistema` si sale de la configuración, con el mismo criterio que ya usa
`PEDIR_A` (`contaperu/operaciones.py:50-69`).

**3. `lleva_centro` lee la marca cuando hay plan y el prefijo cuando no.**

**4. El mismo circuito que la imputación.** El plan no cabe dentro de `configuracion`: `errores_de_configuracion`
rechaza con razón las claves que no conoce (`contaperu/operaciones.py:151-153`). Llega como argumento de la fachada
—en `diagnosticar`, `exportar` y `generar_asiento`, los tres a la vez, para que «listo» signifique lo mismo que «se
exporta»— y viaja al núcleo bajo una clave reservada, igual que `imputaciones` (`contaperu/operaciones.py:203`).

```
documento ──► comprobantes ──► detracciones.normalizar ──► validar.revisar(…, claves_previas*)
configuracion ──► errores_de_configuracion ──► config_aplicada(driver)
imputacion ────► con_imputacion ──┐
plan_de_cuentas* ► con_plan* ─────┴──► config { imputaciones, plan_de_cuentas* }
                                             │
                     faltantes_para(comprobantes, config, exige(driver))
                       sin_sigla · sin_codigo_de_moneda · reparto_no_admitido · sin_cuenta ·
                       cuenta_fuera_del_plan* · reparto_que_no_cuadra · sin_centro (marca* | prefijo)
                             ┌───────────────┴────────────────┐
                    describe (no lanza)                 hace cumplir (lanza)
             diagnosticar → que_falta[].pedir_a    exigir_requisitos → NoExportable → driver
```

```python
# núcleo · asiento/resolucion.py — pseudocódigo, nombres provisionales
def lleva_centro(cuenta: str, config: dict) -> bool:
    if not config.get("usa_centros_costo", True):
        return False
    plan = config.get("plan_de_cuentas")                 # clave reservada, como "imputaciones"
    if plan is not None:                                 # la marca del destino manda
        return bool((plan.get(cuenta.strip()) or {}).get("centro_costo"))
    ...                                                  # lo de hoy: cuentas_con_centro por prefijo

def cuentas_fuera_del_plan(comprobantes, config, es_venta=False) -> list[Comprobante]:
    plan = config.get("plan_de_cuentas")
    if plan is None:                                     # sin plan no se comprueba, y diagnosticar lo dice
        return []
    def escribiria(c):                                   # las mismas cuentas que resuelve el asiento
        return [cuenta for cuenta, _centro, _importe in partes_de(c, config, es_venta)] + \
               [cuenta_tercero(c, config, es_venta)]     # + IGV, detracción… según el libro
    return [c for c in comprobantes if any(cta and cta not in plan for cta in escribiria(c))]
```

**5. En la puerta MCP**, `diagnosticar` publica su forma con `outputSchema`. Tiene que cubrir también la respuesta
temprana cuando la configuración es inválida (`_sin_configuracion`, `contaperu/operaciones.py:455`). Ver §7.

**Caso real que lo destraba:** la nota K de la plantilla, más un error de importación de CONCAR por una cuenta
inexistente. *No verificado:* qué hace exactamente CONCAR al importar una cuenta, un anexo o un centro que no existen
(la plantilla dice «debe existir», no si rechaza la fila o el archivo).

**Tests que lo fijarían:**
- Con un plan que no tiene la cuenta: `listo_para_exportar` es falso, `pedir_a` es `contador` y `exportar` lanza la
  excepción nueva.
- Sin plan: el snapshot de CONCAR sale idéntico.
- Una 63 con `centro_costo: false` en el plan no bloquea. Si `lleva_centro` ignora el plan, el test cae (mutación).

**Qué no:** un lenguaje de requisitos declarativos (`aplica_si{familia, libro, prefijo, rol}` con niveles). ERPNext y
Odoo lo necesitan porque ellos *son* el destino; ContaPerú escribe hacia un destino que ya guarda esa exigencia en su
plan. Tomar el dato es más corto y no inventa reglas (§8).

---

## 3 · Trazabilidad y referencias de registro

### Qué hacen

- **Hacia atrás**, del asiento al documento: ERPNext guarda hasta la fila (`voucher_detail_no`), SAF-T el documento
  por línea (`SourceDocumentID`) y el PLE 5.1 el registro de origen en el campo 20. En los registros, el CUO «debe ser
  el mismo consignado en el Libro Diario» ([Anexo 2](https://spij.minjus.gob.pe/Graficos/Peru/2015/Junio/30/RS-169-2015-SUNAT-ANX-2.pdf)):
  **el enlace va en los dos sentidos**.
- **Hacia delante**, de la factura a lo que la liquida: ERPNext `against_voucher` y su subledger
  [`Payment Ledger Entry`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/payment_ledger_entry/payment_ledger_entry.json)
  (con `delinked`); Odoo `account.partial.reconcile`, una tabla muchos-a-muchos con importe parcial entre líneas;
  XBRL GL `documentApplyToNumber`; el `Assignment` de [python-accounting](https://github.com/ekmungai/python-accounting).
- **Agrupar sin pisar:** el PLE prohíbe consolidar en el Libro Diario («No se permite la consolidación de
  operaciones») y, donde la admite —el Registro de Inventario Permanente Valorizado—, exige añadir al CUO «un número
  secuencial separado de un guión» y conservar el detalle ([RS 042-2018/SUNAT, anexo](https://www.sunat.gob.pe/legislacion/superin/2018/anexo-042-2018.pdf)).
- **Borrados como lápidas:** Codat `metadata.isDeleted` y la distinción entre `modifiedDate` (en Codat) y
  `sourceModifiedDate` (en el sistema de origen) ([modified dates](https://docs.codat.io/using-the-api/modified-dates));
  Merge `remote_was_deleted` ([journal entries](https://docs.merge.dev/accounting/journal-entries/)).

### Qué hace ContaPerú hoy

- Cada línea lleva `documento` —sigla, `tipo_cp`, serie-número, fechas— y, en notas, `referencia` al documento que
  corrige (`contaperu/asiento/motor.py:126-134`). La línea de la detracción apunta a su factura por `referencia`.
- **La unión línea → comprobante no es directa.** `contraparte_doc` va solo en las líneas de tercero y de detracción;
  el `serie_numero` de la línea sale formateado según el driver, mientras que `Comprobante.clave` quita los ceros; y
  `generar_asiento` devuelve el libro y las líneas, no los comprobantes (`contaperu/operaciones.py:342`). Hoy las
  líneas de un comprobante se reconocen por `(sub_diario, correlativo)`, que cambia al re-exportar.
- **La huella es por tanda** (`contaperu/asiento/huella.py:34-41`): el sha256 de todas las líneas, sin el correlativo.
  Responde bien a «¿esta tanda ya salió?», pero no a la pregunta que de verdad cuesta. Si una tanda lleva los
  comprobantes A y B y la siguiente lleva B y C, las huellas son distintas, B se importa dos veces y CONCAR la suma.
- El CSV se ofrece como la salida «más honesta», buena «para escribir un driver nuevo teniendo delante lo que hay que
  traducir» (`contaperu/drivers/csv/__init__.py:3-6`), pero sus columnas no llevan `rol` ni los `tipo_cp`
  (`contaperu/drivers/csv/__init__.py:41-65`): justo lo que un driver necesita para no adivinar.
- Ningún driver consolida: CONCAR escribe una fila por línea neutral y un asiento por comprobante.

### Qué tomar

**1. Un índice por comprobante como anotación** (`_asiento.comprobantes*`, y lo mismo en `_exportacion`; nivel **F**).
Las claves `_` solo valen en la raíz del documento (`estandar/LEEME.md`, «Anotaciones que produce el motor»), así que el
índice va ahí y **no toca la línea, ni el esquema de línea, ni el snapshot**:

```python
# fachada · generar_asiento / exportar — las líneas no cambian; solo se anota dónde empieza y acaba cada comprobante
# (lineas_del_libro ya arma las líneas comprobante por comprobante, contaperu/asiento/motor.py:208)
indice, lineas = [], []
for c in comprobantes:                                    # en el orden del libro
    propias = lineas_del_comprobante(c, …)                # las mismas de hoy
    indice.append({
        "id_externo": c.id_externo or None,               # la llave de la aplicación
        "clave": [libro.ruc, libro.tipo, *c.clave],       # la identidad estable (punto 2)
        "lineas": [len(lineas), len(lineas) + len(propias) - 1],
        "huella": huella(propias),                        # la MISMA fórmula, por comprobante
    })
    lineas += propias
salida["_asiento"]["comprobantes"] = indice               # huella(lineas) de la tanda: intacta
```

**2. La identidad estable** = `libro.ruc` + `libro.tipo` + `Comprobante.clave`, **sin el periodo**: un comprobante se
anota una sola vez por RUC (`DUPLICADO_PERIODO_ANTERIOR`, el error 452 de SUNAT, `contaperu/validar.py:211-227`), así que
la misma clave sirve también para detectar duplicados entre periodos. Es legible y no necesita un hash nuevo.

- **Cumple el papel que el PLE le da al CUO, pero no es el CUO.** El CUO lo pone el software contable que genera el
  libro; en el flujo de hoy ese software es el destino (CONCAR), no ContaPerú. El análogo del lado del SIRE es el CAR
  (*no verificado*: su composición exacta).
- **En ventas la contraparte sobra.** La serie-número del emisor ya es única, y un RUC de cliente mal escrito partiría
  la identidad en dos. `comparar_sire.py` toma la misma decisión por la misma razón (`contaperu/comparar_sire.py:70-73`).
  Decidirlo es parte de la propuesta.
- Para un destino que importa archivos, el id en el destino es (mes, sub-diario, número), que el motor ya devuelve en
  `_asiento.sub_diarios` (`contaperu/operaciones.py:343`). Por eso el `id_externo` reservado para la **línea** no tiene
  todavía caso con CONCAR: lo tendrá el primer destino con API.

**3. Hacia delante: una tabla de asignación** (`aplicaciones*`: `[{movimiento, clave, importe}]`, con parciales). Es la
salida de la conciliación del §5, y sigue a `account.partial.reconcile` y a `Payment Ledger Entry`.

**4. Cómo sigue un agente una línea hasta su papel.** Sin base de datos, con lo que ya viaja:

```
_asiento.comprobantes[k] ── lineas[i..j] ──► asiento[i..j]
        │ id_externo · clave
        ▼
comprobantes[] del documento de ENTRADA (generar_asiento no lo devuelve: el agente o la aplicación lo conserva)
        │ origen · archivo_nombre · datos_originales (el UBL leído, o la fila cruda del SIRE)
        ▼
el XML o la fila de la propuesta, que guarda la aplicación
```

**Caso real que lo destraba:** tandas de CONCAR que se solapan, que la huella por tanda no detecta, y el comprobante
que cambió después de exportarse (§4).

**Tests que lo fijarían:**
- Los rangos del índice cubren `0..n-1` sin huecos ni solapes.
- Las líneas de cada rango cuadran solas.
- El literal de `tests/test_huella.py:24` no cambia.
- Otro punto de partida del correlativo da la misma huella por comprobante; un céntimo da la misma clave con otra huella.

**Esperan un caso:** `trazas*`, la tabla fila-de-destino → líneas neutrales para el primer driver que consolide
(test: partición exacta e importes que suman); y `documento.id_externo` dentro de la línea, para el primer driver
`desde_lineas` que necesite el id del origen, que es lo único que ve (`contaperu/drivers/contrato.py`).

---

## 4 · Flujo de datos, inmutabilidad y concurrencia

### Qué hacen

- **Nunca se edita lo contabilizado; se revierte.** `REFERENCIAS.md` §5 ya lo recoge. Lo nuevo es que revertir obliga a
  elegir **la fecha**. ERPNext, con `enable_immutable_ledger`, asienta la cancelación en su propia fecha
  ([documentación](https://docs.frappe.io/erpnext/user/manual/en/immutable-ledger-in-erpnext)); Formance permite
  revertir en la fecha del original (`atEffectiveDate`) y separa la fecha del hecho (`timestamp`) de la de inserción
  (`insertedAt`); el PLE usa el estado 9 con el CUO original en vez de tocar el periodo cerrado.
- **La excepción controlada existe**, y tiene nombre: ERPNext
  [`Repost Accounting Ledger`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/repost_accounting_ledger/repost_accounting_ledger.json),
  sometible y limitado por `repost_allowed_types`.
- **Bloqueos en capas.** Odoo 18 tiene fechas de bloqueo por impuesto, venta, compra y ejercicio, y una `hard_lock_date`
  «irreversible and does not allow any exception»; las excepciones a las demás se registran con usuario, motivo y
  caducidad en `account.lock_exception` ([company.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/company.py),
  [account_lock_exception.py](https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_lock_exception.py)).
- **Integridad demostrable:** hash encadenado y secuencia sin huecos en Odoo
  ([inalterabilidad](https://www.odoo.com/documentation/18.0/applications/finance/accounting/reporting/data_inalterability.html))
  y en el log de Formance («SHA256 hash of the log entry, chained from the previous log»).
- **Concurrencia sin duplicados:** TigerBeetle usa el `id` del cliente como clave de idempotencia y encadena
  transferencias atómicas con el flag `linked` ([linked events](https://docs.tigerbeetle.com/coding/linked-events/)). El
  patrón *transactional outbox* garantiza que un mensaje sale solo si la transacción se confirma, y exige consumidores
  idempotentes ([microservices.io](https://microservices.io/patterns/data/transactional-outbox.html)). django-hordak
  llega a hacer cumplir el cuadre con un *trigger* en la base
  ([documentación](https://django-hordak.readthedocs.io/en/latest/hordak-database-triggers.html)).
- **Lo que se usó, congelado en el asiento:** ERPNext guarda en cada `GL Entry` el tipo de cambio de la transacción
  (`transaction_exchange_rate`) junto a los importes en cada moneda.

### Qué hace ContaPerú hoy

- **El núcleo no tiene problema de concurrencia, porque no tiene estado.** No sale a la red, no lee el entorno ni mira el
  reloj, y los tests lo hacen cumplir (`tests/test_frontera.py:75-106`). Dos matices:
  - **El disco no tiene test.** Leer datos empaquetados es aceptable (el catálogo del PCGE con `lru_cache`,
    `contaperu/pcge/catalogo.py:27`), pero `comparar_sire.leer` abre una ruta del usuario (`contaperu/comparar_sire.py:77-80`),
    que es trabajo de la puerta.
  - `validar.revisar` y `detracciones.normalizar` escriben sobre los comprobantes que reciben. En la fachada es seguro,
    porque cada llamada construye los suyos; no lo sería si una aplicación compartiera objetos entre hilos.
- **Las tres fechas ya existen.** La del hecho es `documento.fecha_emision`; la contable, `linea.fecha`, acotada al periodo
  (`contaperu/asiento/motor.py:114-119`); la de registro, `_exportacion.fecha`, que pone quien llama. SAF-T
  (`TransactionDate`, `GLPostingDate`, `SystemEntryDate`) y Formance son una tabla de equivalencias, no una propuesta.
- **El tipo de cambio ya va congelado en cada línea**, pero como `float` (`contaperu/asiento/motor.py:111`, y la tasa de
  la detracción en `:71`), contra la regla de `Decimal` de punta a punta.
- **El único contador compartido es el correlativo** por sub-diario y mes. El motor numera desde el punto de partida que
  le dan (`contaperu/asiento/resolucion.py:205`) y devuelve los rangos que usó, pero el contador vive en la aplicación:
  dos exportaciones simultáneas con el mismo punto de partida chocan en el destino.
- **Una tensión declarada.** `estandar/LEEME.md` («La detracción, que ocurre en dos tiempos») dice que, al pasar a
  `PAGADO`, «el asiento puede regenerarse con el número real». Si ese asiento ya se importó en un destino que suma,
  regenerarlo lo duplica, y la huella distinta impide reconocerlo. Hoy es una frase del documento, no código: el motor
  escribe siempre el número comodín (`NUMERO_DETRACCION_PENDIENTE`, `contaperu/asiento/configuracion.py:22`).

### Qué tomar

**1. Una tabla de decisión por comprobante**, con la identidad y la huella del §3. La consulta la aplicación, que es la
que recuerda qué exportó:

| ¿La identidad ya se exportó a ese destino? | ¿La huella es la misma? | Qué es | Qué se hace |
|---|---|---|---|
| no | — | nuevo | sale en la tanda |
| sí | sí | ya salió | no se repite |
| sí | no | cambió después de exportarse | **no se regenera**: lo resuelve el contador en el destino, con fuente (el análogo del estado 9 del PLE) |

**2. Corregir la frase del LEEME** sobre la detracción regenerada: cómo se resuelve el segundo tiempo (un asiento
complementario, un asiento del pago o la corrección en el destino) es una decisión contable con fuente y archivo real, y
el estándar no debe adelantarla.

**3. El tipo de cambio y la tasa de la detracción como texto en la línea**, con el `float` solo al escribir la columna.
Tiene costo, y hay que decirlo: la huella de toda tanda en dólares o con detracción cambia, y la fórmula es contrato
(`contaperu/asiento/huella.py:20-23`). Es un cambio de comportamiento que se anuncia en el `CHANGELOG`.

**4. La versión del motor en `_asiento` y `_exportacion`**, fuera de la huella: cuando un cambio de comportamiento se
anuncia, quien guardó una tanda necesita saber con qué versión salió.

**5. Para la aplicación, como orientación de ingeniería** (no hay fuente contable detrás):
- La fuente de verdad es una base relacional; lo exportado no se edita.
- La exportación y el rango de correlativos que consumió se registran **en la misma transacción, antes de entregar el
  archivo** (el outbox aplicado a un Excel).
- Solo se cachean **hechos inmutables**: el tipo de cambio publicado para una fecha, el plan de cuentas de una versión.
  Un diccionario en memoria basta a la escala de un estudio contable; un caché compartido (Redis) solo se justifica con
  varios procesos, y sigue siendo seguro solo porque lo cacheado no cambia. **Nunca** se cachean imputaciones ni
  configuración.

```
APLICACIÓN (con estado)                                   MOTOR (sin estado)
documentos · imputaciones · configuración ─────────────►  diagnosticar / exportar
claves ya anotadas ───────── claves_previas* ──────────►
plan del destino ──────────── plan_de_cuentas* ────────►
                              ◄──── bytes + _exportacion { huella, comprobantes*[clave, huella],
                                                           sub_diarios, motor* }
registra la exportación + el rango de correlativos (una transacción) ─► entrega ─► destino (SUMA)
```

---

## 5 · Cuando el proceso empieza en el banco

### Qué hacen: los formatos

| Formato | Qué es | Lo que sirve para conciliar |
|---|---|---|
| **ISO 20022 camt.052 / camt.053 / camt.054** | Mismo esqueleto: reporte intradía, extracto (con saldo obligatorio) y **aviso de cargo o abono**, que es el *push* | `Ntry/Amt`, `CdtDbtInd`, `Sts` (BOOK/PDNG/INFO), `BookgDt`, `ValDt`, `AcctSvcrRef`, `BkTxCd`, `TxDtls/Refs/EndToEndId`, `RltdPties`, `RmtInf/Ustrd` y `RmtInf/Strd` ([guía de mensajes camt.054 de Standard Chartered](https://www.sc.com/en/uploads/sites/66/content/docs/Standard-Chartered-ISO-20022-message-formatting-guideline-for-camt.054.pdf)) |
| **SWIFT MT940 / MT942** | Extracto diario / reporte intradía | `:61:` (fecha valor, D/C, importe, tipo, referencia del cliente, `//` referencia del banco) y `:86:` con subcampos en las variantes estructuradas ([Danske Bank](https://danskeci.com/-/media/pdf/danskeci-com/swift-mt/reconciliation/mt940_structured.pdf), [MT942](https://developer.huntington.com/enterprisepayments/docs/swift-mt942-intra-day)) |
| **BAI2** | Estándar de EE. UU. | Registro `16` de transacción con código de tipo ([Huntington](https://developer.huntington.com/enterprisepayments/docs/bai2)) |
| **OFX** | Descarga para pymes y particulares | `FITID`, el id único de la transacción y la llave antiduplicado ([especificación de FNB](https://www.online.fnb.co.za/rhelp_0_15/Downloads/Statement_File_Specifications/Statement_Type_-_OFX.pdf)) |

### Qué hacen: el push y el pull

- **Plaid Transactions Sync** ([API](https://plaid.com/docs/api/products/transactions/)): llega el webhook
  `SYNC_UPDATES_AVAILABLE`, se llama a `/transactions/sync` con el cursor guardado mientras `has_more`, se aplican
  `added`, `modified` y `removed`, y se guarda `next_cursor`. La lección que importa: **una transacción pendiente no se
  confirma, se reemplaza**. Sale en `removed` y la definitiva entra en `added` con otro `transaction_id` y
  `pending_transaction_id` apuntando a la anterior; el nombre y el importe pueden cambiar
  ([datos de transacciones](https://plaid.com/docs/transactions/transactions-data/)).
- **GoCardless Bank Account Data** cubre el EEE bajo PSD2, con bancos que limitan las consultas por día
  ([documentación](https://docs.gocardless.com/bank-account-data/overview)), y según su propia página tiene cerradas las
  altas nuevas ([aviso](https://bankaccountdata.gocardless.com/new-signups-disabled)).
- **Codat Bank Feeds** empuja transacciones bancarias **hacia** el software contable: una cuenta origen que el cliente
  mapea (`pending` → `linked`) y lotes de hasta 1000 transacciones con `pushOperation` asíncrono; en QuickBooks, «Success»
  no significa visible todavía ([crear la cuenta](https://docs.codat.io/bank-feeds/create-account),
  [enviar transacciones](https://docs.codat.io/bank-feeds/pushing-transactions)).
- **Xero Bank Feeds** (solo para entidades socias) recibe extractos con saldo inicial y final que deben cuadrar, y usa el
  `transactionId` de cada línea para detectar duplicados ([OpenAPI](https://github.com/XeroAPI/Xero-OpenAPI/blob/master/xero_bankfeeds.yaml)).
- **Open Banking UK** notifica con un único evento, `resource-update`, que no trae la transacción: solo dice «vuelve a
  leer» ([perfil de notificación de eventos](https://openbankinguk.github.io/read-write-api-site3/v3.1.10/profiles/event-notification-api-profile.html)).
  El *push* bancario, en la práctica, es un aviso más un *pull*.

### Qué hacen: los proyectos abiertos

- **Odoo**: cada línea de extracto crea al instante un asiento contra la **cuenta transitoria** del diario, y conciliar
  reemplaza esa línea por la contrapartida real
  ([documentación 17](https://www.odoo.com/documentation/17.0/applications/finance/accounting/bank/reconciliation.html),
  [`account_bank_statement_line.py`](https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/account_bank_statement_line.py)).
  Las reglas (`account.reconcile.model`) combinan etiqueta con `contains`/`match_regex`, rango de importe, socio,
  tolerancia de pago y un mapeo regex → socio ([código 17](https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/account_reconcile_model.py)).
  La edición 19 las simplificó; el detalle de qué se retiró es *según terceros*.
- **OCA** importa camt, camt.054, OFX y hojas de cálculo, y pone una restricción `unique(unique_import_id)`: «una
  transacción bancaria solo puede importarse una vez» ([bank-statement-import](https://github.com/OCA/bank-statement-import),
  [código](https://raw.githubusercontent.com/OCA/bank-statement-import/18.0/account_statement_import_base/models/account_bank_statement_line.py)).
  En la rama 18.0 no hay módulo MT940.
- **ERPNext** **no** asienta al importar: crea un `Bank Transaction` (Pending, Unreconciled, Reconciled, Settled) con
  `transaction_id` para duplicados y una tabla hija de pagos con el importe asignado
  ([documentación](https://docs.frappe.io/erpnext/user/manual/en/bank-transaction)). Su herramienta de conciliación
  puntúa de forma **aditiva y explicable**: uno más por referencia que coincide, por importe igual y por socio igual
  ([`bank_reconciliation_tool.py`](https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/bank_reconciliation_tool/bank_reconciliation_tool.py)).
- **Midday** empareja movimientos con los recibos de su bandeja con pesos (50 % *embedding*, 35 % importe, 10 % moneda,
  5 % fecha) y umbrales, y solo automatiza un patrón de comercio tras confirmaciones repetidas, *según su artículo*
  ([motor de conciliación](https://midday.ai/updates/automatic-reconciliation-engine/)).
- **Blnk** declara reglas `{field, operator, allowable_drift}` —la tolerancia en % para importes y en segundos para
  fechas— y estrategias `one_to_one`, `one_to_many` y `many_to_one`
  ([reglas](https://docs.blnkfinance.com/reconciliations/matching-rules),
  [estrategias](https://docs.blnkfinance.com/reconciliations/strategies.md)).
- **Deduplicación en el resto:** Actual Budget no admite dos veces el mismo `imported_id` y, sin id, busca importe, fecha
  cercana y beneficiario parecido ([importar](https://actualbudget.org/docs/transactions/importing/)); Firefly III
  combina un identificador externo con un hash
  ([detección de duplicados](https://docs.firefly-iii.org/references/data-importer/duplicate-detection/)).
- **Aprender sin estado en el motor:** `smart_importer` entrena un clasificador con las entradas ya existentes del libro
  y lo aplica al importar ([repositorio](https://github.com/beancount/smart_importer)); hledger usa reglas CSV con `if`
  por regex ([manual](https://hledger.org/1.40/hledger.html#csv)).

### Perú: lo confirmado y lo que no

**Confirmado:**
- **No hay *open finance* vigente.** La SBS está en su hoja de ruta y, según terceros, la regulación se espera hacia 2027
  ([IUPANA](https://iupana.com/2025/11/25/es-el-proyecto-mas-importante-que-tiene-la-sbs-dice-el-regulador-financiero-sobre-el-open-finance-en-peru/)).
  La interoperabilidad que impulsa el BCRP es **de pagos, no de datos de cuenta**
  ([BCRP](https://www.bcrp.gob.pe/sistema-de-pagos/interoperabilidad/estrategia-de-interoperabilidad-de-los-pagos-minoristas.html)).
- **Los movimientos llegan hoy por archivo.** El BCP ofrece Host to Host por SFTP con archivos de recaudación
  ([viabcp](https://www.viabcp.com/empresas/cobranzas-y-pagos/telecredito/host-to-host)) y anunció APIs de empresa con
  consulta de movimientos, *según terceros* ([ecommercenews](https://www.ecommercenews.pe/pagos-online/2026/bcp-optimiza-la-gestion-de-pagos-y-transferencias-de-empresas-con-apis-y-host-to-host.html/)).
  Hay agregadores que listan la banca de empresas peruana con un endpoint de movimientos, *según el proveedor*
  ([Prometeo](https://docs.prometeoapi.com/docs/per%C3%BA)).
- **Los sistemas contables peruanos concilian importando Excel** ([CONCAR CB](https://realsystems.com.pe/concar/concar-cb/),
  [Starsoft](https://www.starsoft.com.pe/prod_contabilidad.html)).
- **ITF:** 0,005 % (TUO de la Ley del ITF, DS 150-2007-EF, art. 10, con la tasa de la Ley 29667), retenido por las
  empresas del sistema financiero (art. 16) y deducible para el Impuesto a la Renta (art. 19)
  ([TUO](https://www.sunat.gob.pe/legislacion/itf/ds150_07.htm)).
- **Detracciones:** el depósito masivo se hace con un TXT por SOL
  ([orientación SUNAT](https://orientacion.sunat.gob.pe/02-deposito-de-detracciones-aspecto-generales)), y la constancia
  la genera SOL cuando el Banco de la Nación comunica el pago
  ([orientación SUNAT](https://orientacion.sunat.gob.pe/3145-03-constancia-de-deposito-de-detraccion-empresas)): **no
  hay un formato de máquina documentado para la constancia**.

**No confirmado:** que algún banco peruano entregue MT940 o camt; APIs públicas de movimientos de BBVA Perú, Interbank o
Scotiabank Perú; la cobertura de otros agregadores; el formato posicional del TXT de detracciones campo por campo.

### Qué hace ContaPerú hoy

- **Nada de banco.** Existen solo `condicion_pago` en el comprobante, `medio_pago` como configuración de CONTASIS (y
  reservado en el estándar) y la columna Y de CONCAR, que el motor no llena y que la plantilla exige cuando la cuenta
  tiene habilitado el medio de pago (§2).
- **La conciliación de constancias de detracción está pendiente de un archivo real** (`contaperu/detracciones.py:109-112`,
  [ARQUITECTURA.md](ARQUITECTURA.md) «Hoja de ruta»). Pero la mitad ya está: `diagnosticar` lista las detracciones que
  esperan constancia (`_detraccion_pendiente`, `contaperu/operaciones.py:405`), y el monto en soles enteros ya tiene su
  regla con fuente (`monto_detraccion`, `contaperu/detracciones.py:57`).
- **Dos trampas verificadas para un lector de extractos.** Un `.xlsx` empieza por `PK\x03\x04` y el lector lo toma por
  ZIP y lo desarma (`contaperu/lectores/archivos.py:56-58`, `:78-110`). Y un `.txt` es un archivo «auxiliar» que se ignora
  en silencio salvo que sea la propuesta del SIRE (`contaperu/lectores/archivos.py:26`, `:39-43`).

### Qué tomar

**1. El movimiento, con el vocabulario de camt** (`Movimiento*`, **N**). Es el formato más completo y el que otros
traducen; un Excel peruano se proyecta hacia él, no al revés:

```python
Movimiento* = {
    "cuenta_banco": "…", "moneda": "PEN", "importe": "1500.00",      # texto exacto, siempre positivo
    "sentido": "cargo|abono",
    "contabilizado": True,                  # BOOK/PDNG de camt — NO se llama `estado`: ya tiene tres sentidos
    "fecha_contable": "AAAA-MM-DD", "fecha_valor": "AAAA-MM-DD",
    "referencia_banco": "…",                # AcctSvcrRef / número de operación
    "referencia_extremo": "…",              # EndToEndId, si viene
    "contraparte": {"nombre": "…", "documento": "…", "cuenta": "…"},
    "descripcion": "…", "codigo_banco": "…",  # BkTxCd o el código propio del banco
    "datos_originales": {},                 # la fila cruda, que el motor transporta y no lee
}
```

**2. El primer lector es el archivo real de un banco peruano**, con la misma regla que un driver: un formato que nadie ha
entregado no se lee. Lo que haya que corregir en la clasificación de entradas (un libro de Excel antes que un ZIP, un TXT
de banco que no es auxiliar) entra con él.

**3. Primero se empareja y después se asienta** —como ERPNext, no como la cuenta transitoria inmediata de Odoo—, porque
el destino suma: con transitoria, cada movimiento produciría un asiento transitorio y otro de reclasificación, dos
importaciones por hecho. La cuenta transitoria queda como opción del contador para lo que siga sin pareja al cierre, y la
cuenta sale de la configuración, nunca del motor.

**4. Deduplicar** por la referencia del banco o, si falta, por una huella determinista (cuenta, fecha contable, importe,
descripción y ordinal dentro del día), como `FITID`, `unique_import_id` o `imported_id`. **Solo lo contabilizado se
propone**; lo pendiente informa y nada más (la lección de Plaid).

**5. `conciliar*`, una función pura** (**N**):

```python
def conciliar(movimientos: list[dict], pendientes: list[dict], reglas: dict) -> dict:
    """Propone parejas; no asienta ni guarda. Puntaje aditivo y explicable (como ERPNext): cada
    motivo suma y se dice. Los pesos y la tolerancia son provisionales y se calibran con el archivo real.
    `pendientes` y lo aprendido del historial llegan como datos desde la aplicación."""
    propuestas, sin_pareja, informativos = [], [], []
    for m in movimientos:
        if not m["contabilizado"]:
            informativos.append(m)
            continue
        candidatos = [evaluar(m, d, reglas) for d in pendientes]      # → {clave, puntaje, motivos[]}
        candidatos = [c for c in candidatos if c["puntaje"] >= reglas["umbral"]]
        (propuestas if candidatos else sin_pareja).append(
            {"movimiento": m["referencia_banco"], "candidatos": ordenar(candidatos)})
    return {"propuestas": propuestas, "sin_pareja": sin_pareja, "informativos": informativos}

# motivos legibles, por ejemplo:
#   "importe igual" · "importe dentro de la tolerancia" · "serie-número en la descripción"
#   "RUC de la contraparte en la descripción" · "número de operación citado en la factura"
#   "cuenta del Banco de la Nación y monto de detracción en soles enteros" (detracciones.monto_detraccion)
```

La cardinalidad no es teórica en el Perú: **una factura con detracción se paga con dos movimientos**, el neto al
proveedor y el depósito en el Banco de la Nación. Es el primer caso natural de aplicación parcial, y sale en la tabla
`aplicaciones*` del §3.

**6. El primer caso es `aplicar_constancias*`**, la operación sin estado que el estándar ya describe (`estandar/LEEME.md`,
«La detracción»): entra el documento con detracciones `PROVISIONADO` y el archivo de constancias, y sale el documento con
`PAGADO`, `nro_constancia` y `fecha_constancia`. Antes de diseñar su lector hay que ver **qué archivo real existe**, dado
que la constancia no tiene un formato de máquina documentado: una exportación de la consulta en SOL, el TXT del depósito
masivo u otro.

**7. El asiento de tesorería espera.** Es una regla contable nueva y necesita su fuente (las cuentas del PCGE y el ITF con
su norma) y un archivo aceptado del sub-diario de bancos de CONCAR, que probablemente pida el medio de pago.

**8. En la puerta MCP:** `leer_extracto*` y `proponer_parejas*`, cuando exista su lector.

```
BANCO · AGREGADOR · PORTAL ── Excel · TXT · H2H · API ──► APLICACIÓN: credenciales, cursor, reintentos, guarda lo crudo
                                                                │ bytes + nombre
┌───────────────────────────── MOTOR (puro) ────────────────────▼──────────────────────────────┐
│ identificar(nombre, datos) ──► lector del banco X [archivo real]   (un libro Excel no es un ZIP) │
│ movimientos ──► deduplicar(movimientos, referencias_previas ◄ APP) ──► nuevos                  │
│ conciliar(nuevos, pendientes ◄ APP, reglas) ──► propuestas · sin_pareja · informativos         │
└────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                     APLICACIÓN: el contador confirma ──► guarda parejas y aplicaciones*
                                             │
MOTOR: aplicar_constancias*(documento, constancias)  ◄── PRIMER CASO [archivo real]
       asiento de tesorería                           ◄── ESPERA: fuente + archivo aceptado del destino
                                             │
DRIVER concar: sub-diario de bancos, columna Y (medio de pago) ──► Excel que el destino SUMA
```

---

## 6 · Cómo entran las facturas de proveedores

### Qué hacen

- **Redes de factura electrónica.** Peppol usa el modelo de cuatro esquinas —emisor, su *access point*, el *access point*
  del receptor, receptor—, descubre al destinatario con SML y SMP y transporta BIS Billing 3.0, que es UBL 2.1 sobre
  EN 16931 ([e-rechnung-bund](https://e-rechnung-bund.de/en/faq/peppols-technical-solution-the-four-corner-model/),
  [BIS 3.0](https://docs.peppol.eu/poacc/billing/3.0/bis/)). **La red reparte la factura**: el receptor la recibe
  estructurada.
- **Correo.** Odoo crea facturas de proveedor desde un alias del diario de compras, avisa de duplicados y autocompleta
  desde la factura anterior del mismo proveedor ([vendor bills 17](https://www.odoo.com/documentation/17.0/applications/finance/accounting/vendor_bills.html));
  Xero da una dirección que crea **borradores** y solo acepta adjuntos
  ([Xero Central](https://central.xero.com/s/question/0D53m00009ditslCAA/where-do-i-find-my-xero-bills-email-address));
  QuickBooks lee lo reenviado y lo deja para revisar y emparejar con el banco
  ([Intuit](https://quickbooks.intuit.com/learn-support/en-us/help-article/accounts-payable/email-receipts-bills-quickbooks-online/L7r2LAQ7C_US_en_US));
  Midday tiene una bandeja con estados «emparejado», «sugerido» y «pendiente» ([documentación](https://midday.ai/docs/receipt-matching/)).
- **Extracción.** `invoice2data` usa plantillas YAML por emisor con campos obligatorios de fecha, importe y número
  ([repositorio](https://github.com/invoice-x/invoice2data)). El framework OCA `account_invoice_import` prefiere el XML
  estructurado (UBL, Factur-X), busca al proveedor por su identificador fiscal, guarda una configuración de importación
  por proveedor y, si ya hay un borrador, ofrece actualizarlo ([OCA/edi](https://github.com/OCA/edi),
  [README](https://github.com/OCA/edi/tree/12.0/account_invoice_import)).
- **APIs unificadas.** Codat exige que el proveedor exista antes de crear la factura y ofrece opciones de mapeo por
  conexión ([bills](https://docs.codat.io/payables/sync/bills)); Merge escribe la factura de proveedor como `Invoice` con
  `type=ACCOUNTS_PAYABLE` ([invoices](https://docs.merge.dev/accounting/invoices/)).
- **El flujo común**, con sus estados reales: ingesta → formato (el XML estructurado gana al PDF) → duplicado → proveedor
  por identificador fiscal → cuenta sugerida → **borrador** → contabilizado → emparejado con el pago. En Odoo,
  `account.move.state` va de `draft` a `posted` o `cancel`; en ERPNext, `docstatus` 0/1/2
  ([`purchase_invoice.py`](https://github.com/frappe/erpnext/blob/develop/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py)).

### Perú: SUNAT liquida, pero no reparte

- El Perú tiene un modelo de **validación previa**: el OSE hace la comprobación, emite la constancia de recepción (CDR) y
  la envía a SUNAT ([OSE](https://cpe.sunat.gob.pe/informacion_general/operador_servicios_electronicos)); en SEE-Del
  Contribuyente el envío tiene su propio plazo ([SEE-Del Contribuyente](https://cpe.sunat.gob.pe/sistema_emision/see_contribuyente)).
  Los plazos se citan vigentes a la fecha de consulta. **Pero no hay una red que entregue el XML al receptor**: el CDR
  es la constancia del emisor, no del adquiriente.
- El emisor está obligado a **poner el comprobante a disposición del adquiriente en una página web durante un año**, y a
  conservar los que emite y los que recibe ([SEE-Del Contribuyente](https://cpe.sunat.gob.pe/sistema_emision/see_contribuyente)).
  En la práctica el XML llega por correo.
- La **propuesta del Registro de Compras en el SIRE** trae los **hechos** de lo que los proveedores informaron, no el XML.
- Hay OSE que ofrecen recepción por correo con portal de descarga; no encontramos una API pública documentada para esos
  servicios. La descarga en SOL del XML de los comprobantes recibidos se describe en fuentes de terceros, pero *no está
  verificada* en una fuente oficial (ni la norma, ni desde cuándo, ni para qué sistemas de emisión).

La consecuencia de diseño: **el canal práctico es una bandeja** —una dirección de correo por RUC, la subida manual o la
mensajería— y **la propuesta del RCE es la lista de control** de lo que debería haber llegado.

### Qué hace ContaPerú hoy

- **Identifica por bytes y extensión.** `expandir` desarma los ZIP y `convertir_xml` convierte los XML UBL 2.1 y la
  propuesta del SIRE; los PDF y las imágenes quedan en `pendientes_ia` para que los lea la aplicación
  (`contaperu/lectores/archivos.py:78-144`). Si el mismo comprobante llega como XML y como lectura de IA, **el XML gana**
  (`clave_orden`, `contaperu/lectores/archivos.py:147`).
- **La propuesta ya se lee como comprobantes** (`sire_txt.parsear`, `contaperu/lectores/sire_txt.py:171`), con la fila
  cruda en `datos_originales`.
- **`comparar_sire` compara TXT contra TXT, campo a campo**: el reemplazo generado contra la exportación del detalle de
  SUNAT (`contaperu/comparar_sire.py`). Nació de un contraste real.
- **Los duplicados entre periodos no llegan a la fachada.** `validar.revisar(…, claves_previas)` existe y produce
  `DUPLICADO_PERIODO_ANTERIOR` (`contaperu/validar.py:211-251`), y ese código tiene hasta su `pedir_a`
  (`contaperu/operaciones.py:57`). Pero la fachada llama siempre sin `claves_previas`, así que desde la CLI o el MCP ese
  error nunca se dispara.
- **`pedir_a: proveedor` está reservado** y nadie lo usa (`contaperu/asiento/faltas.py:19`, `contaperu/operaciones.py:22`).
- **Los ítems del UBL no se modelan**: del XML se toma solo la descripción de la primera línea como `concepto`
  (`contaperu/lectores/xml_ubl.py:240-242`).

### Qué tomar

**1. `claves_previas` en la fachada** (**F**): en `revisar`, `diagnosticar`, `exportar` y el MCP. La aplicación, que
recuerda lo que ya anotó, pasa sus claves; el motor ya sabe qué hacer con ellas.

**2. `cruzar_con_propuesta*`** (**N**, y **F** para exponerla). Compara un nivel más arriba que `comparar_sire`: entre
comprobantes y por su `clave`, porque los dos lados ya son comprobantes.

```python
def cruzar_con_propuesta(cargados: list[Comprobante], propuesta: list[Comprobante]) -> dict:
    """Pura. La propuesta del RCE es la lista de control; no corrige nada."""
    p = {c.clave: c for c in propuesta}
    q = {c.clave: c for c in cargados if not c.excluida}
    return {
        "en_los_dos": [{"clave": k, "diferencias": diferencias(q[k], p[k], ("total", "base_gravada", "igv"))}
                       for k in sorted(p.keys() & q.keys())],
        "solo_en_propuesta": [{"clave": k, "motivo": "falta el XML", "pedir_a": PROVEEDOR}      # primer caso real
                              for k in sorted(p.keys() - q.keys())],
        "solo_cargados": [{"clave": k, "motivo": "no está en la propuesta: validez o anulación", "pedir_a": CONTADOR}
                          for k in sorted(q.keys() - p.keys())],
    }
```

`solo_en_propuesta` es **el primer caso real de `pedir_a: proveedor`**: SUNAT dice que la factura existe, y quien tiene
el XML es el proveedor. En `solo_cargados`, la consulta de validez la hace la aplicación y el motor recibe el resultado
como dato. Qué observación dispararía ese dato entra con la documentación del servicio de validez como fuente.

**3. `sugerir_imputacion*`** (**N**). Es el análogo determinista de la configuración por proveedor de OCA y del
autocompletado de Odoo:

```python
def sugerir_imputacion(c: Comprobante, historial: list[dict], minimo: int = 2) -> dict:
    """historial ◄ APP: [{proveedor, cuenta_contable, centro_costo}] de lo ya revisado.
    Pura y determinista (conteo). Devuelve propuestas con motivo y NUNCA escribe la imputación:
    la decide el contador en la pantalla de revisión."""
    previas = [h for h in historial if h["proveedor"] == solo_digitos(c.contraparte_doc)]
    conteo = Counter((h["cuenta_contable"], h.get("centro_costo", "")) for h in previas)
    return {"id_externo": c.id_externo, "propuestas": [
        {"cuenta_contable": cuenta, "centro_costo": centro, "motivo": f"{n} de {len(previas)} de este proveedor"}
        for (cuenta, centro), n in sorted(conteo.items(), key=lambda x: (-x[1], x[0]))[:3] if n >= minimo]}
```

```
CANALES (APLICACIÓN): correo · subida · bandeja de un OSE · web del emisor          SIRE: propuesta del RCE
      │ bytes + nombre                                                                   │
MOTOR  expandir ─► convertir_xml ─► comprobantes (origen xml)          sire_txt.parsear ─► propuesta (origen sire)
      │               └─► pendientes_ia ─► APP: IA ─► comprobante (origen vision, confianza < 1)
      ▼
validar.revisar(…, claves_previas* ◄ APP)          el XML gana a la lectura por IA (clave_orden)
      ▼
cruzar_con_propuesta* ─┬─ en_los_dos: diferencias ─────────► contador
                       ├─ solo_en_propuesta ───────────────► pedir_a: proveedor
                       └─ solo_cargados ───────────────────► contador (validez: la consulta la APP)
      ▼
sugerir_imputacion*(c, historial ◄ APP) ─► propuestas con motivo
      ▼
APP · revisión: el contador decide ─► imputacion { id_externo: … }
      ▼
diagnosticar(…, plan_de_cuentas*) ─► exportar ─► CONCAR · CONTASIS · SIRE ─► §5: emparejar con el pago
```

**Caso real que lo destraba:** la propuesta del RCE, que el motor ya lee, y el contraste que dio origen a `comparar_sire`.

**Tests que lo fijarían:**
- Los tres cajones, con un caso en cada uno.
- Una clave con ceros a la izquierda casa con la misma sin ceros.
- Un RUC de proveedor mal escrito sale como uno solo en la propuesta más uno solo cargado, que es lo correcto en compras.
- `sugerir_imputacion` desempata de forma estable, respeta el mínimo y no toca la imputación.

**Qué no:**
- Leer `cbc:AccountingCost` (BT-19/BT-133). No hay evidencia de que los XML peruanos lo traigan, y el lector no lo lee.
  Queda como pista para cuando un XML real lo muestre, igual que la orden de compra (`cac:OrderReference`), cuya presencia
  en la guía de SUNAT *no está verificada*.
- Imputar por ítem de la factura: es un hueco declarado. Hoy lo cubre el reparto de la imputación.

---

## 7 · La arquitectura completa

```
APLICACIÓN · red · credenciales · IA · estado · pantalla de revisión
  correo y bandejas · IA de PDF y fotos · descarga del SIRE · servicio de validez · banco, agregador o H2H
  guarda: documentos · imputaciones · configuración · plan del destino · claves anotadas ·
          exportaciones (clave + huella + rangos de correlativo) · movimientos · parejas · historial por proveedor
      │ bytes        │ documento + configuracion + imputacion + claves_previas* + plan_de_cuentas*       │ bytes
══════▼══════════════▼═════════════════════════════════════════════════════════════════════════════════▼══════
3 · FACHADA Y PUERTAS · operaciones · servidor_mcp · cli
    hoy: leer_xml · leer_propuesta_sire · revisar · diagnosticar · generar_asiento · exportar · cuadrar · …
    *:   cruzar_con_propuesta · sugerir_imputacion · leer_extracto · proponer_parejas ·
         anotaciones MCP · outputSchema(diagnosticar) · [pedir lo que falta, cuando el SDK lo traiga]
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
2 · DRIVERS · concar (construir) · contasis (desde_comprobantes) · sire (linea) · csv (desde_lineas) · terceros
    *:        el plan exportado de CONCAR → forma neutral · el sub-diario de bancos          [archivo real]
──────────────────────────────────────────────────────────────────────────────────────────────────────────────
1 · NÚCLEO · sin red, disco, estado ni reloj
    lectores: xml_ubl · sire_txt · *extracto del banco X [archivo real]
    validar(claves_previas) · detracciones · *aplicar_constancias [archivo real]
    asiento: partes_de → faltantes_para(*plan) → FALTAS → motor → huella · *índice por comprobante
    *cruzar · *conciliar · *sugerir   (proponen con motivo; nunca deciden)
```

La regla que ordena el diagrama es la de siempre, extendida a las dos entradas nuevas: **cada flecha que cruza la línea
doble lleva datos, nunca una conexión**. Lo que el motor necesita saber del mundo —qué se anotó antes, qué plan tiene
el destino, qué movimientos llegaron, qué decidió el contador otras veces— se lo da la aplicación como argumento.

### La puerta MCP

**Qué dice la especificación.**

| Revisión | Lo que importa aquí | Fuente |
|---|---|---|
| **2025-06-18** | Salida estructurada (`outputSchema` + `structuredContent`), *elicitation*, enlaces a recursos en los resultados | [changelog](https://modelcontextprotocol.io/specification/2025-06-18/changelog) |
| **2025-11-25** | Tareas experimentales; *elicitation* por URL; los errores de validación de entrada son errores de herramienta, «to enable model self-correction» (SEP-1303); JSON Schema 2020-12 | [changelog](https://modelcontextprotocol.io/specification/2025-11-25/changelog) |
| **2026-07-28** | Sin estado (sin `initialize`); pedir datos al usuario pasa a viajar en la respuesta (`resultType: "input_required"` con un `requestState` que el servidor debe firmar y tratar «as attacker-controlled»); las tareas pasan a ser una extensión; *sampling*, *roots* y *logging* quedan obsoletos | [changelog](https://modelcontextprotocol.io/specification/2026-07-28/changelog), [MRTR](https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr), [SEP-2663](https://modelcontextprotocol.io/seps/2663-tasks-extension) |

Las anotaciones de herramienta son pistas, no seguridad: `readOnlyHint` vale falso por defecto, `destructiveHint`
verdadero, `idempotentHint` falso y `openWorldHint` verdadero, y «clients should never make tool use decisions based on
ToolAnnotations received from untrusted servers» ([schema.ts 2025-11-25](https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2025-11-25/schema.ts)).
En modo formulario, un servidor no debe pedir contraseñas ni credenciales
([elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation)).

**Cómo diseñan sus herramientas los servidores contables.** Xero (oficial) usa verbos `list-*`, `create-*` y `update-*`
([xero-mcp-server](https://github.com/XeroAPI/xero-mcp-server)). Intuit usa `{verbo}_{entidad}` y variables para apagar
escritura, actualización y borrado ([quickbooks-online-mcp-server](https://github.com/intuit/quickbooks-online-mcp-server)).
Apideck ofrece un modo dinámico de tres herramientas para catálogos grandes y un `--scope read|write|destructive`
([mcp](https://github.com/apideck-libraries/mcp)). Merge agrupa herramientas en paquetes y revisa datos personales antes
de devolverlos ([Agent Handler](https://docs.merge.dev/merge-agent-handler/overview)).

**Qué hace ContaPerú hoy** (`contaperu/servidor_mcp.py`): FastMCP, 11 herramientas y 5 recursos, transporte HTTP sin
estado (`stateless_http`, `:443`); ninguna herramienta escribe nada fuera de su respuesta. Comprobado en el SDK instalado
(`mcp` 1.30.0): `FastMCP.tool` acepta `annotations` y `structured_output`; las 11 herramientas tienen hoy ambas vacías;
las excepciones de una herramienta ya llegan al cliente como `isError`; y el protocolo más reciente que conoce es el
2025-11-25, sin `requestState`: **ese SDK no habla todavía 2026-07-28**.

| Herramienta | Anotaciones | `outputSchema` | Pedir lo que falta | Cuándo |
|---|---|---|---|---|
| Las 11 de hoy | `readOnlyHint: true`, `openWorldHint: false` (con `readOnlyHint` verdadero, `destructiveHint` e `idempotentHint` no significan nada) | — | — | Ya; subiendo el mínimo del pin `mcp>=1.2`, que no garantiza `annotations` (*no verificado*: en qué versión entró) |
| `diagnosticar` | las mismas | Sí, cubriendo también la forma `_sin_configuracion` | Con MRTR | Espera un SDK con 2026-07-28 |
| `exportar` | las mismas | No: devuelve el archivo como recurso embebido | — | Ya |
| Las nuevas (§2, §5, §6) | las mismas | Sí | — | Cada una cuando exista su función |

No se proponen tareas (todo es síncrono y hay un tope de 5.000 comprobantes, `contaperu/operaciones.py:33`), ni prompts, ni
*sampling*. *No verificado*: si la *elicitation* del SDK actual funciona con el transporte sin estado.

---

## 8 · Lo que no se toma, y por qué

- **Un lenguaje de requisitos declarativos** (ERPNext, Odoo). La exigencia del destino ya vive en su plan de cuentas, que
  es un dato (§2). Un DSL sin segundo caso sería una regla escrita por si acaso.
- **Numscript o cualquier lenguaje de reglas contables** (Formance). Las reglas viven en código, con su fuente al lado
  ([CONTRIBUTING.md](CONTRIBUTING.md)).
- **Importes en enteros de la unidad mínima** (TigerBeetle). El texto exacto con `Decimal` ya lo resuelve y no pierde la
  moneda de vista.
- **Log con hash encadenado, secuencia sin huecos, fechas de bloqueo.** Son estado: de la aplicación o del ERP de
  destino, nunca del motor.
- **La cuenta transitoria inmediata** (Odoo). El destino suma; primero se empareja (§5).
- **Modelos definidos por el usuario y *field mappings* por conexión** (Nango, Merge). El modelo lo define SUNAT
  (`REFERENCIAS.md`, «Lo que no se toma»), y dónde va cada dato ya lo resuelven `COLUMNAS_ELEGIBLES` y la configuración
  por sistema.
- **Los estados de intercambio de OCA y el `blocking_level` de Odoo** dentro del motor. Son estado de la aplicación, y la
  gradación error/aviso ya existe (`Observacion.nivel` y `FALTAS`).
- **Ítems del UBL e imputación por línea de factura.** Hueco declarado hasta que haya un caso.
- **`cbc:AccountingCost`.** Sin evidencia en el UBL peruano.
- **Llamar CUO a la identidad del §3, o hacerla un hash opaco.** El CUO es del software que genera el PLE, y una clave
  legible se puede leer en un error.
- **Una huella de la configuración aplicada.** Metería las imputaciones en la huella y no tiene caso.
- **Guardar aparte el tipo de cambio usado, o tres fechas nuevas.** Ya van en la línea y en `_exportacion` (§4).
- ***Embeddings* y aprendizaje estadístico dentro del motor** (Midday, `smart_importer`). No son deterministas: son de la
  aplicación, y el motor recibe lo aprendido como datos.
- **Del MCP: tareas, *sampling*, *roots*, prompts, el modo dinámico de Apideck y los interruptores de escritura de QBO.**
  Once herramientas puras no los necesitan.
- **`Idempotency-Key`, webhooks y sincronización incremental.** Descartados en `REFERENCIAS.md` por la misma razón: el
  motor no habla con otra API con estado.
- **Redis como recomendación contable.** No hay una fuente contable que la respalde; queda como nota de ingeniería para
  la aplicación (§4).

---

## 9 · Tabla de propuestas

El orden en que se ejecutan, con sus hitos, dependencias y criterios de salida, está en
[HOJA-DE-RUTA.md](HOJA-DE-RUTA.md); esta tabla queda como el inventario de lo que la investigación propuso.

Prioridad **A**: afina lo que existe, tiene un caso visto y no necesita datos de fuera. **B**: tiene caso, pero cambia
una salida (y se anuncia) o es una función nueva que decide el mantenedor. **C**: espera un archivo real. **D**: espera un
segundo caso o una versión del SDK.

| # | Propuesta | Nivel | Caso real que la destraba | Test que la fijaría | Nombre | Prio |
|---|---|---|---|---|---|---|
| 1 | `claves_previas` en `revisar`, `diagnosticar`, `exportar` y el MCP | F | `DUPLICADO_PERIODO_ANTERIOR` nunca se dispara desde la fachada (error 452) | Con una clave previa, el comprobante sale en `bloqueantes` con `pedir_a: contador`; sin ella, todo igual | ya existe en `validar` | A |
| 2 | Anotaciones en las 11 herramientas | F | Sin anotación, un cliente asume `destructiveHint` y `openWorldHint` verdaderos | `test_servidor_mcp` recorre las 11 | — | A |
| 3 | Corregir la frase del LEEME sobre la detracción regenerada | estándar | Regenerar lo ya importado duplica en un destino que suma | — | — | A |
| 4 | Índice por comprobante: identidad, rango de líneas y huella | F | Tandas que se solapan; comprobante que cambió tras exportarse | Partición exacta; cuadre por rango; literal de `test_huella` intacto | `_asiento.comprobantes*` | A |
| 5 | Llevar la lectura de disco de `comparar_sire` a la CLI | puerta | La regla «sin disco en el núcleo» | Un vigilante de disco en `test_frontera`, salvo datos empaquetados | — | A |
| 6 | Tipo de cambio y tasa de detracción como texto en la línea | N · D | La regla de `Decimal` | Línea con texto; celda de CONCAR igual (snapshot intacto); huella en USD con literal nuevo y anuncio | — | B |
| 7 | CSV con `rol` y los `tipo_cp` | D | El CSV se ofrece como plantilla de driver y pierde lo que un driver necesita | Columnas nuevas presentes y llenas | — | B |
| 8 | Versión del motor en `_asiento` y `_exportacion` | F | Saber con qué versión salió una tanda tras un cambio anunciado | Igual a `__version__`; fuera de la huella | `motor*` | B |
| 9 | `cruzar_con_propuesta` y el primer `pedir_a: proveedor` | N · F | La propuesta del RCE como lista de control | Tres cajones; ceros; RUC mal escrito | `cruzar_con_propuesta*` | B |
| 10 | `outputSchema` de `diagnosticar` | F | Un agente que valida la forma de la respuesta | Las dos formas de retorno validan contra el esquema | — | B |
| 11 | Plan de cuentas del destino y falta `cuenta_fuera_del_plan` | N · F · D | Nota K de la plantilla de CONCAR | Plan sin la cuenta bloquea y `exportar` lanza; sin plan, snapshot idéntico | `plan_de_cuentas*`, `cuenta_fuera_del_plan*` | C |
| 12 | `lleva_centro` por la marca del plan | N | Nota M; el propio docstring de `lleva_centro` | La marca manda sobre el prefijo (mutación) | — | C |
| 13 | Centro de costo contra la lista `centros_costo` | N | Nota M, «Ver T.G. 05» | Un centro inexistente bloquea solo si llega la lista | — | C |
| 14 | `aplicar_constancias` | N | Hoja de ruta; `_detraccion_pendiente` ya responde | De `PROVISIONADO` a `PAGADO` con el archivo real; sin pareja, igual | `aplicar_constancias*` | C |
| 15 | Lector de extracto del banco X y el movimiento | N | El Excel o TXT del portal bancario, el formato confirmado en el Perú | Archivo real anonimizado; un libro Excel no se desarma como ZIP; deduplica | `Movimiento*`, `leer_extracto*` | C |
| 16 | `conciliar` | N | Constancias primero; después cobros y pagos | Motivos legibles; cardinalidades; lo pendiente no se propone; tolerancia | `conciliar*` | C |
| 17 | Asiento de tesorería | N · D | Cobros y pagos hacia el destino | Archivo aceptado del sub-diario de bancos; ITF con su norma | — | C |
| 18 | `sugerir_imputacion` | N · F | La imputación repetida por proveedor | Determinista; mínimo; nunca escribe la imputación | `sugerir_imputacion*` | C |
| 19 | Pedir lo que falta desde el MCP (MRTR) | F | Pedir una cuenta sin guardar estado | — | — | D |
| 20 | Contrato de lector y *entry points* de lectores | N | El segundo banco | Un test de conformidad análogo al de drivers | `contaperu.lectores*` | D |
| 21 | `trazas` de un driver que consolide | D | El primer driver que agrupe líneas | Partición exacta; los importes suman | `trazas*` | D |
| 22 | `documento.id_externo` en la línea | estándar | Un driver `desde_lineas` que escriba el id del origen | Transporte puro; fuera de la huella | — | D |
| — | ¿Debe `generar_asiento` exigir lo que exige el destino? | F | §2 | — | — | pregunta |

---

## 10 · Fuentes

Consultadas el 13-sep-2026. Lo ya citado en [REFERENCIAS.md](REFERENCIAS.md) (QuickBooks, Xero, Merge, Codat, Rutter,
Apideck en lo general) no se repite.

**Normas y guías peruanas**
- PLE, Libro Diario 5.1 y registros: RS 169-2015/SUNAT, Anexo 2 — https://spij.minjus.gob.pe/Graficos/Peru/2015/Junio/30/RS-169-2015-SUNAT-ANX-2.pdf
- Registro de Inventario Permanente Valorizado (CUO consolidado): RS 042-2018/SUNAT, anexo — https://www.sunat.gob.pe/legislacion/superin/2018/anexo-042-2018.pdf
- OSE — https://cpe.sunat.gob.pe/informacion_general/operador_servicios_electronicos
- SEE-Del Contribuyente (envío, CDR, puesta a disposición) — https://cpe.sunat.gob.pe/sistema_emision/see_contribuyente
- Depósito de detracciones — https://orientacion.sunat.gob.pe/02-deposito-de-detracciones-aspecto-generales
- Constancia de depósito de detracción — https://orientacion.sunat.gob.pe/3145-03-constancia-de-deposito-de-detraccion-empresas
- TUO de la Ley del ITF, DS 150-2007-EF — https://www.sunat.gob.pe/legislacion/itf/ds150_07.htm
- BCRP, interoperabilidad de pagos minoristas — https://www.bcrp.gob.pe/sistema-de-pagos/interoperabilidad/estrategia-de-interoperabilidad-de-los-pagos-minoristas.html
- SBS y *open finance* (según terceros) — https://iupana.com/2025/11/25/es-el-proyecto-mas-importante-que-tiene-la-sbs-dice-el-regulador-financiero-sobre-el-open-finance-en-peru/

**Estándares**
- SAF-T (XSD noruego 1.10) — https://raw.githubusercontent.com/Skatteetaten/saf-t/master/Norwegian_SAF-T_Financial_Schema_v_1.10.xsd
- XBRL GL — https://wp.itl.ee/wp-content/uploads/2021/02/ANNEX-I-XBRL-GL-accounting-entry-data-standard.pdf y https://www.xbrl.org/the-standard/what/global-ledger/
- OAGIS, `PostJournalEntry` — http://www.datypic.com/sc/oagis10/e-oag_PostJournalEntry.html
- EN 16931, BT-19/BT-133 — https://github.com/ConnectingEurope/eInvoicing-EN16931/issues/270 ; Peppol BIS Billing 3.0 — https://docs.peppol.eu/poacc/billing/3.0/bis/
- Peppol, modelo de cuatro esquinas — https://e-rechnung-bund.de/en/faq/peppols-technical-solution-the-four-corner-model/
- ISO 20022 camt.054 (guía de Standard Chartered) — https://www.sc.com/en/uploads/sites/66/content/docs/Standard-Chartered-ISO-20022-message-formatting-guideline-for-camt.054.pdf
- MT940 estructurado (Danske Bank) — https://danskeci.com/-/media/pdf/danskeci-com/swift-mt/reconciliation/mt940_structured.pdf ; MT942 — https://developer.huntington.com/enterprisepayments/docs/swift-mt942-intra-day ; BAI2 — https://developer.huntington.com/enterprisepayments/docs/bai2 ; OFX — https://www.online.fnb.co.za/rhelp_0_15/Downloads/Statement_File_Specifications/Statement_Type_-_OFX.pdf

**ERPs abiertos**
- ERPNext (rama `develop`): `GL Entry` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/gl_entry/gl_entry.json ; `gl_entry.py` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/gl_entry/gl_entry.py ; `Payment Ledger Entry` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/payment_ledger_entry/payment_ledger_entry.json ; `Accounting Dimension Detail` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/accounting_dimension_detail/accounting_dimension_detail.json ; `Accounting Dimension Filter` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/accounting_dimension_filter/accounting_dimension_filter.json ; libro inmutable — https://docs.frappe.io/erpnext/user/manual/en/immutable-ledger-in-erpnext ; `Repost Accounting Ledger` — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/repost_accounting_ledger/repost_accounting_ledger.json ; `Bank Transaction` — https://docs.frappe.io/erpnext/user/manual/en/bank-transaction ; conciliación — https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/bank_reconciliation_tool/bank_reconciliation_tool.py ; `Purchase Invoice` — https://github.com/frappe/erpnext/blob/develop/erpnext/accounts/doctype/purchase_invoice/purchase_invoice.py
- Odoo 18: `account.move` — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_move.py ; `account.move.line` — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_move_line.py ; fechas de bloqueo — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/company.py ; `account.lock_exception` — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_lock_exception.py ; inalterabilidad — https://www.odoo.com/documentation/18.0/applications/finance/accounting/reporting/data_inalterability.html ; planes analíticos — https://raw.githubusercontent.com/odoo/odoo/18.0/addons/analytic/models/analytic_plan.py , https://raw.githubusercontent.com/odoo/odoo/18.0/addons/account/models/account_analytic_plan.py , https://raw.githubusercontent.com/odoo/odoo/18.0/addons/analytic/models/analytic_distribution_model.py
- Odoo 17: líneas de extracto — https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/account_bank_statement_line.py ; modelos de conciliación — https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account/models/account_reconcile_model.py ; conciliación — https://www.odoo.com/documentation/17.0/applications/finance/accounting/bank/reconciliation.html ; facturas de proveedor — https://www.odoo.com/documentation/17.0/applications/finance/accounting/vendor_bills.html ; `account.edi.document` — https://raw.githubusercontent.com/odoo/odoo/17.0/addons/account_edi/models/account_edi_document.py
- OCA: `edi_oca` — https://raw.githubusercontent.com/OCA/edi-framework/17.0/edi_oca/models/edi_exchange_record.py ; bank-statement-import — https://github.com/OCA/bank-statement-import ; `unique_import_id` — https://raw.githubusercontent.com/OCA/bank-statement-import/18.0/account_statement_import_base/models/account_bank_statement_line.py ; account-reconcile — https://github.com/OCA/account-reconcile ; edi — https://github.com/OCA/edi ; `account_invoice_import` — https://github.com/OCA/edi/tree/12.0/account_invoice_import
- Apache Fineract — https://fineract.apache.org/docs/legacy/

***Ledgers* y librerías**
- TigerBeetle — https://docs.tigerbeetle.com/reference/transfer/ , https://docs.tigerbeetle.com/coding/data-modeling/ , https://docs.tigerbeetle.com/coding/linked-events/
- Formance Ledger v2 — https://raw.githubusercontent.com/formancehq/ledger/main/openapi/v2.yaml ; Formance Payments — https://docs.formance.com/modules/connectivity/payments
- Blnk — https://docs.blnkfinance.com/transactions/transaction-lifecycle , https://docs.blnkfinance.com/reconciliations/matching-rules , https://docs.blnkfinance.com/reconciliations/strategies.md
- django-hordak — https://django-hordak.readthedocs.io/en/latest/hordak-database-triggers.html
- python-accounting — https://github.com/ekmungai/python-accounting
- Beancount — https://beancount.github.io/docs/beancount_language_syntax/ ; beangulp — https://raw.githubusercontent.com/beancount/beangulp/master/beangulp/importer.py , https://raw.githubusercontent.com/beancount/beangulp/master/beangulp/extract.py ; smart_importer — https://github.com/beancount/smart_importer
- hledger, reglas CSV — https://hledger.org/1.40/hledger.html#csv
- invoice2data — https://github.com/invoice-x/invoice2data
- Patrón *transactional outbox* — https://microservices.io/patterns/data/transactional-outbox.html

**APIs unificadas abiertas y detalles nuevos de las cerradas**
- Panora — https://raw.githubusercontent.com/panoratech/Panora/main/packages/api/src/accounting/journalentry/types/model.unified.ts
- Nango — https://nango.dev/docs/implementation-guides/use-cases/unified-apis , https://nango.dev/docs/reference/api/sync/records-list
- Codat — https://docs.codat.io/using-the-api/push , https://docs.codat.io/using-the-api/modified-dates , https://docs.codat.io/bank-feeds/create-account , https://docs.codat.io/bank-feeds/pushing-transactions , https://docs.codat.io/payables/sync/bills
- Merge — https://docs.merge.dev/merge-unified/writing-data/programmatic-writes-with-meta/templates-and-conditional-fields , https://docs.merge.dev/accounting/journal-entries/ , https://docs.merge.dev/accounting/invoices/
- Xero Bank Feeds — https://github.com/XeroAPI/Xero-OpenAPI/blob/master/xero_bankfeeds.yaml ; bandeja de facturas — https://central.xero.com/s/question/0D53m00009ditslCAA/where-do-i-find-my-xero-bills-email-address
- QuickBooks, recibos por correo — https://quickbooks.intuit.com/learn-support/en-us/help-article/accounts-payable/email-receipts-bills-quickbooks-online/L7r2LAQ7C_US_en_US

**Banca y agregadores**
- Plaid — https://plaid.com/docs/api/products/transactions/ , https://plaid.com/docs/transactions/transactions-data/
- GoCardless Bank Account Data — https://docs.gocardless.com/bank-account-data/overview , https://bankaccountdata.gocardless.com/new-signups-disabled
- Open Banking UK — https://openbankinguk.github.io/read-write-api-site3/v3.1.10/profiles/event-notification-api-profile.html
- Midday — https://github.com/midday-ai/midday , https://midday.ai/docs/receipt-matching/ , https://midday.ai/updates/automatic-reconciliation-engine/
- Actual Budget — https://actualbudget.org/docs/transactions/importing/ ; Firefly III — https://docs.firefly-iii.org/references/data-importer/duplicate-detection/
- BCP Host to Host — https://www.viabcp.com/empresas/cobranzas-y-pagos/telecredito/host-to-host ; APIs de empresa (según terceros) — https://www.ecommercenews.pe/pagos-online/2026/bcp-optimiza-la-gestion-de-pagos-y-transferencias-de-empresas-con-apis-y-host-to-host.html/
- Prometeo, Perú (según el proveedor) — https://docs.prometeoapi.com/docs/per%C3%BA
- CONCAR CB — https://realsystems.com.pe/concar/concar-cb/ ; Starsoft — https://www.starsoft.com.pe/prod_contabilidad.html

**MCP**
- Changelogs — https://modelcontextprotocol.io/specification/2025-06-18/changelog , https://modelcontextprotocol.io/specification/2025-11-25/changelog , https://modelcontextprotocol.io/specification/2026-07-28/changelog
- Esquema 2025-11-25 (anotaciones, plantillas de recursos, tareas) — https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/main/schema/2025-11-25/schema.ts
- Herramientas — https://modelcontextprotocol.io/specification/2025-06-18/server/tools , https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- *Elicitation* — https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation ; MRTR — https://modelcontextprotocol.io/specification/2026-07-28/basic/patterns/mrtr ; tareas — https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks , https://modelcontextprotocol.io/seps/2663-tasks-extension
- Servidores — https://github.com/XeroAPI/xero-mcp-server , https://github.com/intuit/quickbooks-online-mcp-server , https://github.com/apideck-libraries/mcp , https://docs.merge.dev/merge-agent-handler/overview
- SDK de Python — https://github.com/modelcontextprotocol/python-sdk
