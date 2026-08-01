# AGENTS.md — imaginAI (MVP v1)

قواعد ثابتة لهذا المشروع. اقرأها قبل أي مهمة، ولا تكررها في كل برومبت.

## نظرة عامة
imaginAI: أداة تحوّل فكرة نصية إلى فيديو طويل جاهز تلقائياً (Script → Voice → Footage → Captions → Render).
هذا هو الإصدار الأول (MVP): مسار **Auto فقط**، موديل واحد يُعرض في الواجهة باسم **"imaginAI Mini"**. لا يوجد محرر تايم لاين، لا حسابات مستخدمين، لا دفع.

## Stack
- Backend: Python 3.11 + FastAPI
- معالجة الفيديو: FFmpeg (استدعاء مباشر عبر subprocess، وليس MoviePy)
- Frontend: Next.js (React) + Tailwind — سهل النشر المجاني على Vercel لاحقاً
- لا قاعدة بيانات في v1: كل job = مجلد مؤقت محلي فيه ملفاته (script.json, audio/, clips/, output.mp4)
- تخزين الحالة: ملف status.json داخل مجلد الـ job، الواجهة تعمل عليه polling كل 3 ثواني

## مزودو الخدمة (Free Tier) — الأسماء فقط، القيم في .env
| الخدمة | الاستخدام | متغير البيئة |
|---|---|---|
| Gemini API | توليد السكريبت (JSON) | `GEMINI_API_KEY` |
| Gemini API | تحويل نص→صوت (TTS) | نفس المفتاح |
| Pexels API | جلب لقطات فيديو (مصدر أساسي) | `PEXELS_API_KEY` |
| Pixabay API | جلب لقطات فيديو (مصدر احتياطي إن لم يوجد في Pexels) | `PIXABAY_API_KEY` |
| Groq API | Whisper للترجمة/الكابشن (سريع ومجاني) | `GROQ_API_KEY` |

### الموديلات المحددة (لا تغيّرها بدون سبب)
- توليد السكريبت + JSON منظّم: `gemini-3.6-flash` مع `responseMimeType: "application/json"`
- توليد الصوت (TTS): `gemini-3.1-flash-tts-preview` — صوت افتراضي واحد لهذه النسخة (اقترح "Kore")، لا تعرض مكتبة أصوات كاملة في v1
- الترجمة/الكابشن: Groq Whisper (`whisper-large-v3-turbo` أو الأحدث المتاح على Groq)

### حدود مهمة يجب احترامها بالكود (rate limiting + caching)
- Gemini المجاني: ~15 طلب/دقيقة، 1500 طلب/يوم → أضف retry مع backoff، ولا ترسل أكثر من طلب واحد متزامن لكل job
- Pixabay: 100 طلب/60 ثانية، ويجب **كاش النتائج 24 ساعة** (متطلب من سياستهم)، ولا Hotlinking دائم — يجب تحميل الفيديو للسيرفر المحلي قبل استخدامه في FFmpeg، ممنوع الاستخدام المباشر لرابط CDN كمصدر دائم
- يجب عرض إسناد المصدر (attribution) لـ Pixabay في أي مكان تُعرض فيه النتائج (متطلب من ترخيصهم)

## بنية المجلدات المتوقعة
```
/backend
  /app
    main.py
    /services  (gemini_script.py, gemini_tts.py, footage.py, captions.py, render.py)
    /jobs      (ملفات مؤقتة لكل job)
  .env.example
/frontend
  /app (Next.js app router)
```

## قواعد الكود
- كل استدعاء API خارجي يجب أن يكون بدالة منفصلة في `/services` مع معالجة أخطاء try/except واضحة
- لا تكتب أي مفتاح API كنص مباشر في الكود — فقط `os.getenv(...)`
- استخدم `.env.example` بدون قيم حقيقية كمرجع فقط
- كل مرحلة من الـ pipeline (سكريبت → صوت → لقطات → كابشن → رندر) يجب أن تكون قابلة للاختبار منفردة عبر endpoint أو سكريبت CLI منفصل قبل ربطها بالكل

## سير العمل المفضّل معي (الوكيل)
1. عند أي مهمة جديدة: اقترح خطة تنفيذ فقط أولاً (Planning)، لا تكتب كوداً قبل مراجعتي للخطة
2. نفّذ على دفعات صغيرة (مرحلة واحدة من الـ pipeline في كل مرة)، واختبرها قبل الانتقال للتالية
3. لا تلمس ملفات خارج مجلد المشروع نهائياً
