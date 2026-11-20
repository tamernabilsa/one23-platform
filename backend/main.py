from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client, Client
from bs4 import BeautifulSoup
import httpx
import os
import json
import base64
import hashlib
import re
import random

app = FastAPI(title="One23 Full AI SaaS Platform", version="7.0")

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

# --- نماذج البيانات (Models) ---
class CampaignRequest(BaseModel):
    company_url: str
    email: str | None = None

class MediaRequest(BaseModel):
    script_text: str
    company_url: str

class ClientRegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    brand_name: str
    brand_color: str = "#FF9900"

class ClientLoginRequest(BaseModel):
    email: str
    password: str

class BrandPlanRequest(BaseModel):
    client_email: str
    brand_name: str
    business_type: str
    target_country: str = "المملكة العربية السعودية"

class ContentStudioRequest(BaseModel):
    client_email: str
    brand_name: str
    brand_color: str
    topic: str
    generate_image: bool = True

class LandingPageCreateRequest(BaseModel):
    client_email: str
    brand_name: str
    headline: str
    subheadline: str
    offer_details: str
    whatsapp_number: str
    accent_color: str = "#FF9900"

class PageLeadSubmitRequest(BaseModel):
    page_slug: str
    customer_name: str
    customer_phone: str
    notes: str | None = ""

