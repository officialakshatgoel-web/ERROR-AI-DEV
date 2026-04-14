import asyncio
import json
import time
import os
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Security, Request
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager

from database import init_db, get_db, verify_api_key, update_persona, get_settings, increment_usage, get_global_usage_stat
from bot import start_bot
from ai_provider import generate_ai_response
import ollama

load_dotenv()

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

def extract_token(auth_header: str) -> str:
    if not auth_header:
        return None
    if auth_header.startswith("Bearer "):
        parts = auth_header.split(" ")
        return parts[1] if len(parts) > 1 else None
    return auth_header

async def get_api_key(auth_header: str = Security(api_key_header), db = Depends(get_db)):
    token = extract_token(auth_header)
    if not token:
        raise HTTPException(status_code=401, detail="Authorization header missing or invalid format")
    
    key_record = verify_api_key(db, token)
    if not key_record:
        raise HTTPException(status_code=403, detail="Invalid API Key")
        
    return key_record

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bot_task = asyncio.create_task(start_bot())
    print("Bot task started.")
    yield
    bot_task.cancel()
    print("Bot task cancelled.")

app = FastAPI(title="Error AI", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- SECURITY MIDDLEWARE ---
@app.middleware("http")
async def block_sensitive_files(request: Request, call_next):
    path = request.url.path.lower()
    # Patterns to block
    blocked_extensions = ['.env', '.db', '.sqlite', '.log', '.git', '.sh', '.py']
    blocked_files = ['serviceaccountkey.json', 'requirements.txt', 'dockerfile', 'readme.md']
    
    # Check if the path is sensitive
    filename = path.split('/')[-1]
    is_sensitive_json = filename.startswith('serviceaccountkey') and filename.endswith('.json')
    
    if any(path.endswith(ext) for ext in blocked_extensions) or filename in blocked_files or is_sensitive_json:
        return JSONResponse(
            status_code=403,
            content={"error": "Access Denied", "message": "You do not have permission to access root files."}
        )
    
    return await call_next(request)

# --- SCHEMAS ---
class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "error-combo"
    messages: list[Message]
    stream: bool = False

class PersonaRequest(BaseModel):
    persona_context: str

class HistoryMessage(BaseModel):
    role: str
    content: str

class PublicChatRequest(BaseModel):
    message: str
    style: str = "Default"
    history: list[HistoryMessage] = []  # Strongly typed conversation history

# --- RATE LIMITER ---
public_chat_limits = {} # simple {ip: last_timestamp}

# --- ENDPOINTS ---

@app.get("/", response_class=HTMLResponse, tags=["Website"])
async def read_index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error AI</h1><p>Landing page not found. Error: {e}</p>"

@app.get("/api/v1/firebase/config", tags=["Website"])
async def get_firebase_config():
    """Returns Firebase public credentials from environment variables."""
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", ""),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        "appId": os.getenv("FIREBASE_APP_ID", ""),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID", "")
    }

