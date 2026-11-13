*[Português](README.md) · [English](README.en.md) · **Español***

# Forja Studio (Estudio Local)

Un solo panel para generar **imágenes, vídeo y narración** en tu propio ordenador, con IA de
código abierto. Sin suscripción, sin créditos, sin nube. Lo instalas una vez y lo usas para
siempre.

No es un proyecto de IA nueva. Las IAs que hay aquí son públicas y cualquiera puede
descargarlas. **Lo que este proyecto entrega es la configuración**: qué IAs valen la pena,
ajustadas de qué manera, conectadas entre sí en una sola pantalla. Se construyó en una máquina
real, haciendo vídeos reales: en 40 días, **2.253 generaciones, 98,7% completadas**.

> ### 📦 Para instalar: **5 GB**
>
> La plataforma entera —el panel, la pantalla de cuenta, todo— cabe en **unos 5 GB**. No hace
> falta descargar ningún modelo de IA antes. Lo instalas, lo abres y ya lo estás usando.
>
> **Las IAs vienen después**, una a una, con el botón **"Todavía no instalada"** que hay en la
> ficha de cada IA, dentro del programa. Descargas solo las que quieres, cuando quieres, y
> solo las que tu ordenador aguanta: la más ligera son 16,9 GB.
>
> Reserva **50 GB libres** para empezar con holgura (plataforma + la primera IA).

## En qué punto está esto

**Este panel está en desarrollo y lo usa cada día la persona que lo escribe.** No es un
producto terminado: es una herramienta de trabajo que funciona, publicada para quien quiera lo
mismo en su propia máquina.

Las mejoras nacen del uso real: lo que estorba en el trabajo del día es lo próximo que se
arregla. Si lo usas y te topas con una piedra en el camino, **abre un issue contando qué
estabas intentando hacer**: así es como las cosas entran en la cola.

## Qué puedes hacer con él

| pestaña | qué hace |
|---|---|
| **Imagen** | fotos realistas, ilustración, y convertir una imagen tuya en otra cosa |
| **Vídeo** | un texto o una imagen se convierten en vídeo con sonido |
| **Persona hablando** | una foto de frente + un texto se convierten en alguien hablando, con los labios sincronizados |
| **Narración** | el texto se convierte en voz en tu ordenador, **gratis**: crea una voz a partir de una descripción o clona la tuya |
| **Canal automático** | el proceso entero: texto → escenas → imágenes → voz → vídeo montado |

Y está la parte que casi nadie sabe que es posible: **pedirle a una IA de programación que
escriba el atajo que automatiza tu trabajo**, y que ese atajo funcione con las IAs que
descargaste, sin pagar por generación.

- [BAT-FEITO-PELA-IA.md](BAT-FEITO-PELA-IA.md) — la idea, y cómo pedirlo (en portugués)
- [LOTE-DE-VIDEOS.md](LOTE-DE-VIDEOS.md) — **hacer muchos vídeos de una vez**: cómo organizar
  las carpetas, qué escribir y la cuenta de tiempo que conviene hacer antes de empezar (en
  portugués)

## 🟢 Para empezar: 5,6 GB, no 275

Este es el orden, y **no hace falta descargar ningún modelo antes de ver el programa**:

```
1.  la PLATAFORMA  →  ~5,6 GB   abre en minutos, ya puedes entrar en tu cuenta y navegar
2.  las IAs        →  después, una a una, con el BOTÓN que hay dentro de la pantalla
```

Dentro, cada IA muestra su propio estado:

```
Z-Image Turbo        Todavía no instalada — 19,3 GB     ← pulsa y descarga
Qwen-Image 2512      instalada
```

Descargas **solo las que quieres**, cuando quieres, y solo las que tu máquina aguanta. La
descarga va en segundo plano, puedes usar el estudio mientras tanto, y **si se corta por la
mitad, sigue desde donde se quedó**.

| para | reserva |
|---|---|
| solo probar (plataforma + 1 IA ligera) | **50 GB** |
| trabajar con imagen, con holgura | ~90 GB |
| todo | 270 GB |

Si solo quieres imágenes, descargas **19,3 GB** y ya está.

---

## Qué necesitas

> **Antes de descargar, lee [REQUISITOS.md](REQUISITOS.md)** (en portugués). Tiene cuánto
> disco ocupa cada IA, cuánto necesitas solo para imagen o solo para vídeo, y qué se midió de
> verdad frente a lo que es una estimación. Son 235,7 GB en total: vale los dos minutos.

**El panel en sí no pesa nada.** Con todo encendido y sin generar nada, medido: **2 GB de RAM
y 1,6 GB de VRAM** —el panel solo son 80 MB—. Lo que pesa es la IA que cargas.

