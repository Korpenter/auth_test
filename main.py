from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from telethon import TelegramClient, errors
import asyncio


class AuthDetails(BaseModel):
    api_id: int
    api_hash: str
    phone: str


class VerifyDetails(AuthDetails):
    code: str
    password: str = None  # 2FA


lock = asyncio.Lock()
app = FastAPI()
clients_dict = {}


class ClientInfo:
    def __init__(self, client, phone_code_hash=None):
        self.client = client
        self.phone_code_hash = phone_code_hash


@app.post("/start_auth")
async def start_auth(details: AuthDetails):
    async with lock:
        try:
            if details.phone not in clients_dict:
                client = TelegramClient(details.phone, details.api_id, details.api_hash, system_version="4.16.30-vxTESTINGBENCH")
                await client.connect()
                sent_code = await client.send_code_request(details.phone)
                phone_code_hash = sent_code.phone_code_hash 
                clients_dict[details.phone] = ClientInfo(client, phone_code_hash)
            else:
                client_info = clients_dict[details.phone]
                client = client_info.client
                
            if not await client.is_user_authorized():
                return {"message": "Введите код авторизации, и пароль от 2FA (если включена)"}
            return {"message": "Авторизован"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify_code")
async def verify_code(details: VerifyDetails):
    async with lock:
        try:
            if details.phone not in clients_dict:
                raise HTTPException(status_code=400, detail="Аутентификация не начата для этого номера телефона")

            client_info = clients_dict[details.phone]
            client = client_info.client
            
            try:
                await client.sign_in(details.phone, details.code, phone_code_hash=client_info.phone_code_hash)
            except errors.SessionPasswordNeededError:
                if details.password:
                    await client.sign_in(password=details.password)
                else:
                    raise HTTPException(status_code=403, detail="2FA включена, повторите с вводом пароля 2FA")

            return {"message": "Авторизован"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/send_message")
async def send_message(details: AuthDetails, message: str = "Hello from FastAPI!"):
    async with lock:
        try:
            if details.phone not in clients_dict or not clients_dict[details.phone].client.is_connected():
                client = TelegramClient(details.phone, details.api_id, details.api_hash, system_version="4.16.30-vxTESTINGBENCH")
                await client.connect()
                clients_dict[details.phone] = ClientInfo(client, "")
            else:
                client = clients_dict[details.phone].client

            if not await client.is_user_authorized():
                raise HTTPException(status_code=401, detail="Не авторизован.")
            
            await client.send_message('me', message)
            return {"message": "message sent"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
