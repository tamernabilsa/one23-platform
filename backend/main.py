from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from bs4 import BeautifulSoup
import httpx
import os
import json

app = FastAPI(title="One23 Explee AI Engine", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# سيقوم الكود بقراءة مفتاح OpenAI تلقائياً من إعدادات Render
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

class CampaignRequest(BaseModel):
    company_url: str

async def fetch_website_text(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http_client:
            response = await http_client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(response.text, "html.parser")
            # استخراج العنوان والوصف وأهم النصوص
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            paragraphs = " ".join([p.get_text(strip=True) for p in soup.find_all(["h1", "h2", "p"])[:15]])
            extracted = f"عنوان الموقع: {title}\nالمحتوى: {paragraphs}"
            return extracted[:2500] # الاكتفاء بأول 2500 حرف لسرعة المعالجة
    except Exception:
        return f"رابط الشركة: {url} (لم نتمكن من سحب النص التفصيلي، قم بالتحليل بناءً على اسم النطاق)."

@app.get("/")
def read_root():
    return {"status": "One23 Real AI Engine is Active"}

@app.post("/api/generate-campaign")
async def generate_campaign(data: CampaignRequest):
    url = data.company_url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="الرجاء إدخال رابط صحيح للشركة.")

    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="مفتاح OpenAI API غير مضاف في إعدادات السيرفر.")

    # 1. قراءة محتوى الموقع الفعلي
    site_content = await fetch_website_text(url)

    # 2. إرسال البيانات إلى GPT-4o للتحليل وصياغة الحملة وسيناريو الفيديو
    prompt = f"""
    أنت خبير تسويق ومحتوى مرئي في منصة one23 (المتخصصة في صناعة فيديوهات الشرح التفاعلية والرسوم المتحركة على غرار Explee لجذب العملاء).
    قم بتحليل بيانات الشركة التالية المستخرجة من موقعها:
    {site_content}

    أعد الإجابة بصيغة JSON فقط تحتوي على المفاتيح التالية بدقة وباللغة العربية الاحترافية:
    {{
        "target_audience": "تحديد دقيق للجمهور المستهدف لهذه الشركة",
        "marketing_message": "رسالة تسويقية مقنعة ومخصصة تقترح عليهم استخدام فيديو تفاعلي لمضاعفة مبيعاتهم",
        "video_script": "فكرة سيناريو فيديو سبورة بيضاء (Whiteboard Animation) من 3 مشاهد قصيرة مخصصة لنشاط هذه الشركة",
        "lead_status": "تقييم فرصة العميل (مثلاً: مؤهل عالي - Hot Lead مع ذكر السبب باختصار)"
    }}
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "أنت مساعد ذكي متخصص في تحليل الشركات وصياغة حملات الفيديو التفاعلي بصيغة JSON."},
                {"role": "user", "content": prompt}
            ]
        )
        ai_result = json.loads(completion.choices[0].message.content)

        return {
            "success": True,
            "company_url": url,
            "target_audience": ai_result.get("target_audience", ""),
            "marketing_message": ai_result.get("marketing_message", ""),
            "video_script": ai_result.get("video_script", ""),
            "lead_status": ai_result.get("lead_status", "مؤهل عالي (Hot Lead)")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء التحليل: {str(e)}")