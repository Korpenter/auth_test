from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient
import asyncio

app = FastAPI()
class AuthDetails(BaseModel):
    api_id: int
    api_hash: str
    phone: str

class VerifyDetails(AuthDetails):
    code: str

clients_dict = {}
lock = asyncio.Lock()

@app.post("/start_auth")
async def start_auth(details: AuthDetails):
    async with lock:
        try:
            if details.phone not in clients_dict:
                client = TelegramClient(details.phone, details.api_id, details.api_hash)
                await client.connect()
                clients_dict[details.phone] = client
            else:
                client = clients_dict[details.phone]
                
            if not await client.is_user_authorized():
                await client.send_code_request(details.phone)
                return {"message": "Code sent, awaiting verification"}
            return {"message": "Already authorized"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify_code")
async def verify_code(details: VerifyDetails):
    async with lock:
        try:
            if details.phone not in clients_dict:
                client = TelegramClient(details.phone, details.api_id, details.api_hash)
                await client.connect()
                clients_dict[details.phone] = client
            else:
                client = clients_dict[details.phone]
                
            await client.sign_in(details.phone, details.code)
            return {"message": "Signed in successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/send_message")
async def send_message(details: AuthDetails, message: str = "Hello from FastAPI!"):
    async with lock:
        try:
            if details.phone not in clients_dict or not clients_dict[details.phone].is_connected():
                client = TelegramClient(details.phone, details.api_id, details.api_hash)
                await client.connect()
                clients_dict[details.phone] = client
            else:
                client = clients_dict[details.phone]

            if not await client.is_user_authorized():
                raise HTTPException(status_code=401, detail="User not authorized")
            
            await client.send_message('me', message)
            return {"message": "Message sent successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))