| | mínimo | cómodo |
|---|---|---|
| **GPU (VRAM)** | **12 GB** — solo imagen | **16 GB** — el panel entero |
| **Memoria (RAM)** | **16 GB** — solo imagen | **32 GB**; con 64 GB nunca te falta |
| **Disco** | **50 GB** para empezar (plataforma + 1 IA) | **270 GB** con todo |
| **Sistema** | Windows 10 u 11 | |

Por qué una tarjeta de 12 GB mueve un modelo de 20 GB: ComfyUI **empuja a la RAM** lo que no
cabe. Funciona, pero entonces es la RAM la que carga con el peso, y por eso importa tanto como
la tarjeta.

Lo que carga cada IA (medido en esta instalación):

| IA | modelos en total | archivo más grande |
|---|---|---|
| Krea 2 Turbo | 17,8 GB | 12,2 GB |
| LTX 2.5 | 28,3 GB | 14,3 GB |
| Persona hablando | 27,6 GB | 15,5 GB |
| Qwen-Image 2512 | 29,6 GB | 19,0 GB |
| MiniMax H3 References | 41,4 GB | 19,5 GB |
| MiniMax H3 Fast | 40,6 GB | 20,6 GB |

> ⚠️ **No escatimes en RAM.** En una máquina con una tarjeta de 16 GB, tener dos IAs grandes
> encendidas a la vez hizo que una escena de minuto y medio tardara **58 minutos**: la máquina
> se pasó todo el rato moviendo modelos entre la tarjeta y el disco. Una generación cada vez,
> siempre.

> ⚠️ **Sé honesto contigo mismo con el espacio en disco.** Son 275 GB si lo quieres todo,
> pero **no** necesitas todo para empezar. Con una conexión de 100 Mb eso es un día entero. El
> instalador te deja elegir caminos más cortos.

## La máquina donde se midió todo esto

Cada número de este repositorio —tiempo de generación, uso de memoria, tamaño de los modelos—
salió de esta máquina, no de la tabla de un fabricante:

| | |
|---|---|
| **GPU** | NVIDIA GeForce RTX 5060 Ti **16 GB** (driver 616.92) |
| **CPU** | Intel Core i9-14900K (24 núcleos / 32 hilos) |
| **Memoria** | **64 GB** DDR5 a 6000 MHz (4 módulos) |
| **Disco** | SSD de 5,5 TB dedicado a los modelos |
| **Sistema** | Windows 11 Pro |

**La tarjeta es la que manda**, y 16 GB es el punto en el que el panel entero funciona sin
trucos. La CPU y la RAM ayudan con lo que sobra: ComfyUI empuja a la RAM todo lo que no cabe
en la tarjeta, así que una memoria lenta o escasa se convierte en tiempo de espera, no en
errores.

Si tu máquina es más pequeña, aquí no se rompe nada: simplemente tarda más, y puede que las
IAs más grandes no quepan. Empieza por el camino de la imagen y ve subiendo.

## Instalación

Dos pasos: **descargar los modelos** y **aplicar la configuración**.

- [INSTALAR.md](INSTALAR.md) — paso a paso, para hacerlo a mano (en portugués). **El lugar estándar es `C:\ForjaStudio`:** `git clone https://github.com/JJatalaia/forja-studio.git C:\ForjaStudio`
- [INSTALAR-COM-IA.md](INSTALAR-COM-IA.md) — **el texto para pegar en Claude Code, Codex o
  Gemini CLI y dejar que la IA descargue y verifique todo por ti** (en portugués)

**De dónde viene cada cosa — todas las IAs y todos los repositorios — está en
[REPOSITORIOS.md](REPOSITORIOS.md)** (en portugués). Son 19 repositorios en Hugging Face y 4
en GitHub; **18 de los 19 se abren directamente**, y solo `Lightricks/LTX-2.5` pide cuenta y
aceptar la licencia — que es lo que provoca el error **401** en LTX 2.5.

Los enlaces de descarga de todos los modelos están en
[IAS-INSTALADAS.md](IAS-INSTALADAS.md), con el tamaño exacto de cada archivo y la carpeta
donde tiene que caer.

## Cómo se usa

Está en [USAR.md](USAR.md) — pestaña por pestaña, con las trampas que aquí nos salieron caras
(en portugués).

## Lo que aprendimos a golpes

[APRENDIZADOS.md](APRENDIZADOS.md) — el coste medido de cada cosa, por qué las imágenes salen
con cara de IA, la trampa de memoria de ComfyUI y la licencia que te puede costar dinero. Es
probablemente la parte más útil de este repositorio: instalar algo lo hace cualquiera.

## La IA de programación llega con la lección aprendida