# --- دوال مساعدة ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

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
            <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; background: #141920; color: #f8fafc; padding: 24px; border-radius: 12px;">
                <h2 style="color: #FF9900;">مرحباً بكم من منصة One23.sa</h2>
                <p>شكراً لتجربة محرك الذكاء الاصطناعي لتحليل موقعكم: <strong dir="ltr">{company_url}</strong></p>
                <div style="background: #1e2530; padding: 16px; border-radius: 8px; margin: 16px 0;">
                    <p><strong style="color: #FF9900;">🎯 الجمهور المستهدف:</strong><br>{audience}</p>
                    <p><strong style="color: #FF9900;">💡 الرسالة التسويقية:</strong><br>{message}</p>
                    <p><strong style="color: #FF9900;">🎬 سيناريو الفيديو التفاعلي المقترح:</strong><br>{script_html}</p>
                </div>
                <a href="https://one23.sa/portal.html" style="display: inline-block; background: #FF9900; color: #141920; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">ادخل بوابة العملاء لإدارة حملاتك الآن</a>
            </div>
            """
            res = await http_client.post("https://api.resend.com/emails", headers=headers, json={
                "from": SENDER_EMAIL,
                "to": [client_email],
                "subject": f"سيناريو الفيديو والخطة التسويقية المقترحة ({company_url}) - One23.sa",
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
                "subject": f"🔔 عميل جديد على One23.sa: {company_url}",
                "html": f"<div dir='rtl'><h3>تم تسجيل عميل جديد:</h3><p><strong>الموقع:</strong> {company_url}</p><p><strong>البريد:</strong> {client_email or 'غير مدخل'}</p><p><strong>السيناريو:</strong><br>{script_html}</p></div>"
            })

    return status_msg

@app.get("/")
def read_root():
    return {"status": "One23 Full AI SaaS Platform + Client Portal is Active"}

# --- 1. مسارات الواجهة الرئيسية (تحليل الموقع + توليد الصوت والمشهد) ---
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

@app.post("/api/generate-media")
async def generate_media_preview(data: MediaRequest):
    clean_text = data.script_text.strip()[:1000]
    if not clean_text:
        raise HTTPException(status_code=400, detail="نص السيناريو فارغ.")

    try:
        speech_response = client.audio.speech.create(
            model="tts-1",
            voice="onyx",
            input=clean_text
        )
        audio_base64 = base64.b64encode(speech_response.content).decode("utf-8")

        image_prompt = (
            f"Detailed hand-drawn whiteboard explainer illustration filling the entire frame, "
            f"bold black marker strokes with vibrant blue and orange highlights on a clean light-gray background, "
            f"showing a dynamic business growth scene, charts, and happy customers for {data.company_url}, "
            f"clear central composition, high contrast, no text."
        )
        image_response = client.images.generate(
            model="gpt-image-1.5",
            prompt=image_prompt,
            size="1024x1024",
            n=1
        )
        img_data = image_response.data[0]
        storyboard_url = f"data:image/png;base64,{img_data.b64json}" if getattr(img_data, "b64json", None) else img_data.url

        return {
            "success": True,
            "audio_base64": audio_base64,
            "storyboard_url": storyboard_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"تعذر توليد المعاينة الصوتية والبصرية: {str(e)}")

# --- 2. مسارات بوابة العملاء (تسجيل، دخول، لوحة التحكم) ---
@app.post("/api/portal/register")
def register_client(data: ClientRegisterRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير متصلة.")
    email_clean = data.email.strip().lower()
    if not email_clean or not data.password or not data.full_name:
        raise HTTPException(status_code=400, detail="الرجاء إكمال جميع الحقول المطلوبة.")

    existing = supabase.table("clients").select("id").eq("email", email_clean).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="هذا البريد الإلكتروني مسجل مسبقاً، يرجى تسجيل الدخول.")

    new_client = {
        "full_name": data.full_name.strip(),
        "email": email_clean,
        "password_hash": hash_password(data.password),
        "brand_name": data.brand_name.strip() or data.full_name.strip(),
        "brand_color": data.brand_color or "#FF9900",
        "plan_tier": "الباقة التجريبية (Starter Trial)"
    }
    res = supabase.table("clients").insert(new_client).execute()
    user_record = res.data[0]
    user_record.pop("password_hash", None)
    return {"success": True, "client": user_record}

@app.post("/api/portal/login")
def login_client(data: ClientLoginRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير متصلة.")
    email_clean = data.email.strip().lower()
    res = supabase.table("clients").select("*").eq("email", email_clean).execute()
    if not res.data:
        raise HTTPException(status_code=401, detail="البريد الإلكتروني غير مسجل.")
    
    user_record = res.data[0]
    if user_record["password_hash"] != hash_password(data.password):
        raise HTTPException(status_code=401, detail="كلمة المرور غير صحيحة.")

    user_record.pop("password_hash", None)
    return {"success": True, "client": user_record}

@app.get("/api/portal/dashboard")
def get_client_dashboard(email: str):
    if not supabase:
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير متصلة.")
    email_clean = email.strip().lower()
    assets = supabase.table("client_assets").select("*").eq("client_email", email_clean).order("created_at", desc=True).execute()
    pages = supabase.table("landing_pages").select("*").eq("client_email", email_clean).order("created_at", desc=True).execute()
    page_leads = supabase.table("page_leads").select("*").eq("owner_email", email_clean).order("created_at", desc=True).execute()
    return {
        "success": True,
        "assets": assets.data or [],
        "landing_pages": pages.data or [],
        "page_leads": page_leads.data or []
    }

# --- 3. أداة خطة العلامة التجارية (Brand Plan) ---
@app.post("/api/portal/brand-plan")
def generate_brand_plan(data: BrandPlanRequest):
    prompt = f"""
    أنت مستشار تسويق واستراتيجي علامات تجارية في السعودية لمنصة One23.sa.
    أنشئ خطة عروض ومحتوى شهرية (4 أسابيع متكاملة) لمشروع:
    - اسم العلامة: {data.brand_name}
    - مجال العمل: {data.business_type}
    - السوق المستهدف: {data.target_country} (مراعاة مواسم الرواتب يوم 27 ميلادي، نهاية الأسبوع، والمواسم السعودية).

    أعد الإجابة بصيغة JSON فقط بالشكل التالي:
    {{
        "plan_title": "عنوان الخطة الشهرية",
        "weeks": [
            {{
                "week": "الأسبوع الأول (فترة نزول الرواتب)",
                "offer_idea": "فكرة العرض الترويجي المقترح",
                "content_angle": "فكرة المنشور أو الفيديو القصير",
                "marketing_reason": "السبب التسويقي لنجاح هذا العرض في هذا التوقيت"
            }}
        ]
    }}
    (تأكد من تضمين 4 أسابيع كاملة في مصفوفة weeks).
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "أنت خبير تخطيط تسويقي للسوق السعودي ترد بصيغة JSON دقيق."},
                {"role": "user", "content": prompt}
            ]
        )
        plan_json = json.loads(completion.choices[0].message.content)
        if supabase:
            supabase.table("client_assets").insert({
                "client_email": data.client_email.lower(),
                "asset_type": "brand_plan",
                "title": plan_json.get("plan_title", f"خطة تسويقية - {data.brand_name}"),
                "content_data": json.dumps(plan_json, ensure_ascii=False),
                "status": "مكتمل"
            }).execute()
        return {"success": True, "plan": plan_json}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في توليد الخطة: {str(e)}")

