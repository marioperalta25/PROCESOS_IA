# Dirección visual propuesta

Estado: propuesta anterior del asistente. No hay biblioteca ni paleta aprobadas;
no implementar estas sugerencias como consecuencia de leer este documento.

## Carácter

Una herramienta de escritorio clara, sobria y cálida, con identidad propia.
Usar jerarquía tipográfica, espacio y materiales discretos. Evitar saturación de
tarjetas, gradientes decorativos dominantes y efectos que compitan con el contenido.

Base técnica propuesta: PySide6 con Qt Widgets. Los estilos y componentes serán
reutilizables, con valores visuales centralizados. La elección se revisará después
de probar compatibilidad y un primer prototipo; aún no es una dependencia instalada.

Qt ofrece coordenadas independientes de la densidad y soporte de escalado; aun así,
se debe comprobar la presentación en las escalas reales de Windows.
Fuente: [documentación oficial de alta densidad de Qt](https://doc.qt.io/qtforpython-6/overviews/qtdoc-highdpi.html).

## Paleta inicial: tinta, marfil y cobre

| Uso | Valor propuesto |
| --- | --- |
| Fondo general | `#F4F0E8` |
| Superficie principal | `#FFFCF7` |
| Navegación oscura | `#222C2A` |
| Texto principal | `#222C2A` |
| Texto secundario | `#58615B` |
| Acción principal, cobre oscuro | `#9A472E` |
| Texto sobre acción principal | `#FFFCF7` |
| Éxito, verde pino | `#326457` |
| Advertencia, ocre oscuro | `#7A511B` |
| Error, granate | `#962F3C` |
| Separador decorativo | `#D9D1C5` |

Estos valores son una propuesta, no una prueba de accesibilidad. Comprobar las
combinaciones utilizadas: contraste mínimo de 4,5:1 para texto normal y 3:1 para
texto grande e indicadores de controles. El separador decorativo no sustituye
el borde perceptible de un control cuando ese borde sea necesario.

## Composición inicial

- Navegación lateral compacta: Inicio, Conversación, Modelos y Configuración.
- Área central con una tarea principal y estados de conexión comprensibles.
- Gestión de instalación accesible desde Configuración y desde errores pertinentes.
- Diagnóstico ampliado bajo demanda; mantener discreto el estado cotidiano.
- Acciones con verbos concretos: Conectar, Instalar Ollama, Descargar, Cancelar.

Las pantallas se implementarán por etapas; esta lista no implica que ya existan.
La información técnica detallada estará disponible cuando ayude a decidir o resolver
un problema, sin dominar la experiencia cotidiana.

## Nitidez y accesibilidad

- Fuente inicial del sistema: Segoe UI en Windows; usar alternativas disponibles
  en otras plataformas. No descargar fuentes durante el arranque.
- Espaciado basado en múltiplos de cuatro y tamaños adaptables al contenido.
- Recursos vectoriales para iconos funcionales; no usar emojis como iconos.
- Verificar escalado de 100 %, 125 %, 150 % y 200 %, sin textos cortados.
- Navegación por teclado, orden de tabulación y foco visibles.
- Etiquetas accesibles y mensajes que expliquen estado y siguiente acción.
- No comunicar éxito o error únicamente con color.
- Animaciones breves solo si aportan contexto; evitar animaciones permanentes.

## Estados que deben diseñarse

Sin modelos, sin conexión, diagnóstico pendiente, tarea en curso, cancelación,
error recuperable y operación terminada. La interfaz debe seguir respondiendo
mientras se consulta Ollama, se descarga un modelo o se ejecuta una instalación.

Antes de consolidar componentes, revisar el prototipo con textos largos en español,
ventanas pequeñas y escalado elevado. Los tamaños mínimos deben responder a esa
verificación, sin fijar toda la interfaz mediante coordenadas absolutas.
