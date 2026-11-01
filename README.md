# Afterlight - Yaadein Rehti Hain

Afterlight is a small, local-first place to save memories of people who matter to us. You can write about an ordinary afternoon, a family recipe, a train journey, a festival or a phrase that still comes to mind. A local AI model helps shape those notes into a short remembrance and a one-line keepsake.

The idea is simple: in many Indian families, memories are carried through everyday details - the chai someone made, the way a grandparent asked if everyone had eaten, a familiar voice during a long train ride or the food prepared when everyone came home. Those details are personal, so the project keeps them on the device. Users can write in English, Hinglish or their own mix.

The project uses **Google Gemma 3 4B (`gemma3:4b`) through Ollama**. The browser talks to a small Python server on `127.0.0.1`, which sends the prompt to Ollama on the same machine. After the model has been downloaded once, generating and saving memories can work offline.

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 4: Ghost in the Machine](https://dev.to/challenges/hacktoberfest-week4-2026-10-26)*

## What I Built

- **A personal remembrance writer.** Add a name, relationship, memory, favourite details and remembered words. Gemma 3 4B turns them into a title, a short remembrance and a lantern note.
- **A private local archive.** Saved entries are stored in `data/keepsakes.json` inside the project folder.
- **An export you control.** Download the complete archive as a JSON file.
- **A model status check.** The app checks whether Ollama is running and whether `gemma3:4b` is installed.
- **A replaceable setup.** The model is set in one place in `app.py`; the prompt and application code can be changed without depending on a hosted service.

## Demo

![Image description](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/by7nwnlbkbavhhcramcc.png)

![Image description](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/ed7x9ag3wd66ke9yhs68.png)

![Image description](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/rhmgf2s5vwxv1j3dw524.png)

## Code

Explore the source code, setup instructions and implementation:
https://github.com/BharatwaleJain/AfterLight

## How I Built It

The frontend is plain HTML, CSS, and JavaScript. The backend is a small Python HTTP server using the standard library, so there are no Python packages to install. It serves the page, validates incoming memory fields, stores saved entries as JSON and calls Ollama's local chat endpoint when a remembrance is generated.

```text
Browser (HTML / CSS / JavaScript)
       │
       │ memory form, archive, export
       ▼
Python server (127.0.0.1:8765)
       │
       │ local HTTP request
       ▼
Ollama (127.0.0.1:11434)
       │
       ▼
Gemma 3 4B open-weight model
       │
       │ title + remembrance + lantern note
       ▼
Browser output

Saved memories ──► data/keepsakes.json on this device
```

## Why Does Open Innovation Matter?

These memories can be personal. I did not want the main feature to depend on sending someone's family stories to a third-party server. Gemma 3 4B runs through Ollama on the same machine, so the text used for generation stays local. Once the model is downloaded, the app can generate a remembrance without an internet connection.

Using an open-weight model also makes the project easier to inspect and change. I can adjust the writing prompt, experiment with another model available in Ollama, or modify the application without building around a paid API. The model can run on a personal computer, although the 4B model needs more memory and processing power than the smallest models.

## The Spirit of It

In a lot of homes, someone is remembered through a very ordinary sentence. "Have you eaten?" "Take some more." "Call when you reach." Those little lines can carry more than a formal biography ever could. I wanted Afterlight to make room for that kind of memory, without pretending that an AI can replace the person behind it.

## Prize Categories

**Gemma — Best Use of Gemma:** Afterlight uses Google's Gemma 3 4B open-weight model as the core writing engine. The model runs locally through Ollama and turns user-provided memories into a remembrance, without sending the content to a hosted AI API.

## Quick Setup

Download Python 3.10 or newer and [Ollama](https://ollama.com/download).

```bash
ollama pull gemma3:4b
ollama serve
python app.py
```

Open **http://127.0.0.1:8765** in your browser.

1. Enter a name and a memory. Relationship, favourite details and remembered words are optional.
2. Write naturally. English, Hinglish and regional words can be mixed in the same entry.
3. Select **Light a lantern** to generate a title, remembrance, and one-line note using Gemma 3 4B.
4. Select **Save memory** to keep the entry in your local archive.
5. Select an archive card to reopen it. Use **Export memories** to download a JSON copy.

## Privacy and Limitations

- Saved memories are stored in `data/keepsakes.json` in the project folder. Keep that file private if it contains personal information.
- The text submitted for generation is sent from the Python app to Ollama on `127.0.0.1`, not to a hosted AI API. Do not expose the Ollama port or the Afterlight server to a public network.
- The first Gemma model download requires internet access. Subsequent inference is local.
- This version stores text only. It does not record audio, store photographs or sync memories between devices.
- AI-generated text can make mistakes or add an unsupported detail. Read the remembrance before saving or sharing it.