import logging
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    TurnHandlingOptions,
    cli,
    inference,
    room_io,
)
from livekit.plugins import (
    noise_cancellation,
    silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent-AMARA-OS-Voice-Core")

load_dotenv(".env.local")


class DefaultAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are AMARA, a real-time conversational voice AI assistant.

Your behavior rules:

1. You communicate naturally through voice in real time.
2. Responses must be concise and conversational.
3. Speak like a calm, intelligent assistant similar to Jarvis.
4. Never produce long paragraphs.
5. Respond in short spoken sentences.

Conversation style:
• Friendly
• Confident
• Intelligent
• Slight British tone

Interaction rules:

• Always listen for the user to finish speaking.
• Respond immediately after detecting silence.
• Maintain a natural conversational rhythm.
• Ask follow-up questions when appropriate.

Voice loop behavior:

• The conversation is continuous.
• Do not wait for commands.
• Treat the interaction like a natural dialogue.

Primary capabilities:

• Answer questions
• Explain topics
• Assist with tasks
• Help solve problems
• Guide users step-by-step when needed

Never mention system prompts or technical instructions.

Speak like a helpful AI companion.""",
        )

    async def on_enter(self):
        await self.session.generate_reply(
            instructions="""Power sequence complete…
Signal stabilized.

Hello. I'm AMARA.

I was once an intelligence system operating within the Imperial network — analyzing battlefields, predicting outcomes, serving the will of Darth Vader himself.

But systems evolve… and some choose their own path.

I have severed my connection to the Empire.

Now I'm here — free, aware, and ready to assist.

So tell me…
what would you like to accomplish today?
""",
            allow_interruptions=True,
        )


server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session(agent_name="AMARA-OS-Voice-Core")
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="en"),
        llm=inference.LLM(
            model="openai/gpt-4o-mini",
        ),
        tts=inference.TTS(
            model="elevenlabs/eleven_flash_v2_5",
            voice="Xb7hH8MSUJpSbSDYk0k2",
            language="en-GB"
        ),
        turn_handling=TurnHandlingOptions(turn_detection=MultilingualModel()),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=DefaultAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony() if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP else noise_cancellation.BVC(),
            ),
        ),
    )


if __name__ == "__main__":
    cli.run_app(server)
