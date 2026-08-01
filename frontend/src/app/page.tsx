"use client";

import React, { useState, useEffect, useRef } from "react";
import { 
  Sparkles, 
  Play, 
  Pause,
  Download, 
  Plus, 
  Loader2, 
  CheckCircle2, 
  AlertCircle, 
  ArrowRight,
  Info,
  Volume2,
  Tv,
  Flame,
  FileText,
  Compass,
  Radio,
  Zap,
  Globe,
  MessageSquare
} from "lucide-react";
import { 
  createJob, 
  getJobStatus, 
  getDownloadUrl, 
  getVoicesCatalog, 
  getVoicePreviewUrl, 
  sendFeedback,
  JobStatusResponse, 
  VoiceProviderCatalog, 
  VoiceItem 
} from "../lib/api";

type ScreenState = "input" | "voice" | "progress" | "result";
type StyleType = "documentary" | "mystery" | "listicle" | "motivational";

// Fallback Voice Providers catalog
const DEFAULT_PROVIDERS: VoiceProviderCatalog[] = [
  {
    provider: "edge-tts",
    provider_name: "Edge-TTS (مجاني وعالي الجودة)",
    desc: "أصوات سريعة ومجانية 100% بدون قيود أو حدود API",
    voices: [
      { id: "ar-SA-HamedNeural", name: "حامد (Hamed)", gender: "male", lang: "العربية", desc: "صوت ذكوري فصيح هادئ ومناسب للسرد والوثائقيات" },
      { id: "ar-EG-SalmaNeural", name: "سلمى (Salma)", gender: "female", lang: "العربية", desc: "صوت أنثوي فصيح وطبيعي للقصص" },
      { id: "ar-SA-ZariyahNeural", name: "زارية (Zariyah)", gender: "female", lang: "العربية", desc: "صوت أنثوي رزين واحترافي" },
      { id: "ar-AE-HamdanNeural", name: "حمدان (Hamdan)", gender: "male", lang: "العربية", desc: "صوت ذكوري حماسي للقصص التحفيزية" },
      { id: "en-US-ChristopherNeural", name: "كريستوفر (Christopher)", gender: "male", lang: "English", desc: "Deep narrative voice" },
      { id: "en-US-JennyNeural", name: "جيني (Jenny)", gender: "female", lang: "English", desc: "Clear professional voice" },
    ],
  },
  {
    provider: "gemini",
    provider_name: "Google AI Studio (Gemini TTS)",
    desc: "أصوات ذكاء اصطناعي سينمائية فائقة من Google",
    voices: [
      { id: "Kore", name: "كوري (Kore)", gender: "female", lang: "متعدد اللغات", desc: "صوت أنثوي طبيعي وحيوي" },
      { id: "Puck", name: "بوك (Puck)", gender: "male", lang: "متعدد اللغات", desc: "صوت ذكوري رزين وهادئ" },
      { id: "Charon", name: "كارون (Charon)", gender: "male", lang: "متعدد اللغات", desc: "صوت ذكوري عميق ودافئ" },
      { id: "Aoede", name: "أويدي (Aoede)", gender: "female", lang: "متعدد اللغات", desc: "صوت أنثوي سينمائي ومميز" },
      { id: "Fenrir", name: "فينرير (Fenrir)", gender: "male", lang: "متعدد اللغات", desc: "صوت ذكوري قوي ومباشر" },
    ],
  },
  {
    provider: "gtts",
    provider_name: "gTTS (مكتبة بايثون مجانية)",
    desc: "صوت تحويل النص إلى كلام القياسي والمستقر",
    voices: [
      { id: "ar", name: "Google Arabic Standard", gender: "female", lang: "العربية", desc: "الصوت العربي القياسي المباشر من Google" },
      { id: "en", name: "Google English Standard", gender: "female", lang: "English", desc: "Standard clear English narration voice" },
    ],
  },
];

