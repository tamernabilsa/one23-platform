from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client, Client
from bs4 import BeautifulSoup
import httpx
import os
import json

app = FastAPI(title="One23 AI Engine + Supabase", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# تهيئة OpenAI و Supabase من متغيرات البيئة في Render
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client | None = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

class CampaignRequest(BaseModel):
    company_url: str
    email: str | None = None

async def fetch_website_text(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http_client:
            response = await http_client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            paragraphs = " ".join([p.get_text(strip=True) for p in soup.find_all(["h1", "h2", "p"])[:15]])
            return f"عنوان الموقع: {title}\nالمحتوى: {paragraphs}"[:2500]
    except Exception:
        return f"رابط الشركة: {url} (لم نتمكن من سحب النص التفصيلي، قم بالتحليل بناءً على اسم النطاق)."

@app.get("/")
def read_root():
    return {"status": "One23 AI Engine with Supabase is Active"}

@app.post("/api/generate-campaign")
async def generate_campaign(data: CampaignRequest):
    url = data.company_url.strip()
    email = data.email.strip() if data.email else ""

    if not url:
        raise HTTPException(status_code=400, detail="الرجاء إدخال رابط صحيح للشركة.")

    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="مفتاح OpenAI API غير مضاف في إعدادات السيرفر.")

    site_content = await fetch_website_text(url)

    prompt = f"""
    أنت خبير تسويق ومحتوى مرئي في منصة one23.sa المتخصصة في صناعة فيديوهات الشرح التفاعلية (Whiteboard Animation).
    حلل بيانات الشركة التالية المستخرجة من موقعها:
    {site_content}

    أعد الإجابة بصيغة JSON فقط تحتوي على المفاتيح التالية بدقة وباللغة العربية الاحترافية:
    {{
        "target_audience": "تحديد دقيق للجمهور المستهدف لهذه الشركة",
        "marketing_message": "رسالة تسويقية مقنعة ومخصصة تقترح عليهم استخدام فيديو تفاعلي لمضاعفة مبيعاتهم",
        "video_script": "فكرة سيناريو فيديو سبورة بيضاء من 3 مشاهد قصيرة مخصصة لنشاط هذه الشركة",
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

        target_audience = ai_result.get("target_audience", "")
        marketing_message = ai_result.get("marketing_message", "")
        raw_script = ai_result.get("video_script", "")
        video_script_str = json.dumps(raw_script, ensure_ascii=False) if isinstance(raw_script, (list, dict)) else str(raw_script)
        lead_status = ai_result.get("lead_status", "مؤهل عالي (Hot Lead)")

        # حفظ بيانات العميل والتحليل في Supabase تلقائياً
        if supabase:
            try:
                supabase.table("leads").insert({
                    "company_url": url,
                    "email": email,
                    "target_audience": target_audience,
                    "marketing_message": marketing_message,
                    "video_script": video_script_str,
                    "lead_status": lead_status
                }).execute()
            except Exception as db_err:
                print(f"Supabase insert warning: {db_err}")

        return {
            "success": True,
            "company_url": url,
            "target_audience": target_audience,
            "marketing_message": marketing_message,
            "video_script": raw_script,
            "lead_status": lead_status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء التحليل: {str(e)}")