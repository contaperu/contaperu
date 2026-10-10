"""Lo que este motor le dice a un agente de cada operación: el texto que el servidor MCP publica como
descripción de cada herramienta y de cada recurso.

**No son las descripciones del `api`, y por eso viven aparte.** Las del `api` —la primera frase de cada
docstring— son para quien programa, y las publica el contrato OpenConta; estas son para un modelo que tiene
que decidir cuál llamar y con qué, así que dicen lo que no se deduce de una firma: qué pasa si no mandas el
`driver`, por qué el Excel de CONCAR se suma al importarlo dos veces, cuál es el techo del SIRE.

Están junto a `instrucciones.py` y son de la misma familia que `CAMINO`, **no que `REGLAS`**, y la distinción
importa: `REGLAS` se la lleva quien monta su propia capa de agente, porque no nombra ninguna herramienta.
Estos textos y `CAMINO` sí las nombran —«el recurso `contaperu://drivers` dice el canal de cada uno»—, así que
a quien tenga otras herramientas no le sirven tal cual, y prometerle a un modelo una herramienta que no existe
es peor que no decirle nada. Por eso tampoco se reexportan en `contaperu.api`.

Y están en **un solo sitio** porque hasta la 6.1.0 se escribían dentro de cada función del servidor MCP, que
es donde nacían las divergencias con la tabla. La indentación de la segunda línea en adelante es la que tenían
como docstring, y se conserva: es lo que el agente lee hoy, byte a byte (`tests/fixtures/mcp/publicado.json`).
"""
from __future__ import annotations

