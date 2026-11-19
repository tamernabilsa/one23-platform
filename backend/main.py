from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client, Client
from bs4 import BeautifulSoup
import httpx
import os
import json

app = FastAPI(title="One23 AI Engine + Supabase + Admin + Outreach", version="5.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client | None = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "One23.sa <onboarding@resend.dev>")
ADMIN_NOTIFY_EMAIL = os.environ.get("ADMIN_NOTIFY_EMAIL", "")

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
        return f"رابط الشركة: {url}"

async def send_outreach_emails(client_email: str, company_url: str, audience: str, message: str, script_html: str) -> str:
    if not RESEND_API_KEY:
        return "مفتاح RESEND_API_KEY غير مضاف في Render"

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    status_msg = "لم يتم الإرسال"

    async with httpx.AsyncClient(timeout=15.0) as http_client:
        if client_email:
            client_html = f"""
            <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; background: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px;">
                <h2 style="color: #3b82f6;">مرحباً بكم من منصة one23.sa</h2>
                <p>شكراً لتجربة محرك الذكاء الاصطناعي لتحليل موقعكم: <strong dir="ltr">{company_url}</strong></p>
                <div style="background: #1e293b; padding: 16px; border-radius: 8px; margin: 16px 0;">
                    <p><strong style="color: #60a5fa;">🎯 الجمهور المستهدف:</strong><br>{audience}</p>
                    <p><strong style="color: #60a5fa;">💡 الرسالة التسويقية:</strong><br>{message}</p>
                    <p><strong style="color: #60a5fa;">🎬 سيناريو الفيديو التفاعلي المقترح:</strong><br>{script_html}</p>
                </div>
                <a href="https://one23.sa/#pricing" style="display: inline-block; background: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">استعرض الباقات واطلب الفيديو الآن</a>
            </div>
            """
            res = await http_client.post("https://api.resend.com/emails", headers=headers, json={
                "from": SENDER_EMAIL,
                "to": [client_email],
                "subject": f"سيناريو الفيديو التفاعلي المقترح لشركتكم ({company_url}) - one23.sa",
                "html": client_html
            })
            if res.status_code in (200, 201):
                status_msg = "تم إرسال الإيميل بنجاح"
            else:
                status_msg = f"فشل إرسال Resend: {res.text}"

        if ADMIN_NOTIFY_EMAIL:
            await http_client.post("https://api.resend.com/emails", headers=headers, json={
                "from": SENDER_EMAIL,
                "to": [ADMIN_NOTIFY_EMAIL],
                "subject": f"🔔 عميل جديد على one23.sa: {company_url}",
                "html": f"<div dir='rtl'><h3>تم تسجيل عميل جديد:</h3><p><strong>الموقع:</strong> {company_url}</p><p><strong>البريد:</strong> {client_email or 'غير مدخل'}</p><p><strong>السيناريو:</strong><br>{script_html}</p></div>"
            })

    return status_msg

@app.get("/")
def read_root():
    return {"status": "One23 AI Engine with Outreach is Active"}

@app.post("/api/generate-campaign")
async def generate_campaign(data: CampaignRequest):
    url = data.company_url.strip()
    email = data.email.strip() if data.email else ""

    if not url:
        raise HTTPException(status_code=400, detail="الرجاء إدخال رابط صحيح للشركة.")

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
                {"role": "system", "content": "أنت مساعد ذكي متخصص في تحليل الشركات وصياغة حملات الفيديو التفاعلي بصيغة JSON صالح."},
                {"role": "user", "content": prompt}
            ]
        )

        raw_content = completion.choices[0].message.content
        if not raw_content:
            raise ValueError("لم يرجع الذكاء الاصطناعي أي محتوى.")

        ai_result = json.loads(raw_content)

        target_audience = ai_result.get("target_audience", "")
        marketing_message = ai_result.get("marketing_message", "")
        raw_script = ai_result.get("video_script", "")
        video_script_str = json.dumps(raw_script, ensure_ascii=False) if isinstance(raw_script, (list, dict)) else str(raw_script)
        lead_status = ai_result.get("lead_status", "مؤهل عالي (Hot Lead)")

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

        script_html = video_script_str.replace("\\n", "<br>").replace("\n", "<br>")
        email_status = await send_outreach_emails(email, url, target_audience, marketing_message, script_html)

        return {
            "success": True,
            "company_url": url,
            "target_audience": target_audience,
            "marketing_message": marketing_message,
            "video_script": raw_script,
            "lead_status": lead_status,
            "email_status": email_status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء التحليل: {str(e)}")

@app.get("/api/admin/leads")
def get_all_leads(x_admin_password: str = Header(None)):
    expected_password = os.environ.get("ADMIN_PASSWORD", "one23admin2026")
    if x_admin_password != expected_password:
        raise HTTPException(status_code=401, detail="كلمة مرور الإدارة غير صحيحة.")
    if not supabase:
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير متصلة.")
    try:
        response = supabase.table("leads").select("*").order("created_at", desc=True).execute()
        return {"success": True, "leads": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في جلب البيانات: {str(e)}")