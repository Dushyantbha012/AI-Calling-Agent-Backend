import asyncio
import base64
import json
import os
from collections import deque
from typing import Dict

# Set tokenizers parallelism to avoid fork warnings with sentence-transformers
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from twilio.rest import Client
from twilio.twiml.voice_response import Connect, VoiceResponse

from logger_config import get_logger
from services.call_context import CallContext
from services.llm_service import LLMFactory
from services.stream_service import StreamService
from services.transcription_service import TranscriptionService
from services.tts_service import TTSFactory


## for ssl verification if needed
"""import ssl
import certifi
ssl_context = ssl.create_default_context(cafile=certifi.where())"""

dotenv.load_dotenv()
app = FastAPI()
logger = get_logger("App")

# Global dictionary to store call contexts for each server instance (should be replaced with a database in production)
global call_contexts
call_contexts = {}


@app.get("/")
async def root():
    """Root health check endpoint for Cloud Run."""
    return {"status": "healthy", "message": "AI Call Backend is running"}


@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run startup and liveness probes."""
    return {"status": "healthy", "timestamp": "2025-07-12"}


@app.post("/incoming")
async def incoming_call() -> HTMLResponse:
    """
    Handles incoming calls from Twilio.
    It creates a TwiML response to connect the call to a WebSocket stream.
    """
    server = os.environ.get("SERVER")
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=f"wss://{server}/connection")  # Connect to the WebSocket endpoint
    response.append(connect)
    return HTMLResponse(content=str(response), status_code=200)


@app.get("/call_recording/{call_sid}")
async def get_call_recording(call_sid: str):
    """Get the recording URL for a specific call."""
    recording = get_twilio_client().calls(call_sid).recordings.list()
    if recording:
        print({"recording_url": f"https://api.twilio.com/{recording[0].uri}"})
        return {"recording_url": f"https://api.twilio.com/{recording[0].uri}"}
    if not recording:
        return {"error": "Recording not found"}
    
# Websocket route for Twilio to get media stream
@app.websocket("/connection")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for handling media streams from Twilio.
    It processes incoming media, transcribes audio, generates LLM responses,
    and streams audio back to Twilio.
    """
    await websocket.accept()

    llm_service_name = os.getenv("LLM_SERVICE", "openai")
    tts_service_name = os.getenv("TTS_SERVICE", "deepgram")

    logger.info(f"Using LLM service: {llm_service_name}")
    logger.info(f"Using TTS service: {tts_service_name}")

    # Initialize services
    llm_service = LLMFactory.get_llm_service(llm_service_name, CallContext())
    
    # Initialize RAG service
    await llm_service.initialize_rag()
    
    stream_service = StreamService(websocket)
    transcription_service = TranscriptionService()
    tts_service = TTSFactory.get_tts_service(tts_service_name)
    
    marks = deque()
    interaction_count = 0

    await transcription_service.connect()

    async def process_media(msg):
        """Processes incoming media messages by decoding the audio payload and sending it to the transcription service."""
        await transcription_service.send(base64.b64decode(msg['media']['payload']))

    async def handle_transcription(text):
        """Handles transcribed text by sending it to the LLM service for processing."""
        nonlocal interaction_count
        if not text:
            return
        logger.info(f"Interaction {interaction_count} – STT -> LLM: {text}")
        await llm_service.completion(text, interaction_count)
        interaction_count += 1

    async def handle_llm_reply(llm_reply, icount):
        """Handles LLM replies by sending them to the TTS service for speech generation."""
        logger.info(f"Interaction {icount}: LLM -> TTS: {llm_reply['partialResponse']}")
        await tts_service.generate(llm_reply, icount)

    async def handle_speech(response_index, audio, label, icount):
        """Handles generated speech by buffering it in the stream service for sending to Twilio."""
        logger.info(f"Interaction {icount}: TTS -> TWILIO: {label}")
        await stream_service.buffer(response_index, audio)

    async def handle_audio_sent(mark_label):
        """Handles audio sent events by adding a mark label to the queue."""
        marks.append(mark_label)

    async def handle_utterance(text, stream_sid):
        """Handles user utterances, clears system if interruption is detected."""
        try:
            if len(marks) > 0 and text.strip():
                logger.info("Intruption detected, clearing system.")
                await websocket.send_json({
                    "streamSid": stream_sid,
                    "event": "clear"
                })
                
                # reset states
                stream_service.reset()
                llm_service.reset()

        except Exception as e:
            logger.error(f"Error while handling utterance: {e}")
            e.print_stack()

    async def handle_function_progress(progress_data, icount):
        """Handles function progress updates by sending them to the LLM and TTS pipelines."""
        logger.info(f"Function progress: {progress_data['message']}")
        
        # Send progress updates through the LLM and TTS pipeline for user feedback
        if progress_data['status'] != 'completed':  # Avoid duplicate messages with final result
            await tts_service.generate({
                "partialResponseIndex": None,
                "partialResponse": progress_data['message']
            }, icount)

    # Register event handlers
    transcription_service.on('utterance', handle_utterance)
    transcription_service.on('transcription', handle_transcription)
    llm_service.on('llmreply', handle_llm_reply)
    llm_service.on('function_progress', handle_function_progress)  # Register directly on llm_service
    tts_service.on('speech', handle_speech)
    stream_service.on('audiosent', handle_audio_sent)

    # Queue for incoming WebSocket messages
    message_queue = asyncio.Queue()

    async def websocket_listener():
        """Listens for incoming messages from the WebSocket and puts them in the message queue."""
        try:
            while True:
                data = await websocket.receive_text()
                await message_queue.put(json.loads(data))
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")

    async def message_processor():
        """Processes messages from the message queue, handling start, media, mark, and stop events."""
        while True:
            msg = await message_queue.get()
            if msg['event'] == 'start':
                # Extract stream and call SIDs from the start event
                stream_sid = msg['start']['streamSid']
                call_sid = msg['start']['callSid']
                
                logger.info(f"Media stream started: {msg}")
                
                # Try to extract caller details from start message
                start_data = msg['start']
                from_number = start_data.get('from')
                to_number = start_data.get('to')
                
                logger.info(f"Call details - From: {from_number}, To: {to_number}, CallSid: {call_sid}")
                logger.info(f"Full start message for debugging: {json.dumps(start_data, indent=2)}")
                
                owner_phone = os.getenv("OWNER_PHONE_NUMBER")
                logger.info(f"OWNER_PHONE_NUMBER from env: '{owner_phone}'")
                
                user_phone_number = None
                
                # Try to extract caller number from start message first
                if not from_number:
                    logger.warning("No caller number found in Twilio start message - checking alternative sources")
                    
                    # Try to get caller details from Twilio API
                    try:
                        call_details = get_twilio_client().calls(call_sid).fetch()
                        # Fix: Use _from instead of from_ (underscore prefix, not suffix)
                        from_number = getattr(call_details, '_from', None)
                        to_number = getattr(call_details, 'to', None)
                        
                        logger.info(f"Full call details for debugging: {call_details.__dict__}")
                        
                        # Determine which number is the user's number
                        # The number that doesn't match the Twilio phone number is the user's number
                        twilio_number = os.getenv("TWILIO_PHONE_NUMBER") or os.getenv("APP_NUMBER")
                        
                        if from_number and from_number != twilio_number:
                            user_phone_number = from_number
                        elif to_number and to_number != twilio_number:
                            user_phone_number = to_number
                            
                        logger.info(f"Identified user phone number: {user_phone_number}")
                        
                    except Exception as e:
                        logger.error(f"Failed to retrieve caller number from Twilio API: {str(e)}")
                else:
                    # Determine user number from start message
                    twilio_number = os.getenv("TWILIO_PHONE_NUMBER") or os.getenv("APP_NUMBER")
                    if from_number != twilio_number:
                        user_phone_number = from_number
                    elif to_number != twilio_number:
                        user_phone_number = to_number

                call_context = CallContext()

                if os.getenv("RECORD_CALLS") == "true":
                    get_twilio_client().calls(call_sid).recordings.create({"recordingChannels": "dual"})

                # Store user phone number in call context for future use
                if user_phone_number:
                    call_context.user_phone_number = user_phone_number
                    logger.info(f"Stored user phone number in context: {user_phone_number}")

                # Decide if the call the call was initiated from the UI or is an inbound
                if call_sid not in call_contexts:
                    # Inbound call
                    call_context.system_message = os.environ.get("SYSTEM_MESSAGE")
                    call_context.initial_message = os.environ.get("INITIAL_MESSAGE")
                    call_context.call_sid = call_sid
                    call_contexts[call_sid] = call_context
                else:
                    # Call from UI, reuse the existing context
                    call_context = call_contexts[call_sid]
                    # Update with user phone number if we extracted it
                    if user_phone_number:
                        call_context.user_phone_number = user_phone_number
                
                llm_service.set_call_context(call_context)

                stream_service.set_stream_sid(stream_sid)
                transcription_service.set_stream_sid(stream_sid)

                logger.info(f"Twilio -> Starting Media Stream for {stream_sid}")
                await tts_service.generate({
                    "partialResponseIndex": None,
                    "partialResponse": call_context.initial_message
                }, 1)
            elif msg['event'] == 'media':
                asyncio.create_task(process_media(msg))
            elif msg['event'] == 'mark':
                label = msg['mark']['name']
                if label in marks:
                    marks.remove(label)
            elif msg['event'] == 'stop':
                logger.info(f"Twilio -> Media stream {stream_sid} ended.")
                break
            message_queue.task_done()

    try:
        listener_task = asyncio.create_task(websocket_listener())
        processor_task = asyncio.create_task(message_processor())

        await asyncio.gather(listener_task, processor_task)
    except asyncio.CancelledError:
        logger.info("Tasks cancelled")
    finally:
        await transcription_service.disconnect()