El proyecto trae un `CLAUDE.md` (y un `AGENTS.md` idéntico, para Codex y GPT). Cuando abres
una IA de programación en esta carpeta, **lo lee por su cuenta** y ya sabe: hablar portugués,
cómo manejar el panel, cuánto cuesta cada generación y —lo más importante— **avisarte cuando
un trabajo repetitivo podría convertirse en un atajo**, en vez de dejarte quemar créditos
hablando de ello cada vez.

Siempre ofrece las dos opciones: construye el atajo, o te lo explica y lo construyes tú.

## Skills y agentes para Claude Code

[SKILLS-E-AGENTES.md](SKILLS-E-AGENTES.md) — la carpeta `.claude/` trae 2 skills y 3 agentes
listos (playwright, director de fotografía y script supervisor). Si no usas Claude Code,
puedes borrarla: el panel funciona igual.

## Las IAs

Las 8 que se quedaron en el panel, cuánto pesa cada una y dónde tiene que caer cada archivo:
[IAS-INSTALADAS.md](IAS-INSTALADAS.md).

No se eligieron por gusto. Se **contaron** a lo largo de un historial de 2.253 trabajos: lo
que tenía 10 usos o más en 30 días se quedó, el resto se fue. Nueve IAs salieron del panel
así, entre ellas una de **69 GB que se había usado 4 veces en su vida**. Ninguna se borró:
están en `estudio/presets-extras.json`, con las instrucciones para volver a encenderlas.

## Seguridad

El estudio es un servidor que funciona **en tu máquina**, y solo ahí: escucha en
`127.0.0.1`, nunca en `0.0.0.0`. Nadie de tu red, ni de internet, llega hasta él.

**No expongas este puerto a internet.** Ni abriendo puertos en el router, ni detrás de un
túnel, ni detrás de un proxy. En ese puerto no hay contraseña: quien llegue hasta él manda en
el estudio, puede borrar tus archivos y ocupar tu tarjeta gráfica. Para usarlo desde otra
máquina, usa una VPN o un túnel SSH: así el estudio sigue creyendo que la petición vino de
dentro.

Escuchar solo en `127.0.0.1` **no basta por sí solo**, y vale la pena saber por qué: tu
navegador sí llega a `127.0.0.1`. Cualquier página abierta en otra pestaña podría mandar una
orden hasta aquí. Por eso el estudio tiene un **portón** (`portao`, en `estudio/server.py`):
toda petición que cambie algo solo se acepta si viene de la propia página del estudio; una
petición de otro sitio recibe un 403. Los scripts y los atajos `.bat` siguen funcionando con
normalidad, porque los navegadores se identifican y los scripts no.

Lo que el portón **no** hace: no te protege de un programa malicioso que ya esté corriendo
dentro de tu máquina. Ningún servidor local protege de eso.

## Licencia

**Gratis, con el código a la vista, pero no es software libre.** En tres líneas (el texto
completo está en [LICENSE](LICENSE)):

- **Puedes** descargarlo, instalarlo y usarlo gratis, incluso para ganar dinero.
- **Tienes que** crear una cuenta gratuita. Es una condición de uso.
- **No puedes** redistribuirlo, revenderlo, ni usar la configuración de Forja en otro sitio.

**Lo que produzcas aquí es tuyo.** Imágenes, vídeos, audio y texto: el autor no reclama nada,
no se lleva ninguna parte y no necesita que se le dé crédito.

El código se queda a la vista a propósito, para que sepas qué corre en tu máquina. ¿Quieres
hacer algo que la licencia no permite? Pregunta: un permiso por escrito lo desbloquea.

[NOTICE](NOTICE) enumera los programas con los que Forja habla y sus licencias.

> Hasta el 11 de noviembre de 2026 este proyecto se publicaba bajo la **Apache License 2.0**.
> Quien se llevó una copia en ese periodo conserva los derechos de esa licencia sobre esa
> copia.

### ⚠️ Pero la licencia de los MODELOS es otra historia

Los modelos no vienen en este repositorio: los descargas de quien los publicó, y **se aplica
la licencia de ellos**. Y no son todas iguales:

| | licencia | ¿puedes monetizar? |
|---|---|---|
| **VoxCPM 2** (voz) | Apache-2.0 | **sí** |
| **OmniVoice** (voz) | **CC-BY-NC** | **NO** — y es el motor que VoiceStudio enciende por defecto |
| VoiceStudio (el programa) | AGPL-3.0 | se habla con él por red, nunca se copia |

**Si ganas dinero con tus vídeos, cambia el motor de voz a VoxCPM 2 antes de publicar.** El
panel muestra la licencia del motor activo en la pestaña de Narración: míralo ahí.

---

*Esta es una traducción de [README.md](README.md). Si alguna vez los dos no coinciden, el de
portugués es el original y es el que vale.*