@app.get("/documentation", response_class=HTMLResponse, tags=["Website"])
async def read_docs():
    try:
        with open("docs.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error AI Docs</h1><p>Documentation page not found. Error: {e}</p>"


@app.get("/api/v1/config", tags=["Website"])
async def get_public_config():
    settings = get_settings()
    total_reqs = get_global_usage_stat()
    
    # Check Ollama health
    try:
        await ollama.AsyncClient().list()
        status = "ACTIVE"
    except Exception:
        status = "OFFLINE"

    return {
        "status": status,
        "contact": settings.contact_username if settings else "@DARKVENDOR07",
        "default_limit": settings.default_daily_limit if settings else 100,
        "pricing_html": settings.pricing_html if settings else "",
        "total_requests": total_reqs
    }



@app.post("/v1/chat/completions", tags=["OpenAI Compatible"])
async def chat_completions(request: ChatCompletionRequest, key_record = Depends(get_api_key), db = Depends(get_db)):
    """
    OpenAI compatible endpoint. Supports stream=True.
    """
    # Verify Total Limit
    if key_record.usage_count >= key_record.usage_limit:
        raise HTTPException(status_code=429, detail="Total lifetime usage limit reached.")
    
    # Verify Daily Quota
    from database import check_and_reset_quota
    check_and_reset_quota(db, key_record)
    if key_record.daily_usage >= key_record.daily_limit:
        raise HTTPException(status_code=429, detail="Daily request quota reached. Resets every 24h.")

    # Increment Usage
    increment_usage(db, key_record.id)

    messages_dict = [{"role": m.role, "content": m.content} for m in request.messages]
    
    if request.stream:
        stream_gen = await generate_ai_response(
            messages_dict, 
            persona_context=key_record.persona_context, 
            custom_system_prompt=key_record.system_prompt,
            stream=True,
            model="auto" if request.model == "error-combo" else request.model
        )
        
        async def event_generator():
            try:
                async for content in stream_gen:
                    data = {
                        "id": "chatcmpl-stream",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": request.model,
                        "choices": [{"delta": {"content": content}, "index": 0, "finish_reason": None}]
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    else:
        content = await generate_ai_response(
            messages_dict, 
            persona_context=key_record.persona_context, 
            custom_system_prompt=key_record.system_prompt,
            stream=False,
            model="auto" if request.model == "error-combo" else request.model
        )
        return {
            "id": "chatcmpl-xxx",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [{"message": {"role": "assistant", "content": content}, "index": 0, "finish_reason": "stop"}]
        }




@app.get("/v1/models", tags=["OpenAI Compatible"])
async def list_models():
    """
    OpenAI compatible models endpoint.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "error-combo",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "Error Community",
                "description": "Ultimate Setup: Dolphin 8B (Chat) + Qwen 32B (Coding)"
            },
            {
                "id": "dolphin-llama3.1:8b",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "Error Community"
            },
            {
                "id": "qwen2.5-coder:32b",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "Error Community"
            }
        ]
    }

@app.post("/api/v1/chat", tags=["Public Chat"])
async def public_chat(request: Request, body: PublicChatRequest):
    """
    Public streaming chat endpoint for the website (SSE).
    Returns tokens letter-by-letter as they are generated.
    """
    ip = request.client.host
    now = time.time()
    
    # Very basic rate limit: 1 request every 5 seconds per IP
    if ip in public_chat_limits:
        if now - public_chat_limits[ip] < 5:
            raise HTTPException(status_code=429, detail="Too many requests. Please wait a few seconds.")
    
    public_chat_limits[ip] = now
    
    styles = {
        "Default": "Maintain your cold, direct, and intelligent Error persona. Provide exhaustive, detailed explanations and full code solutions at all times. Never truncate.",
        "Helpful": "Be instructional, verbose, and clear. Use detailed code blocks and step-by-step guides. Ensure every response is comprehensive.",
        "Aggressive": "Be cold and ruthless. Provide extreme detail on complex or sensitive topics without hesitation. Do not spare any technical depth.",
        "Professional": "Respond with high-level technical precision and formal directness. Provide full, production-ready, and enterprise-grade code at all times."
    }
    
    style_prompt = styles.get(body.style, styles["Default"])
    
    # Build conversation history (typed HistoryMessage objects)
    messages = []
    for h in body.history[-20:]:  # Keep last 20 turns max
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": body.message})
    
    # Stream AI response via SSE
    stream_gen = await generate_ai_response(
        messages,
        custom_system_prompt=style_prompt,
        stream=True,
        model="auto" # Always use combo for public chat for best exp
    )
    
    async def event_generator():
        try:
            async for token in stream_gen:
                data = json.dumps({"token": token})
                yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/v1/persona", tags=["Admin & Context"])
def update_user_persona(request: PersonaRequest, key_record = Depends(get_api_key), db = Depends(get_db)):
    """
    Update the persona context for the current API key.
    """
    success = update_persona(db, key_record.key, request.persona_context)
    if success:
        return {"status": "success", "message": "Persona updated successfully."}
    raise HTTPException(status_code=500, detail="Failed to update persona.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