# Por el nombre de la herramienta, que es como la ve el agente.
PARA_HERRAMIENTA: dict[str, str] = {
    'leer_xml_ubl': """Lee el XML UBL 2.1 de la factura electrónica de SUNAT y devuelve un documento `open-accounting`.

    Acepta un XML suelto como texto, o un ZIP en base64 con varios dentro (`es_base64: true`).
    Descarta lo que no es un comprobante — las constancias de recepción (CDR) y las hojas de
    estilo— y avisa de lo que no pudo leer.

    `libro` es la cabecera, y son **exactamente cuatro claves**: `ruc`, `razon_social`, `periodo`
    (AAAAMM) y `tipo` (`venta` o `compra`). Cualquier otra detiene la lectura diciendo su nombre;
    el libro no admite ni anotaciones `_`.
    """,
    'leer_propuesta_sire': """Lee el TXT de la propuesta que SUNAT entrega en el SIRE y devuelve un documento
    `open-accounting`.

    Es lo que el contribuyente descarga de su SIRE con lo que SUNAT cree que compró o vendió;
    a partir de ahí se compara con la realidad y se corrige. Acepta el TXT como texto o el ZIP
    tal cual lo entrega SUNAT (`es_base64: true`).

    `libro` es la cabecera, y son **exactamente cuatro claves**: `ruc`, `razon_social`, `periodo`
    (AAAAMM) y `tipo` (`venta` o `compra`). Cualquier otra detiene la lectura diciendo su nombre;
    el libro no admite ni anotaciones `_`.
    """,
    'validar_comprobantes': """Revisa los comprobantes de un documento `open-accounting` y devuelve el mismo documento con
    `estado` y `observaciones` puestos en cada uno.

    Comprueba lo que se puede comprobar sin salir a ningún sitio: que el RUC sea un RUC, que el
    IGV cuadre con la base, que el total sea la suma de sus partes, que la fecha no sea posterior
    al periodo (error; una venta de un mes anterior solo avisa, y una compra anterior, solo pasados
    los 12 meses del plazo de anotación), que no haya duplicados —en el lote y, con `claves_previas`, contra lo ya
    anotado en otros periodos—. Las observaciones de nivel `error`
    bloquean la exportación; las de nivel `aviso` no.

    También descarta las detracciones cuyo código no está en la tabla del contribuyente, que es
    de donde salen los códigos inventados cuando una IA confunde la retención del IGV con una
    detracción. Con `imputacion` —la misma de `generar_asiento`— comprueba además que cada llave
    hable de un comprobante que está: una huérfana sale aquí y no al exportar.
    """,
    'normalizar_detracciones': """Contrasta la detracción de cada comprobante con la tabla del contribuyente y deja en
    blanco la que no reconozca.

    Sirve sobre todo después de leer comprobantes con un modelo de lenguaje: la confusión más
    común es tomar la **retención del IGV** (el 3 % que retiene un agente de retención cuando la
    factura pasa de S/ 700, y que no toca el registro de compras) por una detracción.
    """,
    'diagnosticar': """Dice todo lo que hay que mirar de un mes ANTES de exportarlo. **Llámala antes de `exportar`.**

    En una sola respuesta: si el mes está listo (`listo_para_exportar`) y, si no, por qué
    (`por_que_no`); qué comprobantes tienen observaciones que bloquean y cuáles solo avisos, por su
    serie-número; qué falta para el sistema de destino —cuenta contable, centro de costo, tipos de
    comprobante sin sigla, monedas que no admite, un reparto entre cuentas que no admite
    (`reparto_no_admitido`), lo que no cabe en su formato (`no_cabe`), sub-diarios sin correlativo—; qué
    detracciones esperan todavía su constancia (`detracciones_pendientes`) y cuáles ya están
    depositadas (`detracciones_pagadas`) — una detracción cuenta como pagada cuando tiene un número
    de constancia que no es el comodín **y** la fecha del depósito, así que una que trae número y no
    fecha sigue saliendo como pendiente y lo que hay que pedir es la fecha; un resumen por proveedor o cliente; desde qué
    correlativo arrancaría cada sub-diario; y la lista de lo que saldría.

    `driver` es el sistema de destino y **se declara siempre** (los que hay, en `contaperu://drivers`):
    lo que falta depende de él, así que suponerlo devolvería el diagnóstico de otro sistema.
    `exige` dice qué pide ese destino (el CSV no exige centro de costo; CONCAR sí), y `que_falta`
    agrupa por motivo lo que de verdad bloquea, con **`pedir_a`**: `contador` si se resuelve mirando
    el documento o el plan de cuentas, `sistema` si es configuración del destino o un dato público
    que no está en el papel. Úsalo para redactar la pregunta a quien toca, en vez de adivinar.

    No corrige nada ni inventa nada: un comprobante sin cuenta se arregla donde se revisa, y aquí
    solo se dice cuál es. Es la herramienta para enseñarle a la persona qué va a salir antes de
    generar un archivo que luego se importa en su sistema contable. `imputacion` es la misma de
    `generar_asiento`: un reparto que no suma la base sale en `faltantes.reparto_que_no_cuadra`.
    Si la `configuracion` no cumple lo que se declara en `contaperu://configuracion`, lo dice en
    `errores_de_configuracion`, cada error con su ruta. La forma de la respuesta está en el recurso
    `contaperu://esquemas/diagnostico`.
    """,
    'generar_asiento': """Convierte los comprobantes en líneas de diario, sin el formato de ningún sistema.

    Devuelve el bloque `asiento` del estándar: cuenta, debe o haber, importe, moneda, glosa,
    centro de costo y el documento que lo respalda. Es lo que sirve para revisar el asiento, o
    para cargarlo en un sistema que no tenga driver todavía.

    `correlativos` dice por qué número empieza cada sub-diario ({"11": 1}); si no se pasa,
    empieza en 1. Con `incluir_observados` se genera aunque haya comprobantes con errores —
    útil para ver qué saldría, arriesgado para presentar.

    `imputacion` trae lo que se decidió para cada comprobante, por su `id_externo`: su
    `cuenta_contable`, su `centro_costo`, la `cuenta_tercero` (la del total) o un `reparto` de la base
    entre cuentas ([{importe, cuenta_contable, centro_costo}], que tiene que sumar la base). Lo que no
    traiga sale de la configuración.

    `driver` es el sistema de asientos cuya sección de la configuración se aplica: sus siglas, sus
    sub-diarios y las columnas en que pone el centro de costo. **Se declara siempre** —los que hay están
    en el recurso `contaperu://drivers`—, porque el sistema de un contribuyente es suyo y suponerlo arma
    el asiento de otro. Exige lo mismo que `exportar` hacia ese sistema —en CONCAR, el centro de costo y
    una moneda con código—; para ver qué falta sin que se niegue, `diagnosticar`.
    """,
    'exportar': """Genera el archivo que espera un sistema contable, ya listo para importar.

    Devuelve dos cosas: un resumen en JSON (nombre del archivo, comprobantes, debe y haber, y en
    `_exportacion` la **huella** del asiento que salió: si vuelves a exportar lo mismo, la huella se
    repite, y el Excel de CONCAR se SUMA al importarlo dos veces) y **el archivo adjunto**, para
    guardarlo tal cual. `fecha` (AAAA-MM-DD) es opcional y la pones tú: este servidor no mira el reloj.
    `imputacion` es la misma de `generar_asiento`.

    `driver` **se declara siempre**: el sistema contable de un contribuyente es suyo, y un Excel de
    CONCAR importado en un CONTASIS no se nota hasta que ya está dentro.

    Drivers disponibles, por canal —a quién entrega cada uno— (el recurso `contaperu://drivers` dice el de
    cada cual):
      - SUNAT:  `sire` — el TXT para reemplazar la propuesta del RVIE o del RCE en SUNAT: el
                contenido va en `texto` y el ZIP que sube a SUNAT, adjunto.
                `ple` — el Libro Diario del PLE, que es el OTRO régimen de SUNAT: una fila por línea del
                asiento, no por comprobante.
                `ple_plan` — el detalle del plan contable del PLE (formato 5.3).
      - Legacy: `concar` — el Excel de asientos de 41 columnas, adjunto como `.xlsx`.
                `contasis` — el registro de compras o de ventas que importa CONTASIS, adjunto como
                `.xlsx`: una fila por comprobante, sin sub-diario (se elige al importar).
                `starsoft` — los asientos en TXT de palotes.
      - ERP:    `csv` — las líneas de diario en columnas, en `texto` y también adjunto.
                `asiento_contable` — el documento del estándar con sus comprobantes y su asiento, sin siglas ni
                correlativos de ningún sistema legacy, adjunto como `.json`.

    Antes de escribir nada, en los drivers que arman asiento (`concar`, `csv`) comprueba que cuadre; si
    no cuadra, falla. `contasis` y `sire` no arman asiento: `contasis` se niega antes por lo que exige y
    por lo que no cabe en su formato (`no_cabe`).
    """,
    'validar_partida_doble': """Comprueba que la suma del Debe sea exactamente igual a la del Haber.

    Sin tolerancia: un céntimo de diferencia es un asiento mal armado. Devuelve las dos sumas,
    la diferencia y cuántas líneas no dicen si son Debe o Haber.
    """,
    'resumen': """Cuánto es este libro: base gravada, IGV y total, **cada moneda por su lado**.

    Lo que un contador pregunta antes de dar un mes por bueno. **No pide destino**: es del libro, no de un
    archivo — si lo que quieres es qué saldría hacia un sistema contable concreto, eso es `diagnosticar`.

    Dos avisos para decírselos a quien pregunte: **las notas de crédito restan** (los tipos 07 y 87), así
    que el total no cuadra sumando a mano lo que se ve; y **soles y dólares no se suman entre sí**, porque
    sumar importes nominales de dos monedas no da ningún total. Lo excluido y lo marcado duplicado se
    cuentan en `recuento` y no suman.

    Con `agrupar_por="contraparte"`, los mismos totales por proveedor o cliente, de más a menos.
    """,
    'por_cuenta': """El pre-mayor: en qué cuentas cayó un asiento, con su debe y su haber por moneda, y el cuadre.

    Recibe las líneas que devuelve `generar_asiento`. Delata una imputación mal puesta sin generar ningún
    archivo: una cuenta con un importe que no le toca salta a la vista en una lista de diez cuentas y no en
    una tabla de seiscientas filas.

    Trae el cuadre global y también **por moneda**, que dice algo que el global no puede: dos monedas cuyos
    descuadres se compensan salen cuadradas en el total y descuadradas cada una. Y `roles` va en plural:
    con una detracción, la cuenta por pagar hace dos papeles en el mismo asiento.
    """,
    'buscar_cuenta_pcge': """Busca una cuenta en el Plan Contable General Empresarial 2026, por nombre o por código.

    Con `texto` devuelve las cuentas cuyo nombre lo contiene (sin distinguir tildes ni mayúsculas).
    Con `codigo` devuelve esa cuenta y, si no está en la norma, **la cuenta madre que la gobierna**:
    de `603201` sale `6032 Suministros`, porque el PCGE llega a cinco dígitos y las divisionarias
    las abre cada empresa. Un código que no resuelve ni por su elemento está mal escrito.

    Úsala antes de decidir la `cuenta_contable` de un comprobante: es la diferencia entre elegir
    una cuenta que existe y proponer uno que suena bien.
    """,
    'adaptar_pcge2026': """Adapta las cuentas de un asiento al Plan Contable General Empresarial 2026.

    **La tabla de equivalencias está vacía, y hoy eso es lo correcto**: este proyecto nace en 2026
    y trabaja con el PCGE 2026 desde el primer asiento, así que no hay plan anterior del que
    traducir. La herramienta existe como riel para el día que una modificatoria sustituya cuentas;
    mientras tanto devuelve el asiento intacto y lo dice en su informe (`sin_tabla`).

    Cuando llegue esa modificatoria, cada equivalencia entrará **con la cita del artículo que la
    respalda** —el cargador se niega a leer un mapeo sin ella—, porque una equivalencia inventada
    produce estados financieros incorrectos en la contabilidad de quien confíe en esto.

    Para saber si una cuenta existe o cómo se llama, la herramienta es `buscar_cuenta_pcge`; esta
    no es esa.
    """,
    'configuracion_por_defecto': """La configuración contable de partida: lo general en la raíz —cuentas, centros de costo, tasas
    de detracción— y una sección por sistema contable con lo suyo (`concar`: siglas y sub-diarios,
    códigos, columnas del centro de costo; `csv`: siglas, sub-diarios y códigos de la detracción;
    `contasis`: medio de pago y columnas del centro de costo).

    **Con `driver`, la de quien lleva ese sistema**: lo general con las cuentas de ese sistema y solo
    su sección. Pásalo siempre que sepas a qué sistema contable exporta el contribuyente, porque las
    cuentas de fábrica son las del PCGE a seis dígitos y hay sistemas que numeran de otra forma.

    Es un punto de partida razonable, no la verdad de ningún contribuyente: el plan de cuentas
    y los sub-diarios los decide cada empresa. Cópiala, cámbiale lo que toque y pásala como
    `configuracion` en las demás herramientas: se valida entera, y lo que no existe se dice.
    """,
    'drivers_disponibles': """Los sistemas contables a los que se puede exportar, y qué pide cada uno.

    Por nombre —el que va en `driver`—: qué archivos genera, si arma asientos o es un registro, su **canal** —a
    quién entrega: `sunat`, `legacy` o `erp`—, lo que **exige** para no negarse (CONCAR pide centro de costo y
    una moneda con código; el CSV no) y si tiene sección propia en la configuración.

    Ojo con `sunat`: son los dos regímenes, el SIRE y el PLE. El `sire` manda compras y ventas; el `ple`, el
    Libro Diario y los demás libros.

    Llámala antes de `diagnosticar`, `generar_asiento` o `exportar` cuando no sepas qué destino usa el
    contribuyente: esas tres lo exigen y no lo suponen.
    """,
}

