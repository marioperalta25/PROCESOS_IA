---
name: interfaz-escritorio
description: Diseñar o implementar pantallas, componentes y estados de la aplicación de escritorio PROCESOS_IA en Python. Aplicar a interacción, estilo, accesibilidad y escalado.
---

# Interfaz de escritorio

Leer [las reglas comunes](../../reglas/AGENTS.md). Confirmar en
[el registro técnico](../../proyecto/decisiones.md) si existe una biblioteca
elegida. [El diseño](../../proyecto/diseno-interfaz.md) es una propuesta;
consultarlo cuando corresponda sin asumir que el usuario aprobó sus valores.

## Procedimiento

1. Confirmar la pantalla y el flujo de la etapa actual. Buscar componentes,
   estilos y presentadores reutilizables antes de crear otros.
2. Diseñar estados vacío, ocupado, completado, cancelado y fallido para ese flujo.
   Indicar qué puede hacer el usuario en cada uno.
3. Reutilizar los valores visuales existentes y aprobados. Si el encargo autoriza
   proponer diseño, distinguir propuesta de decisión; mantener los valores elegidos
   en un único recurso del tema, sin imponer la paleta sugerida anteriormente.
4. Conectar acciones a casos de uso inyectados. El código visual no conoce comandos
   de instalación ni URLs de endpoints específicos de Ollama.
5. Ejecutar trabajo lento fuera del hilo de interfaz y transferir resultados mediante
   mecanismos seguros del framework elegido. Si se adopta Qt, modificar widgets
   solo desde su hilo principal; no dar esa elección por hecha.
6. Comprobar teclado, foco, contraste, escalado y textos largos antes de entregar.

## Criterios específicos

- **Responsividad obligatoria y contenedor base general**: Toda nueva vista, diálogo o subpantalla DEBE implementar diseño responsivo reutilizando el contenedor base general (`ContenedorPantallaResponsiva`) o área de scroll (`QScrollArea` con `widgetResizable=True`). Jamás colocar widgets verticales largos en layouts fijos que provoquen aplastamiento o solapamiento en resoluciones estándar.
- **Scroll segmentado inteligente (sin atascos)**: El contenedor general coordina mediante `FiltroScrollSegmentado` la rueda del ratón entre scrollbars hijos y el scroll general: si el control interno cabe completamente o llega a su extremo superior/inferior, la rueda desplaza fluidamente la página completa; si está en medio de su contenido, se desplaza internamente.
- **Indicadores claros en controles de selección**: Todo `QRadioButton` y `QCheckBox` debe contar con estilo visual explícito de selección (`:checked` con color de acción terracota `{p.accion_principal}`, indicador sólido y texto en negrita) para que el usuario identifique al instante cuál opción está seleccionada.
- **Campos multilínea y bitácoras con expansión vertical controlada**: Toda área de texto editable (prompts, instrucciones, entradas multilínea), listas de selección de columnas y bitácoras DEBEN disponer de redimensionamiento vertical interactivo mediante tirador de cursor (`SizeVerCursor`) con cotas controladas (`EditorTextoExpandible`, `TiradorRedimensionVertical`).
- **Alturas y anchos mínimos garantizados sin truncamiento**: Todo control interactivo (`QPushButton`, `QListWidget`, `QTextEdit`, `QTableWidget`) debe contar con un `minimumHeight` (>=26-32px) y evitar `maximumWidth` rígidos que provoquen truncamiento de texto (por ejemplo "Ninguna" cortado).
- **Sin solapamiento de textos e inputs**: Los labels y campos de entrada deben estar claramente estructurados con espaciados limpios (márgenes consistentes de 8-12px, espaciado de 6-10px) evitando colisiones visuales entre etiquetas y campos.
- **Adaptación por modos de pantalla**: Conectar el evento de redimensionamiento a `adaptar_modo(modo)` usando `ModoPantalla` (COMPACTO, ESTANDAR, AMPLIO) para contraer textos de botones y apilar columnas en pantallas angostas.
- Cargar recursos locales nítidos y componentes funcionales sin decoración excesiva.
- Mantener la acción principal visible y los detalles técnicos accesibles al necesitarlos.
- **Control exacto de barra de progreso**: La barra de progreso de tareas por lotes o procesamiento individual (1 a 1) DEBE reflejar el avance real tras recibir la respuesta de cada registro o tras registrar un fallo/error que avanza al siguiente. Nunca debe incrementar el contador ni reportar 100% de antemano cuando apenas se está enviando la petición.
- **Integración con Gestor de Rutas centralizado**: Los diálogos de selección de archivos (`QFileDialog.getOpenFileName`, `getExistingDirectory`) y visualizadores de carpetas deben iniciar en las subcarpetas segmentadas del `EnrutadorSalidas` (`datos/`, `imagenes/`, `extracciones/`) en lugar de `Path.home()` o rutas dispersas.
- No mostrar porcentajes inventados; usar progreso indeterminado cuando no se mida.
- Una cancelación solicitada se diferencia de una tarea ya cancelada.
- Presentar errores con causa conocida y siguiente acción, sin volcar trazas al usuario.
- Revisar callbacks, señales y datos de presentación al cambiar contratos consumidos.
- No volver a solicitar autorización si el mismo plan ya cuenta con una válida.

## Resultado verificable

La pantalla permanece utilizable durante tareas lentas, respeta la dirección visual,
se adapta de forma fluida a cualquier tamaño de ventana mediante el contenedor responsivo sin
solapamientos ni controles aplastados, y se puede recorrer con teclado. Informar qué escalas
se verificaron realmente; documentar las pendientes sin afirmar que fueron probadas.

