from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI(title="One23 Explee MVP API", version="1.0")

# السماح للواجهة الأمامية بالاتصال بالباك إند
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CampaignRequest(BaseModel):
    company_url: str

@app.get("/")
def read_root():
    return {"status": "One23 Core Engine is running successfully"}

@app.post("/api/generate-campaign")
def generate_campaign(data: CampaignRequest):
    url = data.company_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="الرجاء إدخال رابط صحيح للشركة.")
    
    # محاكاة تحليل الذكاء الاصطناعي وصياغة الحملة (يمكن ربطه بـ OpenAI API مباشرة لاحقاً)
    target_audience = "أصحاب الشركات والمؤسسات المهتمة بتحسين الكفاءة التشغيلية في الرياض."
    marketing_message = f"مرحباً بك! لاحظنا أن موقعك ({url}) يقدم خدمات ممتازة، ويمكننا مضاعفة عملائك المحتملين عبر أتمتة وعرض خدماتك بفيديوهات تفاعلية ذكية."
    hot_lead_status = "مؤهل عالي (Hot Lead)"

    return {
        "success": True,
        "company_url": url,
        "target_audience": target_audience,
        "marketing_message": marketing_message,
        "lead_status": hot_lead_status
    }