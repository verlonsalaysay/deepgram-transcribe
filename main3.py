from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, Callable
from deepgram import Deepgram
from dotenv import load_dotenv
import os
import string

load_dotenv()

app = FastAPI()

dg_client = Deepgram(os.getenv('DEEPGRAM_API_KEY'))

templates = Jinja2Templates(directory="templates")

def new_transcript(transcript):
    words=transcript.split()
    sentence=[]
    for character in words:
        if character[-1] in string.punctuation:
                if character[-2].lower()=='a' or character[-2].lower()=='e' or character[-2].lower()=='i' or character[-2].lower()=='o' or character[-1].lower()=='u':
                    word=character[0:len(character)-1]+('-v')
                    word=word+(character[-1])
                else:
                    word=character[0:len(character)-1]+('-c')
                    word=word+(character[-1])
        else:
                if character[-1].lower()=='a' or character[-1].lower()=='e' or character[-1].lower()=='i' or character[-1].lower()=='o' or character[-1].lower()=='u':
                    word=character+'-v'
                else:
                    word=character+'-c'
        sentence.append(word)
    return " ".join(sentence)

async def process_audio(fast_socket: WebSocket):
    async def get_transcript(data: Dict) -> None:
        if 'channel' in data:
            transcript = data['channel']['alternatives'][0]['transcript']
            # print(transcript)
            if transcript:
                await fast_socket.send_text(new_transcript(transcript))
		
    deepgram_socket = await connect_to_deepgram(get_transcript)

    return deepgram_socket

async def connect_to_deepgram(transcript_received_handler: Callable[[Dict], None]):
    try:
        socket = await dg_client.transcription.live({'punctuate': True, 'interim_results': False})
        socket.registerHandler(socket.event.CLOSE, lambda c: print(f'Connection closed with code {c}.'))
        socket.registerHandler(socket.event.TRANSCRIPT_RECEIVED, transcript_received_handler)
        
        return socket
    except Exception as e:
        raise Exception(f'Could not open socket: {e}')
 
@app.get("/", response_class=HTMLResponse)
def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/listen")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        deepgram_socket = await process_audio(websocket) 

        while True:
            data = await websocket.receive_bytes()
            deepgram_socket.send(data)
    except Exception as e:
        raise Exception(f'Could not process audio: {e}')
    finally:
        await websocket.close()