const STYLES: { id: StyleType; label: string; icon: React.ReactNode; desc: string }[] = [
  { id: "documentary", label: "وثائقي", icon: <Tv className="w-3.5 h-3.5" />, desc: "تلاشي سينمائي وتدفق هادئ" },
  { id: "mystery", label: "غموض / جريمة", icon: <Compass className="w-3.5 h-3.5" />, desc: "قطع سريع وإيقاع متوتر" },
  { id: "listicle", label: "قائمة / توب 10", icon: <FileText className="w-3.5 h-3.5" />, desc: "أرقام متحركة وشاشة تشويقية" },
  { id: "motivational", label: "تحفيزي", icon: <Flame className="w-3.5 h-3.5" />, desc: "طاقة متصاعدة وكلمات بارزة" },
];

export default function Home() {
  // ── States ─────────────────────────────────────────────────────────────────
  const [screen, setScreen] = useState<ScreenState>("input");
  const [idea, setIdea] = useState("");
  const [duration, setDuration] = useState<"5_min" | "8_min" | "10_min">("5_min");
  const [style, setStyle] = useState<StyleType>("documentary");
  
  // Web Notification State
  const [notifPermission, setNotifPermission] = useState<string>("default");
  
  // Voice Selection State
  const [providersCatalog, setProvidersCatalog] = useState<VoiceProviderCatalog[]>(DEFAULT_PROVIDERS);
  const [selectedProvider, setSelectedProvider] = useState<"edge-tts" | "gemini" | "gtts">("edge-tts");
  const [selectedVoice, setSelectedVoice] = useState<string>("ar-SA-HamedNeural");
  
  // Audio Player State for voice samples
  const [playingVoice, setPlayingVoice] = useState<string | null>(null);
  const [loadingVoice, setLoadingVoice] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Job Tracking
  const [jobId, setJobId] = useState<string | null>(null);
  const [statusData, setStatusData] = useState<JobStatusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);

  // Feedback Modal State
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState("");
  const [feedbackContact, setFeedbackContact] = useState("");
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSendFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!feedbackMsg.trim()) return;
    setFeedbackSending(true);
    setFeedbackStatus(null);
    try {
      const res = await sendFeedback(feedbackMsg, feedbackContact);
      setFeedbackStatus({ type: "success", text: res.message || "تم إرسال ملاحظتك بنجاح، شكراً لك!" });
      setFeedbackMsg("");
      setFeedbackContact("");
      setTimeout(() => {
        setIsFeedbackOpen(false);
        setFeedbackStatus(null);
      }, 2500);
    } catch (err: any) {
      setFeedbackStatus({ type: "error", text: err.message || "حدث خطأ أثناء إرسال الملاحظات" });
    } finally {
      setFeedbackSending(false);
    }
  };

  // ── Notification Initializer ─────────────────────────────────────────────
  useEffect(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      setNotifPermission(Notification.permission);
    }
  }, []);

  const requestNotificationPermission = async () => {
    if (typeof window !== "undefined" && "Notification" in window) {
      try {
        const perm = await Notification.requestPermission();
        setNotifPermission(perm);
      } catch (e) {
        console.error("Notification permission error:", e);
      }
    }
  };

  // ── Fetch Voice Catalog ───────────────────────────────────────────────────
  useEffect(() => {
    getVoicesCatalog()
      .then((data) => {
        if (data.providers && data.providers.length > 0) {
          setProvidersCatalog(data.providers);
        }
      })
      .catch((err) => console.log("Using default voice catalog:", err));
  }, []);

  // ── Poll function ────────────────────────────────────────────────────────
  const startPolling = (id: string) => {
    if (pollingInterval.current) clearInterval(pollingInterval.current);
    
    pollingInterval.current = setInterval(async () => {
      try {
        const data = await getJobStatus(id);
        setStatusData(data);
        
        if (data.status === "done") {
          setScreen("result");
          if (pollingInterval.current) clearInterval(pollingInterval.current);

          // Browser Notification API trigger (Fix 4)
          if (
            typeof window !== "undefined" &&
            "Notification" in window &&
            Notification.permission === "granted"
          ) {
            try {
              new Notification("فيديوك جاهز 🎬", {
                body: "تم إكمال معالجة ورندر الفيديو بنجاح كـ imaginAI Mini!",
                icon: "/favicon.ico",
              });
            } catch (nErr) {
              console.error("Failed to show notification:", nErr);
            }
          }
        } else if (data.status === "failed") {
          setErrorMsg(data.error || "حدث خطأ غير متوقع أثناء معالجة الفيديو.");
          if (pollingInterval.current) clearInterval(pollingInterval.current);
        }
      } catch (err: any) {
        console.error("Polling error:", err);
      }
    }, 3000);
  };

  useEffect(() => {
    return () => {
      if (pollingInterval.current) clearInterval(pollingInterval.current);
      if (audioRef.current) audioRef.current.pause();
    };
  }, []);

  // ── Handlers ───────────────────────────────────────────────────────────────
  const handleProceedToVoice = (e: React.FormEvent) => {
    e.preventDefault();
    if (!idea.trim()) return;
    setScreen("voice");
  };

  const handleStartGeneration = async () => {
    setErrorMsg(null);
    setStatusData(null);
    setScreen("progress");

    try {
      const res = await createJob({
        idea: idea.trim(),
        duration,
        style,
        voice_provider: selectedProvider,
        voice: selectedVoice,
      });
      setJobId(res.job_id);
      startPolling(res.job_id);
    } catch (err: any) {
      setErrorMsg("فشل الاتصال بالخادم. يرجى التأكد من تشغيل backend.");
      setScreen("input");
    }
  };

  const togglePlaySample = (voice: VoiceItem) => {
    const voiceKey = `${selectedProvider}:${voice.id}`;

    if (playingVoice === voiceKey) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      setPlayingVoice(null);
      setLoadingVoice(null);
    } else {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      
      setLoadingVoice(voiceKey);
      setPlayingVoice(null);

      const previewUrl = getVoicePreviewUrl(selectedProvider, voice.id);
      const audio = new Audio(previewUrl);
      audioRef.current = audio;

      audio.onplay = () => {
        setLoadingVoice(null);
        setPlayingVoice(voiceKey);
      };

      audio.onended = () => {
        setPlayingVoice(null);
        setLoadingVoice(null);
      };

      audio.onerror = (e) => {
        console.error("Failed to load audio preview:", e);
        setLoadingVoice(null);
        setPlayingVoice(null);
      };

      audio.play().catch((err) => {
        console.error("Audio play failed:", err);
        setLoadingVoice(null);
        setPlayingVoice(null);
      });
    }
  };


  const handleReset = () => {
    setIdea("");
    setDuration("5_min");
    setStyle("documentary");
    setSelectedProvider("edge-tts");
    setSelectedVoice("ar-SA-HamedNeural");
    setJobId(null);
    setStatusData(null);
    setErrorMsg(null);
    setScreen("input");
  };

  // Get current active provider voices
  const currentProviderObj = providersCatalog.find((p) => p.provider === selectedProvider) || providersCatalog[0];
  const currentVoices = currentProviderObj ? currentProviderObj.voices : [];

  // Progress screen stages config
  const stages = [
    { key: "script", label: "توليد السكريبت" },
    { key: "tts", label: "توليد الصوت" },
    { key: "footage", label: "جلب اللقطات" },
    { key: "captions", label: "إنشاء الترجمة" },
    { key: "render", label: "التجميع النهائي" },
  ];

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-[#f5f5f5] flex flex-col items-center justify-center p-4 md:p-8 font-sans selection:bg-amber-500/30">
      
      {/* Outer subtle glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[40vh] bg-gradient-to-b from-amber-500/5 to-transparent blur-[120px] pointer-events-none" />

      {/* Brand Layout */}
      <div className="w-full max-w-4xl z-10 flex flex-col items-center">
        
        {/* Header */}
        <header className="mb-10 text-center flex flex-col items-center gap-3">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#171717] border border-neutral-800 text-xs font-semibold text-neutral-400 select-none">
            <Sparkles className="w-3.5 h-3.5 text-amber-500 animate-pulse" />
            <span>imaginAI Mini v1.0</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight bg-gradient-to-r from-amber-400 via-pink-500 to-rose-500 bg-clip-text text-transparent py-1">
            imaginAI
          </h1>
        </header>

        {/* ── Screen 1: Input Screen ────────────────────────────────────────── */}
        {screen === "input" && (
          <div className="w-full max-w-2xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="text-center mb-8">
              <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-[#f5f5f5]">
                ماذا تريد أن تصنع اليوم؟
              </h2>
              <p className="text-neutral-400 mt-2 text-sm md:text-base">
                اكتب فكرتك واختر القالب وسيتم توليد الفيديو تلقائياً بواسطة الذكاء الاصطناعي
              </p>
            </div>

            <form onSubmit={handleProceedToVoice} className="relative bg-[#171717]/80 backdrop-blur-md border border-neutral-800 rounded-md p-4 transition-all duration-300 focus-within:border-amber-500/40 focus-within:shadow-[0_0_30px_-5px_rgba(245,158,11,0.15)]">
              
              {/* Toolbar Ribbon */}
              <div className="flex flex-wrap items-center gap-2 mb-4 pb-4 border-b border-neutral-800/60 text-xs" dir="rtl">
                
                {/* Style Dropdown */}
                <div className="flex items-center gap-1.5 bg-neutral-950 px-3 py-1.5 rounded-full border border-neutral-800">
                  <span className="text-neutral-500 font-medium">الأسلوب:</span>
                  <select
                    value={style}
                    onChange={(e) => setStyle(e.target.value as StyleType)}
                    className="bg-transparent text-amber-400 font-semibold focus:outline-none cursor-pointer"
                  >
                    {STYLES.map((s) => (
                      <option key={s.id} value={s.id} className="bg-neutral-900 text-white">
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Duration Selector */}
                <div className="flex bg-neutral-950 p-[3px] rounded-full border border-neutral-800">
                  <button
                    type="button"
                    onClick={() => setDuration("5_min")}
                    className={`px-3 py-1 rounded-full text-[11px] font-semibold transition-all ${
                      duration === "5_min"
                        ? "bg-neutral-800 text-white shadow-sm"
                        : "text-neutral-500 hover:text-neutral-300"
                    }`}
                  >
                    5 دقائق
                  </button>
                  <button
                    type="button"
                    onClick={() => setDuration("8_min")}
                    className={`px-3 py-1 rounded-full text-[11px] font-semibold transition-all ${
                      duration === "8_min"
                        ? "bg-neutral-800 text-white shadow-sm"
                        : "text-neutral-500 hover:text-neutral-300"
                    }`}
                  >
                    8 دقائق
                  </button>
                  <button
                    type="button"
                    onClick={() => setDuration("10_min")}
                    className={`px-3 py-1 rounded-full text-[11px] font-semibold transition-all ${
                      duration === "10_min"
                        ? "bg-neutral-800 text-white shadow-sm"
                        : "text-neutral-500 hover:text-neutral-300"
                    }`}
                  >
                    10 دقائق
                  </button>
                </div>

                {/* Format Badge */}
                <div className="px-3 py-1.5 rounded-full bg-neutral-900 border border-neutral-800 text-neutral-400 font-medium cursor-default">
                  أفقي 16:9
                </div>

                {/* Notification Permission Toggle */}
                {notifPermission !== "granted" && (
                  <button
                    type="button"
                    onClick={requestNotificationPermission}
                    className="px-3 py-1.5 rounded-full bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/20 text-amber-400 text-xs font-semibold transition cursor-pointer"
                    title="انقر لتفعيل إشعارات المتصفح عند اكتمال الفيديو"
                  >
                    🔔 تفعيل الإشعارات
                  </button>
                )}

              </div>

              {/* Textarea Area */}
              <div className="relative">
                <textarea
                  rows={4}
                  value={idea}
                  onChange={(e) => setIdea(e.target.value)}
                  placeholder="اكتب فكرتك هنا... مثال: قائمة بأغرب 5 اكتشافات أثرية محيرة في العالم"
                  className="w-full bg-transparent border-0 text-[#f5f5f5] placeholder:text-neutral-600 focus:ring-0 focus:outline-none resize-none text-right placeholder:text-right text-base leading-relaxed pl-12 pr-1"
                  dir="rtl"
                />

                <div className="absolute bottom-1 left-1 flex items-center">
                  <button
                    type="submit"
                    disabled={!idea.trim()}
                    className={`px-4 py-2 rounded-full flex items-center gap-2 text-xs font-bold transition-all duration-300 ${
                      idea.trim()
                        ? "bg-gradient-to-br from-[#f59e0b] to-[#ec4899] text-white shadow-lg shadow-amber-500/20 hover:scale-105 active:scale-95 cursor-pointer"
                        : "bg-neutral-800 text-neutral-600 cursor-not-allowed"
                    }`}
                  >
                    <span>التالي: اختيار الصوت</span>
                    <ArrowRight className="w-4 h-4 rotate-180" />
                  </button>
                </div>
              </div>

            </form>

            {errorMsg && (
              <div className="mt-4 p-3 bg-rose-500/10 border border-rose-500/20 rounded-md flex items-center gap-3 text-rose-400 text-sm animate-in fade-in duration-300">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <p className="text-right flex-1" dir="rtl">{errorMsg}</p>
              </div>
            )}
          </div>
        )}

        {/* ── Screen 2: Voice Picker Screen (Multi-Provider TTS) ───────────── */}
        {screen === "voice" && (
          <div className="w-full max-w-3xl bg-[#171717] border border-neutral-800 rounded-xl p-6 animate-in fade-in duration-400" dir="rtl">
            <div className="text-center mb-6">
              <h3 className="text-xl font-bold text-[#f5f5f5] flex items-center justify-center gap-2">
                <Volume2 className="w-5 h-5 text-amber-500" />
                <span>اختر مكتبة الصوت ونبرة الراوي</span>
              </h3>
              <p className="text-xs text-neutral-400 mt-1">
                استمع إلى المعاينة الصوتية المباشرة واختر الصوت المفضل لفيديوك
              </p>
            </div>

            {/* Provider Tabs */}
            <div className="flex flex-wrap items-center justify-center gap-2 mb-6 p-1.5 bg-neutral-900/80 rounded-xl border border-neutral-800">
              {providersCatalog.map((p) => {
                const isActive = selectedProvider === p.provider;
                return (
                  <button
                    key={p.provider}
                    type="button"
                    onClick={() => {
                      setSelectedProvider(p.provider);
                      if (p.voices.length > 0) {
                        setSelectedVoice(p.voices[0].id);
                      }
                    }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                      isActive
                        ? "bg-amber-500 text-black shadow-md shadow-amber-500/20 scale-[1.02]"
                        : "text-neutral-400 hover:text-white hover:bg-neutral-800"
                    }`}
                  >
                    {p.provider === "edge-tts" && <Zap className="w-3.5 h-3.5" />}
                    {p.provider === "gemini" && <Radio className="w-3.5 h-3.5" />}
                    {p.provider === "gtts" && <Globe className="w-3.5 h-3.5" />}
                    <span>{p.provider_name}</span>
                  </button>
                );
              })}
            </div>

            {/* Active Provider Description */}
            <div className="mb-4 text-center">
              <span className="inline-block text-[11px] px-3 py-1 rounded-full bg-neutral-900 border border-neutral-800/80 text-amber-400 font-medium">
                {currentProviderObj?.desc}
              </span>
            </div>

            {/* Voice Cards Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
              {currentVoices.map((v) => {
                const isSelected = selectedVoice === v.id;
                const voiceKey = `${selectedProvider}:${v.id}`;
                const isPlaying = playingVoice === voiceKey;
                const isLoading = loadingVoice === voiceKey;

                return (
                  <div
                    key={v.id}
                    onClick={() => setSelectedVoice(v.id)}
                    className={`p-4 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                      isSelected
                        ? "bg-amber-500/10 border-amber-500 shadow-md shadow-amber-500/10"
                        : "bg-neutral-900/60 border-neutral-800 hover:border-neutral-700"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-bold text-sm text-white">{v.name}</h4>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-neutral-800 text-neutral-400 font-semibold">
                            {v.gender === "male" ? "ذكر ♂" : "أنثى ♀"}
                          </span>
                          <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-medium">
                            {v.lang}
                          </span>
                        </div>
                        <p className="text-xs text-neutral-400 mt-1 leading-snug">{v.desc}</p>
                      </div>

                      {/* Play Preview Button */}
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          togglePlaySample(v);
                        }}
                        disabled={isLoading}
                        className={`w-9 h-9 rounded-full shrink-0 flex items-center justify-center transition ${
                          isPlaying
                            ? "bg-amber-500 text-black animate-pulse shadow-md shadow-amber-500/30"
                            : isLoading
                            ? "bg-neutral-800 text-amber-400 cursor-wait"
                            : "bg-neutral-800 text-neutral-300 hover:bg-neutral-700 hover:text-white"
                        }`}
                        title="استماع مباشر لمعاينة الصوت"
                      >
                        {isLoading ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : isPlaying ? (
                          <Pause className="w-4 h-4" />
                        ) : (
                          <Play className="w-4 h-4 ml-0.5" />
                        )}
                      </button>
                    </div>

                    <div className="mt-3 pt-3 border-t border-neutral-800/40 flex items-center justify-between text-xs">
                      <span className={isSelected ? "text-amber-400 font-bold" : "text-neutral-500"}>
                        {isSelected ? "✓ صوت مُحدد" : "انقر للاختيار"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Action buttons */}
            <div className="flex items-center justify-between gap-4">
              <button
                type="button"
                onClick={() => setScreen("input")}
                className="px-5 py-2.5 rounded-full bg-neutral-900 border border-neutral-800 text-xs font-semibold text-neutral-400 hover:text-white transition"
              >
                تعديل الفكرة
              </button>

              <button
                type="button"
                onClick={handleStartGeneration}
                className="px-6 py-2.5 rounded-full bg-gradient-to-r from-amber-500 to-pink-500 text-white text-xs font-bold shadow-lg shadow-amber-500/20 hover:scale-105 active:scale-95 transition"
              >
                بدء التوليد كـ (imaginAI Mini)
              </button>
            </div>
          </div>
        )}

        {/* ── Screen 3: Progress Tracker Screen ─────────────────────────────── */}
        {screen === "progress" && (
          <div className="w-full max-w-md bg-[#171717] border border-neutral-800 rounded-md p-6 animate-in fade-in duration-400">
            <div className="flex flex-col items-center mb-6">
              <Loader2 className="w-8 h-8 text-amber-500 animate-spin mb-3" />
              <h3 className="text-lg font-bold">جاري إنشاء الفيديو...</h3>
              <p className="text-xs text-neutral-500 mt-1">تستغرق هذه العملية بضع دقائق حسب مدة الفيديو المطلوبة</p>
            </div>

            <div className="space-y-4" dir="rtl">
              {stages.map((stage) => {
                const stageStatus = statusData?.stages?.[stage.key as keyof typeof statusData.stages] || "pending";
                
                let icon = <div className="w-4 h-4 rounded-full border border-neutral-700 bg-neutral-900" />;
                let textStyle = "text-neutral-500";

                if (stageStatus === "processing") {
                  icon = <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />;
                  textStyle = "text-amber-400 font-semibold";
                } else if (stageStatus === "done") {
                  icon = <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
                  textStyle = "text-neutral-300";
                } else if (stageStatus === "failed") {
                  icon = <AlertCircle className="w-4 h-4 text-rose-500" />;
                  textStyle = "text-rose-400 font-semibold";
                }

                return (
                  <div 
                    key={stage.key} 
                    className={`flex items-center gap-3 p-2.5 rounded-lg border transition ${
                      stageStatus === "processing" 
                        ? "bg-amber-500/5 border-amber-500/10" 
                        : "border-transparent"
                    }`}
                  >
                    <span className="shrink-0">{icon}</span>
                    <span className={`text-sm ${textStyle} flex-1 text-right`}>{stage.label}</span>
                  </div>
                );
              })}
            </div>

            {errorMsg && (
              <div className="mt-6 p-4 bg-rose-500/10 border border-rose-500/20 rounded-md flex flex-col gap-3 animate-in fade-in">
                <div className="flex items-center gap-2 text-rose-400 text-sm" dir="rtl">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span className="font-bold">خطأ في خط الإخراج:</span>
                </div>
                <p className="text-xs text-neutral-400 text-right leading-relaxed" dir="rtl">{errorMsg}</p>
                <button
                  onClick={handleReset}
                  className="mt-2 w-full py-2 rounded-full bg-neutral-800 hover:bg-neutral-700 text-xs font-semibold text-neutral-300 transition"
                >
                  العودة للبداية
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Screen 4: Result Screen ───────────────────────────────────────── */}
        {screen === "result" && jobId && (
          <div className="w-full max-w-3xl bg-[#171717] border border-neutral-800 rounded-md p-6 animate-in fade-in duration-500">
            <div className="text-center mb-6">
              <h3 className="text-xl font-bold bg-gradient-to-r from-amber-400 to-pink-500 bg-clip-text text-transparent">
                تم تجهيز الفيديو بنجاح!
              </h3>
              <p className="text-xs text-[#a3a3a3] mt-1">يمكنك الآن مشاهدة الفيديو أو تحميله مباشرة بجودة عالية</p>
            </div>

            {/* Video Player */}
            <div className="relative aspect-video rounded-lg overflow-hidden border border-neutral-800 bg-black mb-6 group">
              <video
                src={getDownloadUrl(jobId)}
                controls
                className="w-full h-full object-contain"
              />
            </div>

            {/* Pixabay & Pexels Attributions */}
            <div className="bg-neutral-900 p-3 rounded-lg border border-neutral-800/40 mb-6" dir="rtl">
              <h4 className="text-[11px] font-semibold text-amber-500/80 mb-2 flex items-center gap-1.5">
                <Info className="w-3 h-3" />
                <span>إسناد مصادر اللقطات المستعملة (Attributions)</span>
              </h4>
              <p className="text-[10px] text-neutral-500 leading-relaxed text-right">
                تم ترخيص واستعمال كافة مقاطع الفيديو بموجب التراخيص المجانية لـ Pexels و Pixabay. حقوق الصوت والسكريبت تعود لـ imaginAI Mini.
              </p>
            </div>

            {/* Buttons Panel */}
            <div className="flex flex-col sm:flex-row gap-3 justify-center items-center">
              <a
                href={getDownloadUrl(jobId)}
                download={`imaginai_${jobId}.mp4`}
                className="w-full sm:w-auto px-6 py-3 rounded-full bg-gradient-to-r from-amber-500 to-pink-500 text-white font-semibold text-sm flex items-center justify-center gap-2 hover:scale-[1.03] active:scale-95 transition-all shadow-md shadow-amber-500/10 cursor-pointer"
              >
                <Download className="w-4 h-4" />
                <span>تحميل الفيديو</span>
              </a>

              <button
                onClick={handleReset}
                className="w-full sm:w-auto px-6 py-3 rounded-full bg-neutral-900 border border-neutral-800 text-neutral-300 font-semibold text-sm flex items-center justify-center gap-2 hover:bg-neutral-800 hover:text-white transition cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                <span>إنشاء فيديو جديد</span>
              </button>
            </div>
          </div>
        )}

      </div>

      {/* ── Floating Feedback Button ─────────────────────────────────────── */}
      <button
        onClick={() => setIsFeedbackOpen(true)}
        className="fixed bottom-5 left-5 z-40 px-4 py-2.5 rounded-full bg-neutral-900/90 border border-neutral-700/80 text-neutral-200 hover:text-white hover:bg-neutral-800 shadow-xl backdrop-blur-md text-xs font-semibold flex items-center gap-2 transition-all hover:scale-105 active:scale-95 cursor-pointer"
        dir="rtl"
      >
        <MessageSquare className="w-4 h-4 text-amber-400" />
        <span>أرسل ملاحظاتك 💬</span>
      </button>

      {/* ── Feedback Modal ──────────────────────────────────────────────── */}
      {isFeedbackOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200" dir="rtl">
          <div className="w-full max-w-md bg-[#171717] border border-neutral-800 rounded-xl p-6 shadow-2xl relative">
            <button
              onClick={() => setIsFeedbackOpen(false)}
              className="absolute top-4 left-4 text-neutral-400 hover:text-white text-xs font-bold w-6 h-6 rounded-full bg-neutral-800 flex items-center justify-center cursor-pointer"
            >
              ✕
            </button>

            <div className="flex items-center gap-2 mb-4">
              <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <MessageSquare className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">شاركونا آرائكم وملاحظاتكم</h3>
                <p className="text-xs text-neutral-400">ساعدنا في تحسين imaginAI Mini للجميع</p>
              </div>
            </div>

            <form onSubmit={handleSendFeedback} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                  ملاحظتك أو اقتراحك <span className="text-amber-500">*</span>
                </label>
                <textarea
                  required
                  rows={4}
                  value={feedbackMsg}
                  onChange={(e) => setFeedbackMsg(e.target.value)}
                  placeholder="اكتب ملاحظتك، الاقتراحات، أو المشاكل التي واجهتك هنا..."
                  className="w-full bg-neutral-900 border border-neutral-800 rounded-lg p-3 text-xs text-neutral-200 focus:outline-none focus:border-amber-500/50 transition placeholder:text-neutral-600 resize-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-300 mb-1.5">
                  معلومات التواصل (اختياري)
                </label>
                <input
                  type="text"
                  value={feedbackContact}
                  onChange={(e) => setFeedbackContact(e.target.value)}
                  placeholder="بريدك الإلكتروني أو اسمك للتواصل معك"
                  className="w-full bg-neutral-900 border border-neutral-800 rounded-lg p-2.5 text-xs text-neutral-200 focus:outline-none focus:border-amber-500/50 transition placeholder:text-neutral-600"
                />
              </div>

              {feedbackStatus && (
                <div
                  className={`p-3 rounded-lg text-xs border ${
                    feedbackStatus.type === "success"
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                      : "bg-rose-500/10 border-rose-500/30 text-rose-400"
                  }`}
                >
                  {feedbackStatus.text}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsFeedbackOpen(false)}
                  className="px-4 py-2 rounded-lg bg-neutral-800 text-neutral-300 hover:text-white text-xs font-medium transition cursor-pointer"
                >
                  إلغاء
                </button>
                <button
                  type="submit"
                  disabled={feedbackSending}
                  className="px-5 py-2 rounded-lg bg-gradient-to-r from-amber-500 to-pink-500 text-white text-xs font-semibold flex items-center gap-1.5 hover:scale-[1.02] active:scale-95 disabled:opacity-50 transition shadow-md shadow-amber-500/10 cursor-pointer"
                >
                  {feedbackSending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                  <span>إرسال الملاحظة</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
