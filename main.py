from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, model_validator
from telethon import TelegramClient, errors
import asyncio
import json
import os
import time

class AuthDetails(BaseModel):
    api_id: int
    api_hash: str
    phone: str

    @model_validator(mode="before")
    @classmethod
    def to_py_dict(cls, data):
        return json.loads(data)

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


@app.post("/sign_out")
async def sign_out(details: AuthDetails):
    async with lock:
        try:
            if details.phone not in clients_dict:
                raise HTTPException(status_code=400, detail="Неизвестный клиент")

            client_info = clients_dict[details.phone]
            client = client_info.client

            if not await client.is_user_authorized():
                raise HTTPException(status_code=401, detail="Не авторизован")
            await client.log_out()
            await client.disconnect()
            clients_dict.pop(details.phone)

            return {"message": "Успешное отключение"}
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


@app.post("/send_audio_message")
async def send_audio_message(details: AuthDetails, file: UploadFile):
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
                
            timestamp = int(time.time())
            unique_filename = f"{timestamp}_{file.filename}"
            temp_file_path = f"/tmp/{unique_filename}"
            with open(temp_file_path, "wb") as temp_file:
                audio_data = await file.read()
                temp_file.write(audio_data)
                
            await client.send_file('me', file=temp_file_path, voice_note=True)

            os.remove(temp_file_path)
            
            return {"message": "Аудио отправлено :)"+unique_filename}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
