*[Português](README.md) · **English** · [Español](README.es.md)*

# Forja Studio (Estúdio Local)

One panel to generate **images, video and narration** on your own computer, with open-source
AI. No subscription, no credits, no cloud. Install once, use forever.

This is not a new-AI project. The AIs here are public and anyone can download them. **What
this project delivers is the configuration** — which AIs are worth it, tuned how, wired
together in a single screen. It was built on a real machine, making real videos: in 40 days,
**2,253 generations, 98.7% completed**.

> ### 📦 To install: **5 GB**
>
> The whole platform — the panel, the account screen, everything — fits in **~5 GB**. No AI
> model has to be downloaded first. You install it, open it, and you are already using it.
>
> **The AIs come later**, one at a time, through the **"Not installed yet"** button on each
> AI's card, inside the program. You download only the ones you want, when you want, and only
> the ones your computer can handle — the lightest is 16.9 GB.
>
> Set aside **50 GB free** to start comfortably (platform + the first AI).

## Where this stands

**This panel is under development and is used every day by the person who writes it.** It is
not a finished product: it is a working rig that works, published for anyone who wants the
same thing on their own machine.

Improvements come from real use — whatever gets in the way of the day's work is what gets
fixed next. If you use it and hit a rock in the road, **open an issue telling us what you
were trying to do**: that is how things get into the queue.

## What you can do with it

| tab | what it does |
|---|---|
| **Image** | realistic photos, illustration, and turning one of your images into something else |
| **Video** | text or an image becomes video with sound |
| **Talking person** | a front-facing photo + a text becomes someone speaking, lip-synced |
| **Narration** | text becomes voice on your computer, **for free** — create a voice from a description or clone your own |
| **Automatic channel** | the whole pipeline: text → scenes → images → voice → edited video |

And there is the part almost nobody knows is possible: **asking a coding AI to write the
shortcut that automates your work** — and it runs on the AIs you downloaded, with no
per-generation fee.

- [BAT-FEITO-PELA-IA.md](BAT-FEITO-PELA-IA.md) — the idea, and how to ask for it
- [LOTE-DE-VIDEOS.md](LOTE-DE-VIDEOS.md) — **making many videos at once**: how to arrange the
  folders, what to write, and the time math to do before you start

## 🟢 To start: 5.6 GB, not 275

This is the order, and **no model needs to be downloaded before you see the program**:

```
1.  the PLATFORM   →  ~5.6 GB   opens in minutes, you can already sign in and browse
2.  the AIs        →  later, one at a time, through the BUTTON inside the screen
```

Inside, each AI shows its own state:

```
Z-Image Turbo        Not installed yet — 19.3 GB     ← click and download
Qwen-Image 2512      installed
```

You download **only the ones you want**, when you want, and only the ones your machine can
handle. The download runs in the background, you can use the studio meanwhile, and **if it
stops halfway it resumes from where it stopped**.

| for | set aside |
|---|---|
| just trying it out (platform + 1 light AI) | **50 GB** |
| image work, comfortably | ~90 GB |
| everything | 270 GB |

If you only want images, you download **19.3 GB** and that is it.

---

## What you need

> **Before downloading, read [REQUISITOS.md](REQUISITOS.md)** (in Portuguese). It has how much
> disk each AI takes, how much you need for images only or video only, and what was actually
> measured versus what is an estimate. It is 235.7 GB in total: worth the two minutes.

**The panel itself weighs nothing.** With everything running and nothing generating, measured:
**2 GB of RAM and 1.6 GB of VRAM** — the panel alone is 80 MB. What weighs is the AI you load.

| | minimum | comfortable |
|---|---|---|
| **GPU (VRAM)** | **12 GB** — images only | **16 GB** — the whole panel |
| **Memory (RAM)** | **16 GB** — images only | **32 GB**; with 64 GB you never run short |
| **Disk** | **50 GB** to start (platform + 1 AI) | **270 GB** with everything |
| **System** | Windows 10 or 11 | |

Why a 12 GB card runs a 20 GB model: ComfyUI **pushes to RAM** whatever does not fit. It
works — but then RAM is what carries the load, which is why it matters as much as the card.

What each AI loads (measured on this installation):

| AI | models total | largest file |
|---|---|---|
| Krea 2 Turbo | 17.8 GB | 12.2 GB |
| LTX 2.5 | 28.3 GB | 14.3 GB |
| Talking person | 27.6 GB | 15.5 GB |
| Qwen-Image 2512 | 29.6 GB | 19.0 GB |
| MiniMax H3 References | 41.4 GB | 19.5 GB |
| MiniMax H3 Fast | 40.6 GB | 20.6 GB |

> ⚠️ **Do not skimp on RAM.** On a machine with a 16 GB card, running two large AIs at the
> same time made a 1.5-minute scene take **58 minutes** — the machine spent the whole time
> pushing models between the card and the disk. One generation at a time, always.

> ⚠️ **Be honest with yourself about disk space.** It is 275 GB if you want everything — but
> you do NOT need everything to start. On a 100 Mb connection that is a full day. The
> installer lets you pick smaller tracks.

## The machine all of this was measured on

Every number in this repository — generation time, memory use, model size — came from this
machine, not from a manufacturer's table:

| | |
|---|---|
| **GPU** | NVIDIA GeForce RTX 5060 Ti **16 GB** (driver 616.92) |
| **CPU** | Intel Core i9-14900K (24 cores / 32 threads) |
| **Memory** | **64 GB** DDR5 at 6000 MHz (4 sticks) |
| **Disk** | 5.5 TB SSD dedicated to the models |
| **System** | Windows 11 Pro |