def get_twilio_client():
    """Retrieves a Twilio client using credentials from environment variables."""
    return Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

@app.post("/start_call")
async def start_call(request: Dict[str, str]):
    """Initiate a call using Twilio with optional system and initial messages."""
    to_number = request.get("to_number")
    user_email = request.get("user_email")
    system_message = request.get("system_message")
    initial_message = request.get("initial_message")
    logger.info(f"Initiating call to {to_number} with email: {user_email}")

    service_url = f"https://{os.getenv('SERVER')}/incoming"

    if not to_number:
        return {"error": "Missing 'to_number' in request"}

    try:
        client = get_twilio_client()
        logger.info(f"Initiating call to {to_number} via {service_url}")
        call = client.calls.create(
            to=to_number,
            from_=os.getenv("APP_NUMBER"),
            url=f"{service_url}"
        )
        call_sid = call.sid
        call_context = CallContext()
        call_contexts[call_sid] = call_context
        

        # Set custom system and initial messages for this call if provided
        call_context.system_message = system_message or os.getenv("SYSTEM_MESSAGE")
        call_context.initial_message = initial_message or os.getenv("Config.INITIAL_MESSAGE")
        call_context.call_sid = call_sid
        
        # Store user email if provided
        if user_email:
            call_context.user_email = user_email
            logger.info(f"Stored user email for call {call_sid}: {user_email}")

        return {"call_sid": call_sid}
    except Exception as e:
        logger.error(f"Error initiating call: {str(e)}")
        return {"error": f"Failed to initiate call: {str(e)}"}

