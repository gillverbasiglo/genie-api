from fastapi import Depends, FastAPI
from openai import OpenAI
from google import genai

from app.config import Settings

app = FastAPI()

from pydantic import BaseModel

class TextRequest(BaseModel):
    text: str

@app.post("/process-text")
async def process_text(request: TextRequest):
    settings = Settings()
    client = OpenAI(api_key=settings.open_ai_api_key)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": request.text}
        ]
    )
    
    return {"result": response.choices[0].message.content}

