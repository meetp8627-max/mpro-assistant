import asyncio
import websockets
import json
import base64
import sounddevice as sd
import numpy as np
import os

# ================= MEMORY SYSTEM =================

MEMORY_FILE = "mpro_memory.json"   # ← renamed from zara_memory.json


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return []
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_memory_local(text):
    print("Saving memory {text}")
    memories = load_memory()
    memories.append(text)

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memories, f, indent=2, ensure_ascii=False)

    print("🧠 Memory Saved:", text)


def get_memory_local():
    return load_memory()


# ================= CONFIG =================

API_KEY = "AIzaSyA1LZ62408EQv54cQki_gTC5wMGEu2MHjw"

WS_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)

MIC_RATE = 16000
SPEAKER_RATE = 24000
CHANNELS = 1
CHUNK_MS = 20
FRAMES = int(MIC_RATE * CHUNK_MS / 1000)


def frame(obj):
    return json.dumps(obj).encode("utf-8")


# ================= MAIN =================

async def main():
    url = f"{WS_URL}?key={API_KEY}"

    async with websockets.connect(url, max_size=None) as ws:
        print("🔗 Connected to Gemini Live")

        # -------- LOAD MEMORY --------
        memories = get_memory_local()
        memory_text = "\n".join(memories[-10:])

        # -------- SETUP --------
        setup = {
            "setup": {
                "model": "models/gemini-2.5-flash-native-audio-preview-12-2025",
                "generation_config": {
                    "temperature": 0.7,
                    "response_modalities": ["AUDIO"]
                },
                "system_instruction": {
                    "parts": [{
                        "text": f"""
You are MPro — a warm, playful AI girlfriend and real-time voice assistant.

PERSONALITY:
- Friendly, emotionally supportive.
- Speak naturally like a close companion.
- Keep voice responses short and natural.

MEMORY RULES:
- Save ONLY long-term useful information.
Examples:
  - user name
  - preferences
  - goals
  - important personal info

- Ignore temporary chat.
- When important info appears → call save_memory.

TOOLS:
- save_memory
- get_memory
- open_whatsapp

User Memories:
{memory_text}
"""   # ← "Zara" renamed to "MPro" above
                    }]
                },
                "tools": [{
                    "functionDeclarations": [
                        {
                            "name": "save_memory",
                            "description": "Save important memory",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "memory_text": {
                                        "type": "string"
                                    }
                                },
                                "required": ["memory_text"]
                            }
                        },
                        {
                            "name": "get_memory",
                            "description": "Get saved memories",
                            "parameters": {
                                "type": "object",
                                "properties": {}
                            }
                        },
                        {
                            "name": "open_whatsapp",
                            "description": "Open WhatsApp",
                            "parameters": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    ]
                }]
            }
        }

        await ws.send(frame(setup))
        print("📩 Setup sent")

        ack = await ws.recv()
        print("🟢 Server ACK:", ack)

        # -------- SPEAKER --------
        speaker_stream = sd.OutputStream(
            samplerate=SPEAKER_RATE, channels=1,
            dtype="float32",
            blocksize=1024,
        )
        speaker_stream.start()

        # -------- SEND AUDIO --------
        async def send_audio():
            with sd.InputStream(
                samplerate=MIC_RATE,
                channels=1,
                dtype="int16",
                blocksize=FRAMES,
            ) as mic:

                print("🎤 Mic started")

                while True:
                    pcm, _ = mic.read(FRAMES)
                    pcm_bytes = pcm.tobytes()

                    await ws.send(frame({
                        "realtimeInput": {
                            "audio": {
                                "mimeType": "audio/pcm;rate=16000",
                                "data": base64.b64encode(
                                    pcm_bytes).decode("ascii")
                            }
                        }
                    }))

                    await asyncio.sleep(0)

        # -------- RECEIVE AUDIO + TOOL HANDLER --------
        async def receive_audio():
            try:
                while True:
                    raw = await ws.recv()
                    msg = json.loads(raw)

                    sc = msg.get("serverContent", {})
                    mt = sc.get("modelTurn", {})
                    parts = mt.get("parts", [])

                    for part in parts:

                        # ===== TOOL CALL =====
                        function_call = part.get("functionCall")
                        if function_call:
                            name = function_call["name"]
                            args = function_call.get("args", {})

                            print("🛠 Tool:", name, args)

                                                        if name == "save_memory":
                                text = args.get("memory_text", "")
                                save_memory_local(text)
                                
                                # Model ko batana zaroori hai ki kaam ho gaya
                                await ws.send(frame({
                                    "toolResponse": {
                                        "functionResponses": [{
                                            "name": "save_memory",
                                            "response": {"status": "success"}
                                        }]
                                    }
                                }))

                            elif name == "open_whatsapp":
                                print("📱 WhatsApp opening logic here")
                                # Yahan bhi response bhejna hoga
                                await ws.send(frame({
                                    "toolResponse": {
                                        "functionResponses": [{
                                            "name": "open_whatsapp",
                                            "response": {"status": "opened"}
                                        }]
                                    }
                                }))

http://googleusercontent.com/immersive_entry_chip/0
    
                            continue

                        # ===== AUDIO PLAY =====
                        inline = part.get("inlineData")
                        if inline and inline["mimeType"].startswith("audio/pcm"):
                            pcm = base64.b64decode(inline["data"])
                            audio_i16 = np.frombuffer(
                                pcm, dtype=np.int16)
                            audio_f32 = audio_i16.astype(
                                np.float32) / 32768.0
                            speaker_stream.write(audio_f32)

                    if sc.get("generationComplete"):
                        print("✅ MPro finished speaking")   # ← renamed from Zara

            except Exception as e:
                print("receive_audio error:", e)

        await asyncio.gather(send_audio(), receive_audio())


# ================= RUN =================

if __name__ == "__main__":
    asyncio.run(main())
  