# API route to get the status of a call
@app.get("/call_status/{call_sid}")
async def get_call_status(call_sid: str):
    """Get the status of a call."""
    try:
        client = get_twilio_client()
        call = client.calls(call_sid).fetch()
        return {"status": call.status}
    except Exception as e:
        logger.error(f"Error fetching call status: {str(e)}")
        return {"error": f"Failed to fetch call status: {str(e)}"}

# API route to end a call
@app.post("/end_call")
async def end_call(request: Dict[str, str]):
    """Get the status of a call."""
    try:
        call_sid = request.get("call_sid")
        client = get_twilio_client()
        client.calls(call_sid).update(status='completed')
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error ending call {str(e)}")
        return {"error": f"Failed to end requested call: {str(e)}"}

# API call to get the transcript for a specific call
@app.get("/transcript/{call_sid}")
async def get_transcript(call_sid: str):
    """Get the entire transcript for a specific call."""
    call_context = call_contexts.get(call_sid)

    if not call_context:
        logger.info(f"[GET] Call not found for call SID: {call_sid}")
        return {"error": "Call not found"}

    return {"transcript": call_context.user_context}

# API route to get all call transcripts
@app.get("/all_transcripts")
async def get_all_transcripts():
    """Get a list of all current call transcripts."""
    try:
        transcript_list = []
        for call_sid, context in call_contexts.items():
            transcript_list.append({
                "call_sid": call_sid,
                "transcript": context.user_context,
            })
        return {"transcripts": transcript_list}
    except Exception as e:
        logger.error(f"Error fetching all transcripts: {str(e)}")
        return {"error": f"Failed to fetch all transcripts: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    logger.info(f"Backend server address set to: {os.getenv('SERVER')}")
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