# Por la URI del recurso.
PARA_RECURSO: dict[str, str] = {
    'contaperu://campos/comprobante': """Qué campos de un comprobante los pone el DOCUMENTO, cuáles el SISTEMA que lo produce y cuáles la
    REVISIÓN, más los tres que son obligatorios.

    Léelo antes de armar un documento con datos que alguien te dicte: lo que está en `sistema` o en
    `revision` no lo dice el papel —el estado, el origen, la confianza, si está apartado— y ponerlo tú es
    decidir por el sistema que va a recibirlo. Los tres tramos cubren el comprobante entero.""",
    'contaperu://configuracion': """Qué se configura y cómo: lo general y la sección de cada sistema contable, cada clave con su tipo, su valor
    por defecto, su patrón y sus textos, y en qué columnas de su archivo puede ir cada dato (el centro de costo, por
    ejemplo). Es lo que una aplicación lee para pintar su pantalla de configuración, y contra lo que se valida la
    `configuracion` de las herramientas.""",
    'contaperu://drivers': """Los formatos de salida disponibles y qué libros genera cada uno.

    Lo mismo que la herramienta del mismo nombre, y son las dos a propósito: un recurso se lee, y quien decide si
    el modelo llega a leerlo es el cliente; una herramienta se llama, y el modelo la ve siempre.
    """,
    'contaperu://catalogos/sunat': """Los catálogos de SUNAT que entiende el motor: tipos de comprobante, tipos de documento
    de identidad y monedas.""",
    'contaperu://catalogos/regimenes': """Los regímenes tributarios del Perú y lo que cada uno obliga, con la cita de su artículo: la
    tasa y la base de su pago a cuenta, los libros que obliga a llevar —por su código del PLE— y los
    topes que sacan de él.

    Hoy solo el Régimen Especial tiene su norma leída; los otros tres dicen qué hay que leer para
    que entren, en vez de traer una tasa de memoria. El motor no calcula la cuota: publica la tasa.""",
    'contaperu://catalogos/vencimientos': """Cuándo vence un mes: la fecha de la declaración y el pago, y la fecha máxima de atraso del
    registro electrónico de ventas y de compras, por periodo y por último dígito de RUC, con la
    columna de los buenos contribuyentes. Los dos salen de la RS 000281-2022/SUNAT, un anexo cada
    uno, y el del registro vence antes que el de la declaración.

    No es un reloj: dado un periodo y un dígito devuelve una fecha. Si queda tiempo o hay mora lo
    calcula quien tiene el hoy, que no es el motor. Solo los años que SUNAT publicó resueltos.""",
    'contaperu://catalogos/sire-api': """El CANAL del SIRE, descrito: rutas por libro, parámetros obligatorios, los dos grants de
    OAuth, la metadata de TUS, los estados del ticket y los códigos de retorno, con su fuente.

    El motor no se conecta a SUNAT: esto describe la API para quien escriba su propio conector.
    Y avisa de su techo — «Generar el registro» no existe por API.""",
    'contaperu://catalogos/sire-campos': """El FORMATO del SIRE columna a columna: de cada campo del anexo del RVIE y del RCE, su número, el
    nombre de SUNAT, el campo del documento donde cae —o el motivo por el que no cae— y si el TXT de
    reemplazo lo devuelve.

    Sirve para contestar «¿dónde acabó esta columna?» y «¿qué del registro no se usa?». Una columna que el
    motor no lee no se pierde: la fila entera viaja en `datos_originales["sire"]`.""",
    'contaperu://catalogos/ple-campos': """El FORMATO del Libro Diario 5.1 del PLE columna a columna: de cada uno de sus 21 campos, su número,
    el nombre de SUNAT, de dónde lo saca el driver al escribirlo —o por qué va vacío— y qué hizo con esa
    columna un libro real que SUNAT aceptó.

    Trae también los códigos de libro del PLE y la nomenclatura del fichero `LE…`. No confundirlos con los
    del SIRE, que son otros.""",
    'contaperu://catalogos/estandar': """Los catálogos que este estándar inventa: los roles de una línea del asiento, las cinco clases contables y
    los tipos de libro, cada uno con su fuente y su versión.""",
    'contaperu://catalogos/pcge2026': """El catálogo oficial de cuentas del Plan Contable General Empresarial 2026: cada cuenta con
    su nombre y la página de la norma que lo dice.

    Sirve para dos cosas: poner el nombre de una cuenta, y comprobar que la cuenta que se va a
    escribir existe. **Que una cuenta no esté aquí no la invalida**: el PCGE llega a cinco dígitos
    y cada empresa abre sus divisionarias debajo — `603201` es válida y no aparece en la norma.
    """,
    'contaperu://estandar/open-accounting': """El esquema JSON del documento contable `open-accounting`, con cada campo documentado.""",
    'contaperu://esquemas/diagnostico': """El JSON Schema de la respuesta de `diagnosticar`, también cuando la configuración no se puede aplicar. El SDK no
    deja declararlo como `outputSchema` de la herramienta sin cambiar lo que responde, así que viaja como recurso.""",
}
