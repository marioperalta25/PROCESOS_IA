# Portabilidad entre modelos y herramientas

## Qué significa

El modelo interpreta instrucciones; la herramienta descubre archivos, da acceso al
código y ejecuta operaciones. Un archivo neutral puede suministrarse a distintos
LLM, pero no crea esas capacidades ni garantiza cumplimiento o memoria automática.

Entrada común: AGENTS.md en la raíz; núcleo en [reglas/AGENTS.md](../reglas/AGENTS.md). Procedimientos: `SKILL.md` con `name` y `description`.
Estado breve y referencias duraderas: archivos Markdown sin SDK, base vectorial
ni servicio obligatorio. No duplicar el núcleo para cada proveedor.

## Integración por herramienta

Revisión documental: 21 de octubre de 2026. La tabla describe documentación pública,
no pruebas realizadas en estas herramientas desde este proyecto.

| Entorno | Carga a comprobar |
| --- | --- |
| Compatible con AGENTS.md | Archivo raíz, alcance de instrucciones anidadas y límites de carga |
| Codex | Instrucciones de proyecto y habilidades seleccionadas; verificar archivos efectivamente disponibles |
| GitHub Copilot | Soporte en la superficie utilizada; su documentación admite `.agents/skills` para habilidades de proyecto |
| Claude Code | Soporte de AGENTS.md según versión y configuración; otros archivos de instrucciones pueden desplazarlo |
| Gemini CLI | Archivo de contexto predeterminado GEMINI.md o nombre configurado con `context.fileName` |
| LLM sin acceso al repositorio | Proporcionar explícitamente el núcleo y los fragmentos necesarios; no afirmar que leyó archivos inaccesibles |

Fuentes: [AGENTS.md](https://agents.md/),
[habilidades en OpenAI](https://learn.chatgpt.com/docs/build-skills),
[instrucciones de Copilot](https://docs.github.com/en/copilot/concepts/prompting-and-context/custom-instructions),
[habilidades de Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills),
[memoria e instrucciones de Claude Code](https://code.claude.com/docs/en/memory),
[contexto de Gemini CLI](https://geminicli.com/docs/cli/gemini-md/).

Si un entorno necesita un adaptador, configurarlo al integrar ese entorno y con
el alcance autorizado. Preferir referencia o importación soportada a copias de reglas.
No crear ahora configuraciones globales ni archivos específicos de todos los proveedores.

## Instrucción de entrada manual

```text
Abre AGENTS.md en la raíz y sigue su enlace a las reglas, sin ampliar mi solicitud.
Si puedes leer archivos, abre el núcleo y selecciona solo las habilidades
pertinentes. Si no puedes, indica qué contenido necesitas que te proporcione.
Al retomar una tarea, revalida la memoria breve contra el encargo vigente.
Antes de modificar código, comprueba contratos, consumidores e impacto.
Distingue evidencia, inferencia y pendiente; informa las comprobaciones reales.
```

Una referencia textual no es una importación garantizada. Comprobar qué contenido
recibió la herramienta mediante sus mecanismos de inspección, si existen, y una
tarea de prueba. No aceptar como única evidencia que el modelo diga que leyó todo.

## Herramientas equivalentes

`rg` se recomienda para búsqueda, pero se puede usar un buscador equivalente.
Git se utiliza solo si existe repositorio; en su ausencia, revisar contenido,
fechas o huellas verificables. No inventar revisiones, comandos ni permisos.
Si falta una capacidad, completar lo independiente e indicar la limitación concreta.

La memoria aquí definida guía la recuperación; todavía no hay un programa que la
inyecte en cada petición. Cada integración deberá comprobar ese mecanismo y evaluar
calidad, consumo y adherencia con el modelo y la herramienta que realmente se utilicen.