# --- 4. أداة استوديو المحتوى (Content Studio) ---
@app.post("/api/portal/content-studio")
def generate_content_studio(data: ContentStudioRequest):
    prompt = f"""
    أنت مدير إبداعي في منصة One23.sa. اكتب محتوى تسويقياً احترافياً باللهجة السعودية البيضاء الجذابة لعلامة:
    - اسم المشروع: {data.brand_name}
    - الموضوع أو العرض: {data.topic}

    أعد النتيجة بصيغة JSON فقط:
    {{
        "post_caption": "نص المنشور التسويقي لمنصات التواصل الاجتماعي مع هاشتاقات مناسبة",
        "ugc_script": "سيناريو فيديو قصير (Reels/TikTok) مدته 20 ثانية مع تعليق صوتي مقنع",
        "image_concept": "وصف إنجليزي دقيق لتصميم إعلاني احترافي يعبر عن العرض بأسلوب نظيف وعصري بدون أي نصوص مكتوبة داخل الصورة"
    }}
    """
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "أنت صانع محتوى تسويقي محترف ترد بصيغة JSON صالح."},
                {"role": "user", "content": prompt}
            ]
        )
        content_json = json.loads(completion.choices[0].message.content)
        image_url = ""

        if data.generate_image:
            img_prompt = f"{content_json.get('image_concept', 'Modern commercial product showcase')}, accent color {data.brand_color}, studio lighting, high resolution commercial photography, no text, no letters."
            img_res = client.images.generate(
                model="gpt-image-1.5",
                prompt=img_prompt,
                size="1024x1024",
                n=1
            )
            img_obj = img_res.data[0]
            image_url = f"data:image/png;base64,{img_obj.b64json}" if getattr(img_obj, "b64json", None) else img_obj.url

        if supabase:
            supabase.table("client_assets").insert({
                "client_email": data.client_email.lower(),
                "asset_type": "content_post",
                "title": f"محتوى: {data.topic[:40]}",
                "content_data": json.dumps(content_json, ensure_ascii=False),
                "media_url": image_url if not image_url.startswith("data:") else "",
                "status": "جاهز للنشر"
            }).execute()

        return {"success": True, "content": content_json, "image_url": image_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في استوديو المحتوى: {str(e)}")

# --- 5. منشئ صفحات الهبوط المصغرة (Landing Page Builder) ---
@app.post("/api/portal/landing-page")
def create_landing_page(data: LandingPageCreateRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير متصلة.")
    base_slug = re.sub(r'[^a-zA-Z0-9]', '-', data.brand_name.lower()).strip('-') or "offer"
    slug = f"{base_slug}-{random.randint(1000, 9999)}"

    record = {
        "client_email": data.client_email.lower(),
        "slug": slug,
        "headline": data.headline.strip(),
        "subheadline": data.subheadline.strip(),
        "offer_details": data.offer_details.strip(),
        "whatsapp_number": data.whatsapp_number.strip(),
        "accent_color": data.accent_color or "#FF9900"
    }
    res = supabase.table("landing_pages").insert(record).execute()
    return {"success": True, "page": res.data[0]}

@app.get("/api/public/landing/{slug}")
def get_public_landing_page(slug: str):
    if not supabase:
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير متصلة.")
    res = supabase.table("landing_pages").select("*").eq("slug", slug).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="صفحة العرض غير موجودة.")
    page = res.data[0]
    page.pop("client_email", None)
    return {"success": True, "page": page}

@app.post("/api/public/landing/lead")
def submit_landing_page_lead(data: PageLeadSubmitRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير متصلة.")
    page_res = supabase.table("landing_pages").select("client_email").eq("slug", data.page_slug).execute()
    if not page_res.data:
        raise HTTPException(status_code=404, detail="الصفحة غير موجودة.")
    owner_email = page_res.data[0]["client_email"]

    supabase.table("page_leads").insert({
        "owner_email": owner_email,
        "page_slug": data.page_slug,
        "customer_name": data.customer_name.strip(),
        "customer_phone": data.customer_phone.strip(),
        "notes": data.notes or ""
    }).execute()
    return {"success": True}

# --- 6. لوحة الإدارة (Admin Dashboard) ---
@app.get("/api/admin/leads")
def get_all_leads(x_admin_password: str = Header(None)):
    expected_password = os.environ.get("ADMIN_PASSWORD", "one23admin2026")
    if x_admin_password != expected_password:
        raise HTTPException(status_code=401, detail="كلمة مرور الإدارة غير صحيحة.")
    if not supabase:
        raise HTTPException(status_code=500, detail="قاعدة البيانات غير متصلة.")
    try:
        response