**The card is what rules**, and 16 GB is the point where the whole panel works without
tricks. CPU and RAM help with what is left over: ComfyUI pushes to RAM everything that does
not fit on the card, so slow or scarce memory turns into waiting time, not errors.

If your machine is smaller, nothing here breaks — it just takes longer, and the bigger AIs
may not fit. Start with the image track and work your way up.

## Install

Two steps: **download the models** and **apply the configuration**.

- [INSTALAR.md](INSTALAR.md) — step by step, to do by hand (in Portuguese). **The standard place is `C:\ForjaStudio`:** `git clone https://github.com/JJatalaia/forja-studio.git C:\ForjaStudio`
- [INSTALAR-COM-IA.md](INSTALAR-COM-IA.md) — **the text to paste into Claude Code, Codex or
  Gemini CLI and let the AI download and verify everything for you**

**Where every file comes from — every AI and every repository — is in
[REPOSITORIOS.md](REPOSITORIOS.md)** (in Portuguese). 19 repositories on Hugging Face and 4
on GitHub; **18 of the 19 open straight away**, and only `Lightricks/LTX-2.5` asks for an
account and the licence — which is what causes the **401** error on LTX 2.5.

Download links for every model are in [IAS-INSTALADAS.md](IAS-INSTALADAS.md), with the exact
size of each file and the folder it has to land in.

## Using it

It is in [USAR.md](USAR.md) — tab by tab, with the traps that cost us dearly here.

## What we learned the hard way

[APRENDIZADOS.md](APRENDIZADOS.md) — the measured cost of each thing, why images come out
looking AI-made, ComfyUI's memory trap, and the license that can cost you money. It is
probably the most useful part of this repository: anyone can install something.

## The coding AI comes pre-briefed

The project ships a `CLAUDE.md` (and an identical `AGENTS.md`, for Codex and GPT). When you
open a coding AI in this folder, it **reads that on its own** and already knows: speak
Portuguese, how to drive the panel, what each generation costs, and — most importantly —
**to tell you when a repetitive job could become a shortcut**, instead of letting you burn
credits chatting about it every time.

It always offers both options: it builds the shortcut, or it explains and you build it.

## Skills and agents for Claude Code

[SKILLS-E-AGENTES.md](SKILLS-E-AGENTES.md) — the `.claude/` folder ships 2 skills and 3 ready
agents (playwright, director of photography and continuity supervisor). If you do not use
Claude Code, you can delete it: the panel works the same.

## The AIs

The 8 that stayed in the panel, what each one weighs and where each file has to land:
[IAS-INSTALADAS.md](IAS-INSTALADAS.md).

They were not chosen by taste. They were **counted** across a history of 2,253 jobs: whatever
had 10 or more uses in 30 days stayed, the rest left. Nine AIs left the panel that way —
among them one of **69 GB that had been used 4 times in its life**. None were deleted: they
are in `estudio/presets-extras.json`, with instructions on how to switch them back on.

## Security

The studio is a server that runs **on your machine**, and only there: it listens on
`127.0.0.1`, never on `0.0.0.0`. Nobody on your network, or on the internet, reaches it.

**Do not expose this port to the internet.** Not with router port forwarding, not behind a
tunnel, not behind a proxy. There is no password on that port: whoever reaches it commands
the studio, can delete your files and occupy your graphics card. To use it from another
machine, use a VPN or an SSH tunnel — that way the studio still thinks the request came from
inside.

Listening only on `127.0.0.1` **is not enough by itself**, and it is worth knowing why: your
browser reaches `127.0.0.1`. Any page open in another tab could send a command here. That is
why the studio has a **gate** (`portao`, in `estudio/server.py`): every request that changes
something is only accepted if it comes from the studio's own page — a request from another
site gets a 403. Scripts and `.bat` shortcuts keep working normally, because browsers
identify themselves and scripts do not.

What the gate does **not** do: it does not protect you from malicious software already
running inside your machine. No local server protects against that.

## License

**Free, source visible, but not free software.** In three lines (the full text is in
[LICENSE](LICENSE)):

- **You may** download, install and use it for free, including to make money.
- **You must** create a free account. That is a condition of use.
- **You may not** redistribute, resell, or use the Forja configuration anywhere else.

**Whatever you produce here is yours.** Images, videos, audio and text: the author claims
nothing, takes no cut and does not need to be credited.

The source stays visible on purpose — so you know what runs on your machine. Want to do
something the license does not allow? Ask: written permission unlocks it.

[NOTICE](NOTICE) lists the programs Forja talks to and their licenses.

> Until 11 Nov 2026 this project was released under the **Apache License 2.0**. Anyone who
> took a copy in that period keeps that license's rights over that copy.

### ⚠️ But the MODELS' licenses are a different story

The models do not come in this repository: you download them from whoever published them, and
**their license applies**. And they are not all the same:

| | license | can you monetize? |
|---|---|---|
| **VoxCPM 2** (voice) | Apache-2.0 | **yes** |
| **OmniVoice** (voice) | **CC-BY-NC** | **NO** — and it is the engine VoiceStudio turns on by default |
| VoiceStudio (the program) | AGPL-3.0 | it is talked to over the network, never copied |

**If you make money from your videos, switch the voice engine to VoxCPM 2 before
publishing.** The panel shows the active engine's license on the Narration tab — check there.

---

*This is a translation of [README.md](README.md). If the two ever disagree, the Portuguese one
is the original and wins.*
