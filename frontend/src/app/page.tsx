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
  MessageSquare,
  Landmark,
  Cpu,
  TrendingUp,
  FolderPlus,
  Video,
  Clock,
  Layers,
  ChevronLeft,
  RotateCcw,
  Subtitles,
  X,
  Check,
  Type,
  Palette,
  Sliders,
  Mic,
  Square,
  Upload,
  Wand2
} from "lucide-react";
import { 
  createJob, 
  getJobStatus, 
  getDownloadUrl, 
  getVoicesCatalog, 
  getVoicePreviewUrl, 
  cloneVoice,
  sendFeedback,
  getNiches,
  getProjects,
  createProject,
  getProjectVideos,
  getVideoStreamUrl,
  getCustomFonts,
  uploadCustomFont,
  getJobReviewData,
  resumeJob,
  approveJobSections,
  ReviewData,
  CustomFont,
  JobStatusResponse, 
  VoiceProviderCatalog, 
  VoiceItem,
  DomainCategory,
  SubNiche,
  Project,
  VideoItem
} from "../lib/api";

type ScreenState = "dashboard" | "wizard_step1" | "wizard_step2" | "wizard_step3" | "input" | "voice" | "progress" | "review" | "result";

// Fallback Voice Providers catalog
const DEFAULT_PROVIDERS: VoiceProviderCatalog[] = [
  {
    provider: "gemini",
    provider_name: "Google Gemini (imaginAI Mini)",
    desc: "أصوات الذكاء الاصطناعي الرسمية المتاحة بموديل Gemini TTS",
    voices: [
      { id: "Kore", name: "كوري (Kore)", gender: "female", lang: "متعدد اللغات", desc: "صوت أنثوي طبيعي وحيوي مناسب للقصص والسرد" },
      { id: "Puck", name: "بوك (Puck)", gender: "male", lang: "متعدد اللغات", desc: "صوت ذكوري رزين وهادئ" },
      { id: "Charon", name: "كارون (Charon)", gender: "male", lang: "متعدد اللغات", desc: "صوت ذكوري عميق ودافئ للوثائقيات" },
      { id: "Fenrir", name: "فينرير (Fenrir)", gender: "male", lang: "متعدد اللغات", desc: "صوت ذكوري قوي ومباشر" },
      { id: "Aoede", name: "أويدي (Aoede)", gender: "female", lang: "متعدد اللغات", desc: "صوت أنثوي سينمائي ومميز" },
      { id: "Leda", name: "ليدا (Leda)", gender: "female", lang: "متعدد اللغات", desc: "صوت أنثوي واضح ورقيق" },
      { id: "Orus", name: "اوروس (Orus)", gender: "male", lang: "متعدد اللغات", desc: "صوت ذكوري رسمي ورصين" },
      { id: "Zephyr", name: "زفير (Zephyr)", gender: "female", lang: "متعدد اللغات", desc: "صوت أنثوي هادئ وناعم" },
    ],
  },
  {
    provider: "fish-audio",
    provider_name: "Fish Audio",
    desc: "أصوات فائقة الجودة من منصة Fish Audio المتاحة لحسابك",
    voices: [
      { id: "default", name: "Fish Audio Default Voice", gender: "neutral", lang: "العربية / English", desc: "الصوت الافتراضي الأساسي لمنصة Fish Audio" },
    ],
  },
];

export default function Home() {
  // ── Application Flow States ────────────────────────────────────────────────
  const [screen, setScreen] = useState<ScreenState>("dashboard");

  // Projects & Active Project State
  const [projectsList, setProjectsList] = useState<Project[]>([]);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [activeProjectVideos, setActiveProjectVideos] = useState<VideoItem[]>([]);
  const [loadingProjects, setLoadingProjects] = useState<boolean>(true);

  // Wizard Creation Flow State (Mandatory Step 1 -> Step 2 -> Step 3)
  const [projectNameInput, setProjectNameInput] = useState<string>("");
  const [selectedDomain, setSelectedDomain] = useState<DomainCategory | null>(null);
  const [selectedNiche, setSelectedNiche] = useState<SubNiche | null>(null);
  const [customNicheText, setCustomNicheText] = useState<string>("");
  const [isCustomNicheActive, setIsCustomNicheActive] = useState<boolean>(false);
  const [creatingProject, setCreatingProject] = useState<boolean>(false);

  // Input & Generation State
  const [idea, setIdea] = useState("");
  const [duration, setDuration] = useState<"5_min" | "8_min" | "10_min" | "15_min">("5_min");

  // Input Mode & Provided Script State
  const [inputMode, setInputMode] = useState<"ai_generated" | "script_provided">("ai_generated");
  const [providedScript, setProvidedScript] = useState<string>("");

  // Optional Additional Context State
  const [isContextOpen, setIsContextOpen] = useState<boolean>(false);
  const [additionalContext, setAdditionalContext] = useState<string>("");

  // Niche & Voices Catalogs
  const [domainsCatalog, setDomainsCatalog] = useState<DomainCategory[]>([]);
  const [providersCatalog, setProvidersCatalog] = useState<VoiceProviderCatalog[]>(DEFAULT_PROVIDERS);
  const [selectedProvider, setSelectedProvider] = useState<"gemini" | "fish-audio" | "edge-tts" | "gtts">("gemini");
  const [selectedVoice, setSelectedVoice] = useState<string>("Kore");
  const [selectedMusic, setSelectedMusic] = useState<string>("auto");

  // Web Notification State

  const [notifPermission, setNotifPermission] = useState<string>("default");

  // Captions Customization State (Enhanced for Free Color Picker & CapCut Effects)
  const [captionConfig, setCaptionConfig] = useState({
    color: "#FFFFFF",
    highlight_color: "#FACC15",
    effect: "none",
    font: "Cairo",
    size_percent: 100,
    position: "bottom",
  });
  const [tempCaptionConfig, setTempCaptionConfig] = useState(captionConfig);
  const [isCaptionModalOpen, setIsCaptionModalOpen] = useState(false);

  // Custom Fonts State
  const [customFonts, setCustomFonts] = useState<CustomFont[]>([]);
  const [isUploadFontOpen, setIsUploadFontOpen] = useState(false);
  const [uploadFontName, setUploadFontName] = useState("");
  const [uploadFontFile, setUploadFontFile] = useState<File | null>(null);
  const [uploadFontLoading, setUploadFontLoading] = useState(false);
  const [uploadFontError, setUploadFontError] = useState<string | null>(null);

  // Review Stage State
  const [reviewData, setReviewData] = useState<ReviewData | null>(null);
  const [editedScenesMap, setEditedScenesMap] = useState<Record<number, string>>({});
  const [resumingJob, setResumingJob] = useState<boolean>(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  // Voice Cloning State (Fish Audio)
  const [isCloningOpen, setIsCloningOpen] = useState(false);
  const [cloneVoiceName, setCloneVoiceName] = useState("");
  const [cloneFile, setCloneFile] = useState<File | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [recordedAudioUrl, setRecordedAudioUrl] = useState<string | null>(null);
  const [cloningLoading, setCloningLoading] = useState(false);
  const [cloningError, setCloningError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Audio Player State for voice samples
  const [playingVoice, setPlayingVoice] = useState<string | null>(null);
  const [loadingVoice, setLoadingVoice] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Job Tracking
  const [jobId, setJobId] = useState<string | null>(null);
  const [statusData, setStatusData] = useState<JobStatusResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);

  // Section Approval Modal State (Dynamic Analysis)
  const [sectionApprovalData, setSectionApprovalData] = useState<any>(null);
  const [submittingSectionDecision, setSubmittingSectionDecision] = useState(false);

  // Feedback Modal State
  const [isFeedbackOpen, setIsFeedbackOpen] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState("");
  const [feedbackContact, setFeedbackContact] = useState("");
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // ── Voice Recording & Cloning Handlers (Fish Audio) ────────────────────────
  const handleStartRecording = async () => {
    try {
      setCloningError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
        const file = new File([audioBlob], "voice_recording.wav", { type: "audio/wav" });
        setCloneFile(file);
        setRecordedAudioUrl(URL.createObjectURL(audioBlob));
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(200);
      setIsRecording(true);
      setRecordingTime(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      console.error("Microphone access error:", err);
      setCloningError("تعذر الوصول إلى الميكروفون. يرجى التأكد من إعطاء إذان الاستخدام في المتصفح.");
    }
  };

  const handleStopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    }
  };

  const handleCloneSubmit = async () => {
    if (!cloneFile) {
      setCloningError("يرجى تسجيل صوتك عبر الميكروفون أو رفع ملف صوتي.");
      return;
    }
    if (!cloneVoiceName.trim()) {
      setCloningError("يرجى كتابة اسم للصوت المستنسخ.");
      return;
    }

    setCloningLoading(true);
    setCloningError(null);

    try {
      const result = await cloneVoice(cloneFile, cloneVoiceName.trim());
      // Refresh catalog
      const catRes = await getVoicesCatalog();
      if (catRes.providers) {
        setProvidersCatalog(catRes.providers);
      }
      setSelectedProvider("fish-audio");
      if (result.voice && result.voice.id) {
        setSelectedVoice(result.voice.id);
      }
      setIsCloningOpen(false);
      setCloneVoiceName("");
      setCloneFile(null);
      setRecordedAudioUrl(null);
    } catch (err: any) {
      setCloningError(err.message || "حدث خطأ أثناء استنساخ الصوت.");
    } finally {
      setCloningLoading(false);
    }
  };

  // ── Initial Fetch Projects & Niches ────────────────────────────────────────
  const fetchAllProjects = async () => {
    setLoadingProjects(true);
    try {
      const res = await getProjects();
      setProjectsList(res.projects || []);
      if (res.projects && res.projects.length > 0 && !activeProject) {
        // Select latest project by default
        const latest = res.projects[0];
        setActiveProject(latest);
        loadProjectVideos(latest.project_id);
      }
    } catch (e) {
      console.error("Failed to load projects:", e);
    } finally {
      setLoadingProjects(false);
    }
  };

  const loadProjectVideos = async (projId: string) => {
    try {
      const res = await getProjectVideos(projId);
      setActiveProjectVideos(res.videos || []);
    } catch (e) {
      console.error("Failed to fetch project videos:", e);
    }
  };

  const loadCustomFonts = async () => {
    try {
      const res = await getCustomFonts();
      setCustomFonts(res.fonts || []);
    } catch (e) {
      console.error("Failed to load custom fonts:", e);
    }
  };

  const handleUploadFontSubmit = async () => {
    if (!uploadFontFile) {
      setUploadFontError("يرجى اختيار ملف الخط (.ttf أو .otf)");
      return;
    }
    if (!uploadFontName.trim()) {
      setUploadFontError("يرجى كتابة اسم للخط المرفوع");
      return;
    }

    setUploadFontLoading(true);
    setUploadFontError(null);

    try {
      const result = await uploadCustomFont(uploadFontFile, uploadFontName.trim());
      await loadCustomFonts();
      if (result.font) {
        setTempCaptionConfig((prev) => ({ ...prev, font: `custom:${result.font.id}` }));
      }
      setIsUploadFontOpen(false);
      setUploadFontName("");
      setUploadFontFile(null);
    } catch (err: any) {
      setUploadFontError(err.message || "حدث خطأ أثناء رفع الخط.");
    } finally {
      setUploadFontLoading(false);
    }
  };

  useEffect(() => {
    getNiches()
      .then((res) => {
        if (res?.domains) setDomainsCatalog(res.domains);
      })
      .catch((e) => console.error("Failed to load niches catalog:", e));

    getVoicesCatalog()
      .then((data) => {
        if (data.providers && data.providers.length > 0) {
          setProvidersCatalog(data.providers);
        }
      })
      .catch((err) => console.log("Using default voice catalog:", err));

    fetchAllProjects();
    loadCustomFonts();
  }, []);

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

  // ── Poll Job Status ──────────────────────────────────────────────────────
  const startPolling = (id: string) => {
    if (pollingInterval.current) clearInterval(pollingInterval.current);
    
    pollingInterval.current = setInterval(async () => {
      try {
        const data = await getJobStatus(id);
        setStatusData(data);
        
        if (data.status === "pending_section_approval") {
          setSectionApprovalData((data as any).section_proposal || true);
          if (pollingInterval.current) clearInterval(pollingInterval.current);
        } else if (data.status === "pending_review") {
          try {
            const rev = await getJobReviewData(id);
            setReviewData(rev);
            const initialMap: Record<number, string> = {};
            rev.scenes.forEach((s) => {
              initialMap[s.scene_index] = s.narration;
            });
            setEditedScenesMap(initialMap);
            setScreen("review");
            if (pollingInterval.current) clearInterval(pollingInterval.current);
          } catch (err) {
            console.error("Failed to load review data:", err);
          }
        } else if (data.status === "done") {
          setScreen("result");
          if (pollingInterval.current) clearInterval(pollingInterval.current);

          // Refresh saved project videos from SQLite DB immediately!
          if (activeProject) {
            loadProjectVideos(activeProject.project_id);
            fetchAllProjects();
          }

          // Audio chime on completion using Web Audio API
          try {
            const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(523.25, ctx.currentTime);
            osc.frequency.setValueAtTime(659.25, ctx.currentTime + 0.15);
            osc.frequency.setValueAtTime(783.99, ctx.currentTime + 0.3);
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + 0.8);
          } catch (e) {
            console.error("Audio chime error:", e);
          }

          if (
            typeof window !== "undefined" &&
            "Notification" in window &&
            Notification.permission === "granted"
          ) {
            try {
              new Notification("فيديودك جاهز 🎬", {
                body: "تم إكمال رندر وحفظ الفيديو بقاعدة البيانات بنجاح!",
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

  const handleResumeSubmit = async () => {
    if (!statusData?.job_id || !reviewData) return;
    setResumingJob(true);
    setReviewError(null);
    try {
      const payload = reviewData.scenes.map((sc) => ({
        scene_index: sc.scene_index,
        narration: editedScenesMap[sc.scene_index] ?? sc.narration,
      }));
      await resumeJob(statusData.job_id, payload);
      setScreen("progress");
      startPolling(statusData.job_id);
    } catch (err: any) {
      setReviewError(err.message || "حدث خطأ أثناء استئناف الـ pipeline.");
    } finally {
      setResumingJob(false);
    }
  };

  const handleSectionDecision = async (apply: boolean) => {
    if (!statusData?.job_id) return;
    setSubmittingSectionDecision(true);
    try {
      await approveJobSections(statusData.job_id, apply);
      setSectionApprovalData(null);
      startPolling(statusData.job_id);
    } catch (err: any) {
      alert(err.message || "حدث خطأ أثناء معالجة قرار الأقسام");
    } finally {
      setSubmittingSectionDecision(false);
    }
  };

  // ── Project Wizard Handlers ──────────────────────────────────────────────
  const handleStartNewProjectWizard = () => {
    setProjectNameInput("");
    setSelectedDomain(null);
    setSelectedNiche(null);
    setCustomNicheText("");
    setIsCustomNicheActive(false);
    setScreen("wizard_step1");
  };

  const handleStep1Submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectNameInput.trim()) return;
    setScreen("wizard_step2");
  };

  const handleSelectDomain = (domain: DomainCategory) => {
    setSelectedDomain(domain);
    setSelectedNiche(null);
    setIsCustomNicheActive(false);
    setScreen("wizard_step3");
  };

  const handleCreateProjectFinal = async () => {
    if (!selectedDomain) return;
    let nicheIdToUse = "";

    if (isCustomNicheActive) {
      if (!customNicheText.trim()) return;
      nicheIdToUse = customNicheText.trim();
    } else {
      if (!selectedNiche) return;
      nicheIdToUse = selectedNiche.id;
    }

    setCreatingProject(true);
    try {
      const proj = await createProject({
        name: projectNameInput.trim() || "مشروع جديد",
        domain: selectedDomain.id,
        niche: nicheIdToUse,
      });

      setActiveProject(proj);
      await fetchAllProjects();
      await loadProjectVideos(proj.project_id);

      // Auto-set music mood from niche if available
      if (selectedNiche?.music_style) {
        setSelectedMusic(selectedNiche.music_style);
      } else {
        setSelectedMusic("auto");
      }

      // Automatically transition to creation input screen for this project!
      setScreen("input");
    } catch (err: any) {
      console.error("Failed to create project:", err);
      alert("حدث خطأ أثناء إنشاء المشروع. الرجاء المحاولة مرة أخرى.");
    } finally {
      setCreatingProject(false);
    }
  };

  const handleSelectActiveProject = (proj: Project) => {
    setActiveProject(proj);
    loadProjectVideos(proj.project_id);
    setScreen("input");
  };

  const handleProceedToVoice = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputMode === "ai_generated" && !idea.trim()) return;
    if (inputMode === "script_provided" && !providedScript.trim()) return;
    setScreen("voice");
  };

  const handleStartGeneration = async () => {
    if (!activeProject) {
      alert("الرجاء اختيار أو إنشاء مشروع أولاً");
      return;
    }

    setErrorMsg(null);
    setStatusData(null);
    setScreen("progress");

    try {
      const finalIdea = inputMode === "script_provided" ? providedScript.trim().slice(0, 80) : idea.trim();
      const res = await createJob({
        idea: finalIdea,
        duration: inputMode === "script_provided" ? "5_min" : duration,
        voice_provider: selectedProvider,
        voice: selectedVoice,
        niche_id: activeProject.niche,
        custom_niche: activeProject.niche,
        music_track: selectedMusic,
        caption_config: captionConfig,
        input_mode: inputMode,
        provided_script: inputMode === "script_provided" ? providedScript.trim() : undefined,
        additional_context: inputMode === "ai_generated" && additionalContext.trim() ? additionalContext.trim() : undefined,
      });
      setJobId(res.job_id);
      startPolling(res.job_id);
    } catch (err: any) {
      setErrorMsg(err.message || "حدث خطأ أثناء بدء عملية توليد الفيديو. يرجى التأكد من الموديل المختار والخدمة.");
      setScreen("voice");
    }
  };

  const togglePlaySample = (voice: VoiceItem) => {
    const voiceKey = `${selectedProvider}:${voice.id}`;

    // Clean up existing active audio instance
    if (audioRef.current) {
      const prevAudio = audioRef.current;
      prevAudio.onplay = null;
      prevAudio.onended = null;
      prevAudio.onerror = null;
      try {
        prevAudio.pause();
        prevAudio.currentTime = 0;
      } catch (_) {}
      audioRef.current = null;
    }

    if (playingVoice === voiceKey || loadingVoice === voiceKey) {
      setPlayingVoice(null);
      setLoadingVoice(null);
      return;
    }

    setLoadingVoice(voiceKey);
    setPlayingVoice(null);

    // Try static sample file first
    const safeVoiceId = voice.id.replace(/\//g, "_").replace(/\\/g, "_");
    const staticSampleUrl = `/voice-samples/${selectedProvider}/${safeVoiceId}.mp3`;
    const fallbackUrl = getVoicePreviewUrl(selectedProvider, voice.id);

    const playAudioSource = (url: string, isFallback: boolean = false) => {
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onplay = () => {
        if (audioRef.current === audio) {
          setLoadingVoice(null);
          setPlayingVoice(voiceKey);
        }
      };

      audio.onended = () => {
        if (audioRef.current === audio) {
          setPlayingVoice(null);
          setLoadingVoice(null);
          audioRef.current = null;
        }
      };

      audio.onerror = () => {
        // Guard against race conditions when user switches voices rapidly
        if (audioRef.current !== audio) return;

        if (!isFallback) {
          // If static audio fails, try fallback API endpoint
          playAudioSource(fallbackUrl, true);
        } else {
          console.warn("Failed to load audio preview from fallback endpoint.");
          if (audioRef.current === audio) {
            setLoadingVoice(null);
            setPlayingVoice(null);
            audioRef.current = null;
          }
          if (selectedProvider === "fish-audio") {
            setErrorMsg("لم نتمكن من تشغيل الصوت المعاين. يرجى التأكد من إضافة مفتاح FISH_AUDIO_API_KEY في ملف backend/.env للتوليد والاستماع.");
          } else {
            setErrorMsg("تعذر تشغيل العينة الصوتية لهذا الصوت حالياً.");
          }
        }
      };

      audio.play().catch((err) => {
        // Guard against race conditions when user switches voices rapidly
        if (audioRef.current !== audio) return;

        if (err.name === "AbortError") {
          return;
        }
        if (!isFallback) {
          playAudioSource(fallbackUrl, true);
        } else {
          console.warn("Audio play failed:", err);
          if (audioRef.current === audio) {
            setLoadingVoice(null);
            setPlayingVoice(null);
            audioRef.current = null;
          }
        }
      });
    };

    playAudioSource(staticSampleUrl, false);
  };

  const handleReset = () => {
    setIdea("");
    setDuration("5_min");
    setSelectedProvider("gemini");
    setSelectedVoice("Kore");
    setJobId(null);
    setStatusData(null);
    setErrorMsg(null);
    setScreen("input");
  };


  const handleSendFeedbackSubmit = async (e: React.FormEvent) => {
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

  // Icon Mapper for Domains
  const renderDomainIcon = (iconName: string) => {
    switch (iconName) {
      case "Compass": return <Compass className="w-6 h-6 text-purple-400" />;
      case "Landmark": return <Landmark className="w-6 h-6 text-amber-400" />;
      case "Radio": return <Radio className="w-6 h-6 text-indigo-400" />;
      case "Globe": return <Globe className="w-6 h-6 text-emerald-400" />;
      case "Flame": return <Flame className="w-6 h-6 text-rose-400" />;
      case "TrendingUp": return <TrendingUp className="w-6 h-6 text-cyan-400" />;
      case "Zap": return <Zap className="w-6 h-6 text-sky-400" />;
      default: return <Layers className="w-6 h-6 text-amber-400" />;
    }
  };

  // Current active provider voices
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
    <main className="min-h-screen bg-[#0a0a0a] text-[#f5f5f5] flex flex-col items-center justify-start p-4 md:p-8 font-sans selection:bg-amber-500/30" dir="rtl">
      
      {/* Background glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[40vh] bg-gradient-to-b from-amber-500/5 to-transparent blur-[120px] pointer-events-none" />

      {/* Brand Layout Header */}
      <div className="w-full max-w-5xl z-10 flex flex-col items-center">
        
        <header className="w-full mb-8 text-center flex flex-col items-center gap-3">
          <div className="flex items-center justify-between w-full border-b border-neutral-800 pb-4 mb-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-amber-500 to-rose-500 flex items-center justify-center font-bold text-black text-sm">
                iA
              </div>
              <span className="text-xl font-black bg-gradient-to-r from-amber-400 via-pink-500 to-rose-500 bg-clip-text text-transparent">
                imaginAI
              </span>
            </div>

            <div className="flex items-center gap-3">
              {activeProject && (
                <button
                  onClick={() => setScreen("dashboard")}
                  className="px-3 py-1.5 rounded-lg bg-[#171717] border border-neutral-800 text-xs font-semibold text-neutral-300 hover:border-amber-500/40 transition-colors flex items-center gap-2"
                >
                  <Layers className="w-3.5 h-3.5 text-amber-400" />
                  <span>المشاريع ({projectsList.length})</span>
                </button>
              )}
              <button
                onClick={handleStartNewProjectWizard}
                className="px-3.5 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-black text-xs font-bold transition-all shadow-lg shadow-amber-500/10 flex items-center gap-1.5"
              >
                <Plus className="w-4 h-4" />
                <span>مشروع جديد</span>
              </button>
            </div>
          </div>
        </header>

        {/* ── SCREEN 1: PROJECTS DASHBOARD ────────────────────────────────────── */}
        {screen === "dashboard" && (
          <div className="w-full max-w-4xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                  <Layers className="w-6 h-6 text-amber-400" />
                  لوحة تحكم المشاريع
                </h2>
                <p className="text-neutral-400 text-sm mt-1">
                  اختر مشروعاً سابقاً للمتابعة أو أنشئ مشروعاً جديداً للبدء
                </p>
              </div>
              <button
                onClick={handleStartNewProjectWizard}
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 text-black font-bold text-sm hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center gap-2"
              >
                <FolderPlus className="w-4 h-4" />
                <span>+ مشروع جديد</span>
              </button>
            </div>

            {loadingProjects ? (
              <div className="flex items-center justify-center py-20 text-neutral-400 gap-3">
                <Loader2 className="w-6 h-6 animate-spin text-amber-400" />
                <span>جاري تحميل المشاريع...</span>
              </div>
            ) : projectsList.length === 0 ? (
              <div className="bg-[#121212] border border-dashed border-neutral-800 rounded-2xl p-12 text-center flex flex-col items-center">
                <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center mb-4 text-amber-400">
                  <FolderPlus className="w-8 h-8" />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">لا يوجد أي مشروع بعد</h3>
                <p className="text-neutral-400 text-sm max-w-md mb-6">
                  ابدأ الآن بإنشاء مشروعك الأول باختيار المجال والنيتش المناسب للبدء في توليد الفيديوهات التلقائية.
                </p>
                <button
                  onClick={handleStartNewProjectWizard}
                  className="px-6 py-3 rounded-xl bg-amber-500 text-black font-bold text-sm hover:bg-amber-400 transition-all flex items-center gap-2 shadow-lg shadow-amber-500/20"
                >
                  <Plus className="w-5 h-5" />
                  <span>إنشاء أول مشروع</span>
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                {projectsList.map((proj) => (
                  <div
                    key={proj.project_id}
                    onClick={() => handleSelectActiveProject(proj)}
                    className={`cursor-pointer p-5 rounded-2xl border transition-all relative overflow-hidden group ${
                      activeProject?.project_id === proj.project_id
                        ? "bg-[#1c1917] border-amber-500/60 shadow-lg shadow-amber-500/10"
                        : "bg-[#121212] border-neutral-800 hover:border-neutral-700 hover:bg-[#171717]"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 rounded-full inline-block mb-1.5">
                          النيتش: {proj.niche}
                        </span>
                        <h3 className="text-lg font-bold text-white group-hover:text-amber-400 transition-colors">
                          {proj.name}
                        </h3>
                      </div>
                      <ChevronLeft className="w-5 h-5 text-neutral-500 group-hover:text-amber-400 transition-colors" />
                    </div>

                    <div className="flex items-center gap-4 text-xs text-neutral-400 pt-3 border-t border-neutral-800/80">
                      <span className="flex items-center gap-1.5">
                        <Video className="w-3.5 h-3.5 text-neutral-500" />
                        {proj.video_count || 0} فيديو مسجّل
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-neutral-500" />
                        {new Date(proj.created_at).toLocaleDateString("ar-EG")}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Saved Videos for Active Project */}
            {activeProject && (
              <div className="mt-8 pt-8 border-t border-neutral-800">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <Video className="w-5 h-5 text-amber-400" />
                    فيديوهات مشروع "{activeProject.name}" المسجلة
                  </h3>
                  <button
                    onClick={() => setScreen("input")}
                    className="px-4 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold hover:bg-amber-500/20 transition-all flex items-center gap-1.5"
                  >
                    <Plus className="w-4 h-4" />
                    <span>إنشاء فيديو جديد لهذا المشروع</span>
                  </button>
                </div>

                {activeProjectVideos.length === 0 ? (
                  <div className="bg-[#121212] border border-neutral-800/80 rounded-xl p-8 text-center text-neutral-400 text-sm">
                    لا يوجد أي فيديو مكتمل مسجّل لهذا المشروع بعد.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {activeProjectVideos.map((vid) => (
                      <div key={vid.video_id} className="bg-[#121212] border border-neutral-800 rounded-xl p-4 flex flex-col gap-3">
                        <div className="aspect-video w-full bg-black rounded-lg overflow-hidden relative">
                          <video
                            controls
                            src={getVideoStreamUrl(vid.video_id)}
                            className="w-full h-full object-cover"
                          />
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-white truncate max-w-[200px]">
                            {vid.title || "فيديو بدون عنوان"}
                          </span>
                          <a
                            href={getVideoStreamUrl(vid.video_id)}
                            download={`imaginai_${vid.video_id}.mp4`}
                            className="px-3 py-1 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-200 text-xs font-medium flex items-center gap-1.5 transition-colors"
                          >
                            <Download className="w-3.5 h-3.5" />
                            <span>تحميل</span>
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── WIZARD STEP 1: ENTER PROJECT NAME ─────────────────────────────── */}
        {screen === "wizard_step1" && (
          <div className="w-full max-w-md animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-[#121212] border border-neutral-800 rounded-2xl p-6 shadow-2xl">
              <div className="flex items-center gap-2 text-xs font-bold text-amber-400 mb-3">
                <span className="w-5 h-5 rounded-full bg-amber-500/20 flex items-center justify-center text-[10px]">1</span>
                <span>الخطوة الأولى من 3: اسم المشروع</span>
              </div>
              <h2 className="text-xl font-bold text-white mb-2">ما اسم مشروعك الجديد؟</h2>
              <p className="text-neutral-400 text-xs mb-6">
                أدخل اسماً مميزاً لمساعدتك على تنظيم وفلترة الفيديوهات في لوحة التحكم.
              </p>

              <form onSubmit={handleStep1Submit} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-neutral-300 mb-2">اسم المشروع:</label>
                  <input
                    type="text"
                    required
                    placeholder="مثال: قناة تاريخ العالم، قصص الرعب الغامضة..."
                    value={projectNameInput}
                    onChange={(e) => setProjectNameInput(e.target.value)}
                    className="w-full bg-[#1c1c1c] border border-neutral-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-amber-500 transition-colors"
                  />
                </div>

                <div className="flex items-center justify-between pt-4">
                  <button
                    type="button"
                    onClick={() => setScreen("dashboard")}
                    className="px-4 py-2 rounded-xl text-xs text-neutral-400 hover:text-white transition-colors"
                  >
                    إلغاء
                  </button>
                  <button
                    type="submit"
                    disabled={!projectNameInput.trim()}
                    className="px-6 py-2.5 rounded-xl bg-amber-500 text-black font-bold text-xs hover:bg-amber-400 disabled:opacity-50 transition-all flex items-center gap-1.5"
                  >
                    <span>التالي: اختيار المجال</span>
                    <ArrowRight className="w-4 h-4 rotate-180" />
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ── WIZARD STEP 2: SELECT DOMAIN (EXACTLY 7 CARDS ONLY) ───────────── */}
        {screen === "wizard_step2" && (
          <div className="w-full max-w-4xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="text-center mb-6">
              <div className="inline-flex items-center gap-2 text-xs font-bold text-amber-400 bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20 mb-2">
                <span>الخطوة الثانية من 3</span>
              </div>
              <h2 className="text-2xl font-bold text-white">اختر المجال الرئيسي للمشروع</h2>
              <p className="text-neutral-400 text-xs mt-1">
                المشروع: <span className="text-amber-400 font-bold">{projectNameInput}</span>
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              {domainsCatalog.map((dom) => (
                <div
                  key={dom.id}
                  onClick={() => handleSelectDomain(dom)}
                  className={`cursor-pointer p-5 rounded-2xl border bg-gradient-to-b ${dom.color} hover:border-amber-500/60 hover:scale-[1.02] transition-all flex flex-col justify-between group shadow-xl`}
                >
                  <div>
                    <div className="mb-3 flex items-center justify-between">
                      <div className="p-2.5 rounded-xl bg-black/40 border border-white/10">
                        {renderDomainIcon(dom.icon)}
                      </div>
                      <span className="text-[10px] font-bold text-neutral-400 bg-black/40 px-2 py-0.5 rounded-full">
                        {dom.sub_niches.length} نيتشات
                      </span>
                    </div>
                    <h3 className="text-lg font-extrabold text-white group-hover:text-amber-400 transition-colors mb-1">
                      {dom.title}
                    </h3>
                  </div>
                  <div className="pt-4 border-t border-white/5 flex items-center justify-end text-xs text-amber-400 font-bold gap-1">
                    <span>اختر هذا المجال</span>
                    <ArrowRight className="w-3.5 h-3.5 rotate-180" />
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-start">
              <button
                onClick={() => setScreen("wizard_step1")}
                className="px-4 py-2 rounded-xl text-xs text-neutral-400 hover:text-white transition-colors"
              >
                ← العودة لاسم المشروع
              </button>
            </div>
          </div>
        )}

        {/* ── WIZARD STEP 3: SELECT SUB-NICHE (CUSTOM AT VERY END) ───────────── */}
        {screen === "wizard_step3" && selectedDomain && (
          <div className="w-full max-w-3xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="text-center mb-6">
              <div className="inline-flex items-center gap-2 text-xs font-bold text-amber-400 bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20 mb-2">
                <span>الخطوة الثالثة والأخيرة</span>
              </div>
              <h2 className="text-2xl font-bold text-white">اختر النيتش الفرعي لمجال "{selectedDomain.title}"</h2>
              <p className="text-neutral-400 text-xs mt-1">
                سيُربط هذا النيتش تلقائياً بالمشروع لتعيين نمط الموسيقى والسكريبت والمونتاج
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
              {/* Preserved Preset Sub-Niches */}
              {selectedDomain.sub_niches.map((sn) => (
                <div
                  key={sn.id}
                  onClick={() => {
                    setSelectedNiche(sn);
                    setIsCustomNicheActive(false);
                  }}
                  className={`cursor-pointer p-4 rounded-xl border transition-all ${
                    selectedNiche?.id === sn.id && !isCustomNicheActive
                      ? "bg-amber-500/10 border-amber-500 text-white shadow-lg shadow-amber-500/10"
                      : "bg-[#121212] border-neutral-800 text-neutral-300 hover:border-neutral-700 hover:bg-[#171717]"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="font-bold text-sm text-white">{sn.title}</h4>
                    {selectedNiche?.id === sn.id && !isCustomNicheActive && (
                      <CheckCircle2 className="w-4 h-4 text-amber-400" />
                    )}
                  </div>
                  <p className="text-xs text-neutral-400 leading-relaxed">{sn.desc}</p>
                </div>
              ))}

              {/* STRICT REQUIREMENT: Custom Niche Option AT THE VERY END OF THE LIST */}
              <div
                onClick={() => {
                  setIsCustomNicheActive(true);
                  setSelectedNiche(null);
                }}
                className={`cursor-pointer p-4 rounded-xl border transition-all col-span-1 md:col-span-2 ${
                  isCustomNicheActive
                    ? "bg-purple-950/20 border-purple-500 text-white shadow-lg shadow-purple-500/10"
                    : "bg-[#121212] border-neutral-800 text-neutral-400 hover:border-neutral-700 hover:bg-[#171717]"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <h4 className="font-bold text-sm text-purple-300 flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-purple-400" />
                    نيتش مخصص (خيار إضافي)
                  </h4>
                  {isCustomNicheActive && <CheckCircle2 className="w-4 h-4 text-purple-400" />}
                </div>
                <p className="text-xs text-neutral-400 mb-3">
                  اكتب نيتش خاصاً إذا لم تجد التخصص الفرعي المطلوب ضمن القائمة المحددة أعلاه.
                </p>

                {isCustomNicheActive && (
                  <input
                    type="text"
                    placeholder="اكتب اسم النيتش المخصص هنا..."
                    value={customNicheText}
                    onChange={(e) => setCustomNicheText(e.target.value)}
                    className="w-full bg-[#1c1c1c] border border-purple-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500"
                    onClick={(e) => e.stopPropagation()}
                  />
                )}
              </div>
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-neutral-800">
              <button
                onClick={() => setScreen("wizard_step2")}
                className="px-4 py-2 rounded-xl text-xs text-neutral-400 hover:text-white transition-colors"
              >
                ← العودة لاختيار المجال
              </button>
              <button
                onClick={handleCreateProjectFinal}
                disabled={creatingProject || (!selectedNiche && (!isCustomNicheActive || !customNicheText.trim()))}
                className="px-6 py-3 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 text-black font-bold text-xs hover:opacity-90 disabled:opacity-50 transition-all flex items-center gap-2 shadow-lg shadow-amber-500/20"
              >
                {creatingProject ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>جاري حفظ المشروع...</span>
                  </>
                ) : (
                  <>
                    <span>إنشاء المشروع والبدء 🚀</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ── SCREEN 4: CREATION INPUT SCREEN (AUTO-REFLECTING NICHE) ────────── */}
        {screen === "input" && activeProject && (
          <div className="w-full max-w-2xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            {/* Active Project Banner */}
            <div className="bg-[#121212] border border-neutral-800 rounded-xl p-4 mb-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 font-bold">
                  <Video className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-white text-base">{activeProject.name}</h3>
                    <span className="text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-full">
                      {activeProject.niche}
                    </span>
                  </div>
                  <p className="text-xs text-neutral-400 mt-0.5">
                    المجال: {activeProject.domain}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setScreen("dashboard")}
                className="text-xs text-neutral-400 hover:text-white transition-colors"
              >
                تغيير المشروع
              </button>
            </div>

            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold tracking-tight text-[#f5f5f5]">
                صناعة فيديو لـ "{activeProject.name}"
              </h2>
              <p className="text-neutral-400 mt-1 text-xs">
                اكتب موضوع الفيديو وسيتم إنشاؤه تلقائياً استناداً لمواصفات نيتش المشروع
              </p>
            </div>

            <form onSubmit={handleProceedToVoice} className="space-y-6">
              {/* Segmented Control Toggle */}
              <div className="flex items-center bg-[#171717] p-1 rounded-xl border border-neutral-800">
                <button
                  type="button"
                  onClick={() => setInputMode("ai_generated")}
                  className={`flex-1 py-2.5 rounded-lg text-xs font-extrabold transition-all flex items-center justify-center gap-2 ${
                    inputMode === "ai_generated"
                      ? "bg-amber-500 text-black shadow-lg shadow-amber-500/20"
                      : "text-neutral-400 hover:text-white"
                  }`}
                >
                  <Sparkles className="w-4 h-4" />
                  <span>توليد بالذكاء الاصطناعي</span>
                </button>
                <button
                  type="button"
                  onClick={() => setInputMode("script_provided")}
                  className={`flex-1 py-2.5 rounded-lg text-xs font-extrabold transition-all flex items-center justify-center gap-2 ${
                    inputMode === "script_provided"
                      ? "bg-amber-500 text-black shadow-lg shadow-amber-500/20"
                      : "text-neutral-400 hover:text-white"
                  }`}
                >
                  <FileText className="w-4 h-4" />
                  <span>لدي سكريبت جاهز</span>
                </button>
              </div>

              {/* Style, Music, and Caption Customization controls */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-[#121212] border border-neutral-800 rounded-xl p-3.5">
                  <span className="text-xs text-neutral-400 block mb-1">الأسلوب المعتمد تلقائياً:</span>
                  <div className="flex items-center gap-2 text-sm font-bold text-amber-400">
                    <Compass className="w-4 h-4" />
                    <span>{activeProject.niche}</span>
                  </div>
                </div>

                <div className="bg-[#121212] border border-neutral-800 rounded-xl p-3.5">
                  <span className="text-xs text-neutral-400 block mb-1">نمط الموسيقى التلقائي:</span>
                  <div className="flex items-center gap-2 text-sm font-bold text-emerald-400">
                    <Volume2 className="w-4 h-4" />
                    <span>{selectedMusic}</span>
                  </div>
                </div>

                <div 
                  onClick={() => {
                    setTempCaptionConfig(captionConfig);
                    setIsCaptionModalOpen(true);
                  }}
                  className="cursor-pointer bg-[#121212] border border-amber-500/30 hover:border-amber-500 rounded-xl p-3.5 transition-all flex items-center justify-between group shadow-lg shadow-amber-500/5"
                >
                  <div>
                    <span className="text-xs text-neutral-400 block mb-1">شكل الترجمة والكابشن:</span>
                    <div className="flex items-center gap-2 text-sm font-bold text-amber-400">
                      <Subtitles className="w-4 h-4" />
                      <span>{captionConfig.font} • {captionConfig.position}</span>
                    </div>
                  </div>
                  <span className="text-[11px] font-extrabold bg-amber-500/20 text-amber-400 px-2.5 py-1 rounded-lg group-hover:bg-amber-500 group-hover:text-black transition-all flex items-center gap-1">
                    <span>💬 تخصيص</span>
                  </span>
                </div>
              </div>

              {/* AI GENERATED MODE INPUTS */}
              {inputMode === "ai_generated" ? (
                <>
                  {/* Idea Prompt Input */}
                  <div className="bg-[#121212] border border-neutral-800 rounded-xl p-4">
                    <label className="block text-xs font-bold text-neutral-300 mb-2">
                      موضوع الفكرة أو السكريبت المطلوب:
                    </label>
                    <textarea
                      required
                      rows={4}
                      placeholder="اكتب فكرتك بالتفصيل هنا (مثال: أسرار بناء الأهرامات، قصة اختفاء سفينة ماري سيليست الغامضة...)"
                      value={idea}
                      onChange={(e) => setIdea(e.target.value)}
                      className="w-full bg-[#1c1c1c] border border-neutral-700 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-amber-500 transition-colors"
                    />
                  </div>

                  {/* Optional Context Accordion */}
                  <div className="bg-[#121212] border border-neutral-800 rounded-xl overflow-hidden transition-all">
                    <button
                      type="button"
                      onClick={() => setIsContextOpen(!isContextOpen)}
                      className="w-full p-3.5 flex items-center justify-between text-right hover:bg-[#171717] transition-colors"
                    >
                      <div className="flex items-center gap-2 text-xs font-bold text-neutral-300">
                        <Sparkles className="w-4 h-4 text-amber-400" />
                        <span>إضافة تفاصيل / نقاط تركيز للموديل (اختياري)</span>
                      </div>
                      <span className="text-xs text-amber-400 font-bold">
                        {isContextOpen ? "▲ إغلاق" : "+ إضافة تفاصيل"}
                      </span>
                    </button>
                    {isContextOpen && (
                      <div className="p-4 pt-1 border-t border-neutral-800/50">
                        <p className="text-[11px] text-neutral-400 mb-2">
                          اكتب هنا أي معلومات محددة، تواريخ، أو نقاط دقيقة ترغب أن يلتزم بها الذكاء الاصطناعي أثناء كتابة السكريبت.
                        </p>
                        <textarea
                          rows={3}
                          placeholder="معلومات أو نقاط تريد أن يركز عليها الفيديو (اختياري)..."
                          value={additionalContext}
                          onChange={(e) => setAdditionalContext(e.target.value)}
                          className="w-full bg-[#1c1c1c] border border-neutral-700 rounded-lg p-3 text-xs text-white focus:outline-none focus:border-amber-500 transition-colors"
                        />
                      </div>
                    )}
                  </div>

                  {/* Video Length Selection */}
                  <div className="bg-[#121212] border border-neutral-800 rounded-xl p-4">
                    <label className="block text-xs font-bold text-neutral-300 mb-3">مدة الفيديو المستهدفة:</label>
                    <div className="grid grid-cols-4 gap-2">
                      {[
                        { id: "5_min", label: "5 دقائق" },
                        { id: "8_min", label: "8 دقائق" },
                        { id: "10_min", label: "10 دقائق" },
                        { id: "15_min", label: "15 دقيقة" },
                      ].map((d) => (
                        <button
                          key={d.id}
                          type="button"
                          onClick={() => setDuration(d.id as any)}
                          className={`py-2 rounded-lg text-xs font-bold transition-all border ${
                            duration === d.id
                              ? "bg-amber-500/20 border-amber-500 text-amber-400"
                              : "bg-[#1a1a1a] border-neutral-800 text-neutral-400 hover:border-neutral-700"
                          }`}
                        >
                          {d.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                /* SCRIPT PROVIDED MODE INPUT */
                <div className="bg-[#121212] border border-neutral-800 rounded-xl p-4">
                  <label className="block text-xs font-bold text-neutral-300 mb-2">
                    نص السكريبت الكامل (سيتم تخطي توليد الذكاء الاصطناعي):
                  </label>
                  <textarea
                    required
                    rows={8}
                    placeholder="الصق سكريبتك الكامل هنا... (يفضل الفصل بين المشاهد والفقرات بأسطر فارغة)"
                    value={providedScript}
                    onChange={(e) => setProvidedScript(e.target.value)}
                    className="w-full bg-[#1c1c1c] border border-neutral-700 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-amber-500 transition-colors leading-relaxed"
                  />

                  {/* Live Word Count & Estimated Duration Calculator */}
                  <div className="mt-3 flex items-center justify-between bg-[#181818] border border-neutral-800 rounded-lg px-3.5 py-2.5 text-xs text-neutral-400">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-amber-400" />
                      <span>عدد الكلمات: <strong className="text-white">{providedScript.trim() ? providedScript.trim().split(/\s+/).length : 0}</strong> كلمة</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-amber-400" />
                      <span>المدة التقديرية: <strong className="text-amber-400">
                        {providedScript.trim()
                          ? (providedScript.trim().split(/\s+/).length / 150 < 1
                              ? `~${Math.round((providedScript.trim().split(/\s+/).length / 150) * 60)} ثانية`
                              : `~${(providedScript.trim().split(/\s+/).length / 150).toFixed(1)} دقيقة`)
                          : "0 دقيقة"}
                      </strong></span>
                    </div>
                  </div>
                </div>
              )}

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  disabled={inputMode === "ai_generated" ? !idea.trim() : !providedScript.trim()}
                  className="w-full py-3.5 rounded-xl bg-gradient-to-r from-amber-500 via-rose-500 to-pink-500 text-black font-extrabold text-sm hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
                >
                  <span>التالي: اختيار الراوي الصوتي</span>
                  <ArrowRight className="w-4 h-4 rotate-180" />
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── SCREEN 5: VOICE SELECTION SCREEN ─────────────────────────────── */}
        {screen === "voice" && (
          <div className="w-full max-w-2xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-white">اختر صوت الراوي</h2>
                <p className="text-neutral-400 text-xs mt-0.5">استمع للنماذج الصوتية واختر الصوت الأنسب لنبرة قصتك</p>
              </div>
              <button
                onClick={() => setScreen("input")}
                className="text-xs text-neutral-400 hover:text-white transition-colors"
              >
                ← العودة للتعديل
              </button>
            </div>

            {/* Segmented Control Provider Tabs */}
            <div className="bg-[#121212] p-1.5 rounded-2xl border border-neutral-800 flex items-center gap-2 mb-6 shadow-inner">
              {providersCatalog.map((prov, idx) => {
                const isActive = selectedProvider === prov.provider;
                return (
                  <button
                    key={`${prov.provider}-${idx}`}
                    type="button"
                    onClick={() => {
                      if (audioRef.current) {
                        const prevAudio = audioRef.current;
                        prevAudio.onplay = null;
                        prevAudio.onended = null;
                        prevAudio.onerror = null;
                        try {
                          prevAudio.pause();
                          prevAudio.currentTime = 0;
                        } catch (_) {}
                        audioRef.current = null;
                      }
                      setPlayingVoice(null);
                      setLoadingVoice(null);
                      setSelectedProvider(prov.provider);
                      if (prov.voices && prov.voices.length > 0) {
                        setSelectedVoice(prov.voices[0].id);
                      }
                    }}
                    className={`flex-1 py-3 px-4 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 ${
                      isActive
                        ? "bg-amber-500 text-black shadow-lg shadow-amber-500/20"
                        : "text-neutral-400 hover:text-white hover:bg-neutral-800/50"
                    }`}
                  >
                    <span>{prov.provider === "gemini" ? "✨" : "🐟"}</span>
                    <span>{prov.provider_name}</span>
                  </button>
                );
              })}
            </div>

            {/* Provider Description & Clone Voice Button */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-4">
              {providersCatalog.find((p) => p.provider === selectedProvider)?.desc && (
                <p className="text-xs text-neutral-400 bg-[#121212] border border-neutral-800/80 px-4 py-2.5 rounded-xl flex-1">
                  💡 {providersCatalog.find((p) => p.provider === selectedProvider)?.desc}
                </p>
              )}

              {selectedProvider === "fish-audio" && (
                <button
                  type="button"
                  onClick={() => setIsCloningOpen(true)}
                  className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-bold text-xs hover:opacity-90 transition-all flex items-center justify-center gap-2 shadow-lg shadow-cyan-500/20 shrink-0"
                >
                  <Mic className="w-4 h-4" />
                  <span>🎙️ استنسخ صوتك بصوتك الخالص</span>
                </button>
              )}
            </div>

            {/* Voices List */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
              {currentVoices.map((v) => {
                const voiceKey = `${selectedProvider}:${v.id}`;
                const isSelected = selectedVoice === v.id;
                const isPlaying = playingVoice === voiceKey;
                const isLoading = loadingVoice === voiceKey;

                return (
                  <div
                    key={v.id}
                    onClick={() => setSelectedVoice(v.id)}
                    className={`cursor-pointer p-4 rounded-2xl border transition-all flex flex-col justify-between relative overflow-hidden group ${
                      isSelected
                        ? "bg-amber-500/10 border-amber-500 text-white ring-1 ring-amber-500/30 shadow-lg shadow-amber-500/5"
                        : "bg-[#121212] border-neutral-800/90 text-neutral-300 hover:border-neutral-700 hover:bg-[#161616]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            togglePlaySample(v);
                          }}
                          className={`w-10 h-10 rounded-full flex items-center justify-center border transition-all shrink-0 ${
                            isPlaying
                              ? "bg-amber-500 text-black border-amber-400 scale-105 shadow-md shadow-amber-500/30"
                              : "bg-neutral-800/90 border-neutral-700 text-white hover:border-amber-400 hover:scale-105"
                          }`}
                          title="استماع للنموذج الصوتي"
                        >
                          {isLoading ? (
                            <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                          ) : isPlaying ? (
                            <Pause className="w-4 h-4" />
                          ) : (
                            <Play className="w-4 h-4 fill-current ml-0.5" />
                          )}
                        </button>
                        <div>
                          <span className="font-bold text-sm text-white block">{v.name}</span>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span className="text-[10px] bg-neutral-800 text-neutral-400 px-2 py-0.5 rounded-md font-mono">
                              {v.lang}
                            </span>
                            <span className="text-[10px] bg-neutral-800/80 text-neutral-400 px-2 py-0.5 rounded-md">
                              {v.gender === "male" ? "👨 ذكوري" : v.gender === "female" ? "👩 أنثوي" : "🎙️ محايد"}
                            </span>
                          </div>
                        </div>
                      </div>

                      {isSelected && (
                        <div className="bg-amber-500/20 text-amber-400 p-1 rounded-full border border-amber-500/30">
                          <CheckCircle2 className="w-4 h-4 text-amber-400" />
                        </div>
                      )}
                    </div>

                    <p className="text-xs text-neutral-400 leading-relaxed">{v.desc}</p>
                  </div>
                );
              })}
            </div>


            <div className="flex items-center justify-between pt-4 border-t border-neutral-800">
              <button
                onClick={() => setScreen("input")}
                className="px-4 py-2 rounded-xl text-xs text-neutral-400 hover:text-white"
              >
                ← تراجع
              </button>
              <button
                onClick={handleStartGeneration}
                className="px-8 py-3.5 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 text-black font-extrabold text-sm hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center gap-2"
              >
                <span>بدء إنشاء ورندر الفيديو 🎬</span>
              </button>
            </div>
          </div>
        )}

        {/* ── SCREEN 6: PROGRESS SCREEN ─────────────────────────────────────── */}
        {screen === "progress" && (
          <div className="w-full max-w-md animate-in fade-in zoom-in-95 duration-500 text-center">
            <div className="bg-[#121212] border border-neutral-800 rounded-2xl p-8 shadow-2xl flex flex-col items-center">
              <Loader2 className="w-12 h-12 text-amber-400 animate-spin mb-4" />
              <h2 className="text-xl font-bold text-white mb-1">جاري إنشاء وتجميع الفيديو...</h2>
              <p className="text-xs text-neutral-400 mb-6">قد تستغرق هذه العملية دقيقة إلى دقيقتين حسب طول الفيديو</p>

              {/* Stage Stepper */}
              <div className="w-full space-y-3 mb-6 text-right">
                {stages.map((st) => {
                  const stageState = statusData?.stages?.[st.key as keyof typeof statusData.stages] || "pending";
                  const isDone = stageState === "done";
                  const isProcessing = stageState === "processing";

                  return (
                    <div
                      key={st.key}
                      className={`p-3 rounded-xl border flex items-center justify-between text-xs font-semibold transition-all ${
                        isDone
                          ? "bg-emerald-950/20 border-emerald-500/40 text-emerald-400"
                          : isProcessing
                          ? "bg-amber-500/10 border-amber-500 text-amber-400 animate-pulse"
                          : "bg-neutral-900 border-neutral-800 text-neutral-500"
                      }`}
                    >
                      <span>{st.label}</span>
                      {isDone ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : isProcessing ? (
                        <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
                      ) : (
                        <span className="w-2 h-2 rounded-full bg-neutral-700" />
                      )}
                    </div>
                  );
                })}
              </div>

              {errorMsg && (
                <div className="bg-rose-950/30 border border-rose-800 text-rose-300 p-4 rounded-xl text-xs text-right mb-4">
                  <div className="flex items-center gap-2 font-bold mb-1">
                    <AlertCircle className="w-4 h-4 text-rose-400" />
                    <span>حدث خطأ أثناء المعالجة:</span>
                  </div>
                  <p>{errorMsg}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── SCREEN 6.5: REVIEW & EDIT SCREEN ──────────────────────────────── */}
        {screen === "review" && reviewData && (
          <div className="w-full max-w-4xl animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-[#121212] border border-neutral-800 rounded-2xl p-6 shadow-2xl space-y-6 text-right">
              {/* Header */}
              <div className="border-b border-neutral-800 pb-4">
                <div className="inline-flex items-center gap-2 text-amber-400 bg-amber-950/40 border border-amber-800/40 px-3 py-1 rounded-full text-xs font-bold mb-2">
                  <FileText className="w-4 h-4" />
                  <span>مرحلة التعديل والمراجعة قبل الرندر النهائي 🎬</span>
                </div>
                <h2 className="text-2xl font-extrabold text-white">مراجعة سكريبت ولقطات المشاهد</h2>
                <p className="text-xs text-neutral-400 mt-1">
                  قم بمراجعة نصوص التعليق الصوتي لكل مشهد أو تعديلها. سيتم فقط إعادة توليد الصوت (TTS) للمشاهد التي تقوم بتعديلها لتوفير حصة الاستخدام.
                </p>
              </div>

              {/* Scenes List */}
              <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
                {reviewData.scenes.map((sc) => {
                  const currentText = editedScenesMap[sc.scene_index] ?? sc.narration;
                  const isModified = currentText.trim() !== (sc.narration || "").trim();

                  return (
                    <div
                      key={sc.scene_index}
                      className={`bg-[#181818] border rounded-2xl p-4 transition-all ${
                        isModified ? "border-amber-500/50 bg-amber-950/10" : "border-neutral-800"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-3 border-b border-neutral-800/60 pb-2">
                        <div className="flex items-center gap-2">
                          <span className="w-6 h-6 rounded-full bg-amber-500/20 text-amber-400 text-xs font-extrabold flex items-center justify-center">
                            {sc.scene_index + 1}
                          </span>
                          <span className="font-bold text-sm text-white">المشهد رقم {sc.scene_index + 1}</span>
                          {isModified && (
                            <span className="text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full font-bold">
                              تم التعديل ✍️
                            </span>
                          )}
                        </div>
                        <span className="text-xs text-neutral-400 font-mono bg-neutral-900 px-2.5 py-1 rounded-lg">
                          ⏳ {sc.audio_duration ? sc.audio_duration.toFixed(1) : "5.0"} ثانية
                        </span>
                      </div>

                      {/* Narration Textarea */}
                      <div className="mb-4">
                        <label className="block text-xs font-bold text-neutral-300 mb-1.5">نص التعليق الصوتي للمشهد:</label>
                        <textarea
                          rows={3}
                          value={currentText}
                          onChange={(e) =>
                            setEditedScenesMap((prev) => ({ ...prev, [sc.scene_index]: e.target.value }))
                          }
                          className="w-full bg-[#121212] border border-neutral-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-amber-500 transition-colors leading-relaxed"
                          placeholder="اكتب التعليق الصوتي لهذا المشهد..."
                        />
                      </div>

                      {/* Shots Preview */}
                      {sc.shots && sc.shots.length > 0 && (
                        <div>
                          <label className="block text-xs font-bold text-neutral-400 mb-2">
                            اللقطات المصدرية للمشهد ({sc.shots.length} لقطة):
                          </label>
                          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                            {sc.shots.map((shot) => (
                              <div key={shot.shot_index} className="relative group rounded-xl overflow-hidden border border-neutral-800 bg-black">
                                <video
                                  src={shot.stream_url}
                                  controls
                                  className="w-full aspect-video object-cover"
                                />
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Error Message */}
              {reviewError && (
                <div className="bg-rose-950/30 border border-rose-800 text-rose-300 p-3 rounded-xl text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{reviewError}</span>
                </div>
              )}

              {/* Footer Controls */}
              <div className="border-t border-neutral-800 pt-4 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setScreen("input")}
                  className="px-4 py-2.5 rounded-xl text-xs text-neutral-400 hover:text-white"
                >
                  إلغاء وإعادة الإنشاء
                </button>
                <button
                  type="button"
                  onClick={handleResumeSubmit}
                  disabled={resumingJob}
                  className="px-8 py-3.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 text-black font-extrabold text-sm hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-amber-500/20 flex items-center gap-2"
                >
                  {resumingJob ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>جاري المعالجة ورندر الفيديو النهائي...</span>
                    </>
                  ) : (
                    <>
                      <Zap className="w-4 h-4 fill-current" />
                      <span>اعتماد التعديلات ورندر الفيديو النهائي 🚀</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── SCREEN 7: RESULT SCREEN (WITH DB SAVED VIDEO PLAYER) ──────────── */}
        {screen === "result" && jobId && (
          <div className="w-full max-w-2xl animate-in fade-in slide-in-from-bottom-4 duration-500 text-center">
            <div className="bg-[#121212] border border-neutral-800 rounded-2xl p-6 shadow-2xl">
              <div className="inline-flex items-center gap-2 text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-3 py-1 rounded-full text-xs font-bold mb-4">
                <CheckCircle2 className="w-4 h-4" />
                <span>تم اكتمال وحفظ الفيديو بنجاح!</span>
              </div>
              <h2 className="text-2xl font-extrabold text-white mb-4">الفيديو الخاص بك جاهز للعرض</h2>

              {/* Video Player */}
              <div className="aspect-video w-full bg-black rounded-xl overflow-hidden mb-6 border border-neutral-800 shadow-2xl">
                <video
                  controls
                  autoPlay
                  src={getVideoStreamUrl(jobId)}
                  className="w-full h-full object-cover"
                />
              </div>

              <div className="flex items-center justify-center gap-4">
                <a
                  href={getDownloadUrl(jobId)}
                  download={`imaginai_${jobId}.mp4`}
                  className="px-6 py-3 rounded-xl bg-amber-500 text-black font-extrabold text-xs hover:bg-amber-400 transition-all shadow-lg shadow-amber-500/20 flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  <span>تحميل الفيديو (MP4)</span>
                </a>
                <button
                  onClick={() => setScreen("dashboard")}
                  className="px-6 py-3 rounded-xl bg-neutral-800 text-white font-bold text-xs hover:bg-neutral-700 transition-all flex items-center gap-2"
                >
                  <Layers className="w-4 h-4" />
                  <span>العودة للمشاريع</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── CAPTION CUSTOMIZATION MODAL (FREE COLOR PICKER & CAPCUT EFFECTS) ─ */}
        {isCaptionModalOpen && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200">
            <div className="bg-[#121212] border border-neutral-800 rounded-2xl w-full max-w-4xl p-6 shadow-2xl space-y-6 relative max-h-[90vh] overflow-y-auto">
              {/* Modal Header */}
              <div className="flex items-center justify-between border-b border-neutral-800 pb-4">
                <div className="flex items-center gap-2 text-amber-400 font-extrabold text-lg">
                  <Subtitles className="w-5 h-5" />
                  <h3>تخصيص الكابشن والمؤثرات البصرية</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsCaptionModalOpen(false)}
                  className="p-1 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* ── LEFT: LIVE 16:9 VIDEO PREVIEW ───────────────────── */}
                <div className="flex flex-col gap-2">
                  <span className="text-xs font-bold text-neutral-300">معاينة حية لشكل الفيديو (16:9):</span>
                  <div className="aspect-video w-full rounded-2xl bg-gradient-to-br from-neutral-900 via-black to-neutral-950 border border-neutral-800 relative overflow-hidden flex items-center justify-center p-6 shadow-2xl">
                    <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f1f1f15_1px,transparent_1px),linear-gradient(to_bottom,#1f1f1f15_1px,transparent_1px)] bg-[size:2rem_2rem] opacity-40 pointer-events-none" />

                    {/* Subtitle Display */}
                    <div
                      style={{
                        fontFamily:
                          tempCaptionConfig.font === "Cairo"
                            ? "var(--font-cairo), sans-serif"
                            : tempCaptionConfig.font === "Almarai"
                            ? "var(--font-almarai), sans-serif"
                            : "var(--font-plus-jakarta), sans-serif",
                        fontSize: `${(1.1 * (tempCaptionConfig.size_percent / 100)).toFixed(2)}rem`,
                        alignSelf:
                          tempCaptionConfig.position === "top"
                            ? "flex-start"
                            : tempCaptionConfig.position === "middle"
                            ? "center"
                            : "flex-end",
                        marginTop: tempCaptionConfig.position === "top" ? "1rem" : undefined,
                        marginBottom: tempCaptionConfig.position === "bottom" ? "1rem" : undefined,
                        textShadow:
                          tempCaptionConfig.effect === "shadow"
                            ? "2px 2px 8px rgba(0,0,0,0.95), 0px 0px 4px rgba(0,0,0,0.9)"
                            : tempCaptionConfig.effect === "outline"
                            ? "-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000"
                            : "none",
                        backgroundColor:
                          tempCaptionConfig.effect === "box"
                            ? "rgba(0, 0, 0, 0.75)"
                            : "transparent",
                        padding: tempCaptionConfig.effect === "box" ? "0.4rem 1rem" : "0.25rem 0.5rem",
                        borderRadius: "8px",
                        fontWeight: 700,
                        textAlign: "center",
                        lineHeight: 1.4,
                      }}
                      className="z-10 transition-all duration-150 select-none max-w-[90%] flex flex-wrap items-center justify-center gap-1.5"
                    >
                      {tempCaptionConfig.effect === "karaoke" ? (
                        <>
                          <span style={{ color: tempCaptionConfig.color }}>هذا</span>
                          <span style={{ color: tempCaptionConfig.color }}>مثال</span>
                          <span style={{ color: tempCaptionConfig.highlight_color, textDecoration: "underline" }}>لكاريوكي</span>
                          <span style={{ color: tempCaptionConfig.color }}>الترجمة</span>
                        </>
                      ) : tempCaptionConfig.effect === "pop" ? (
                        <>
                          <span style={{ color: tempCaptionConfig.color }}>هذا</span>
                          <span 
                            style={{ 
                              color: tempCaptionConfig.highlight_color,
                              transform: "scale(1.25)",
                              display: "inline-block",
                              transition: "all 0.2s"
                            }} 
                            className="font-extrabold"
                          >
                            مؤثر POP 💥
                          </span>
                          <span style={{ color: tempCaptionConfig.color }}>الرهيب</span>
                        </>
                      ) : (
                        <span style={{ color: tempCaptionConfig.color }}>هذا مثال لشكل الترجمة على الفيديو</span>
                      )}
                    </div>

                    <div className="absolute top-3 right-3 text-[10px] text-neutral-500 font-bold bg-black/60 px-2 py-0.5 rounded border border-white/5 pointer-events-none">
                      معاينة حية 1080p
                    </div>
                  </div>
                </div>

                {/* ── RIGHT: CONTROLS ──────────────────────────────────────── */}
                <div className="space-y-5 text-right">
                  {/* 1. Primary & Highlight Free Color Pickers */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold text-neutral-300 mb-1.5">لون النص الأساسي:</label>
                      <div className="flex items-center gap-2 bg-[#1a1a1a] border border-neutral-800 p-1.5 rounded-xl">
                        <input
                          type="color"
                          value={tempCaptionConfig.color}
                          onChange={(e) => setTempCaptionConfig({ ...tempCaptionConfig, color: e.target.value })}
                          className="w-8 h-8 rounded-lg border-0 cursor-pointer bg-transparent"
                        />
                        <input
                          type="text"
                          value={tempCaptionConfig.color}
                          onChange={(e) => setTempCaptionConfig({ ...tempCaptionConfig, color: e.target.value })}
                          className="w-full bg-transparent text-xs font-mono text-white focus:outline-none uppercase"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-neutral-300 mb-1.5">لون التمييز (Highlight):</label>
                      <div className="flex items-center gap-2 bg-[#1a1a1a] border border-neutral-800 p-1.5 rounded-xl">
                        <input
                          type="color"
                          value={tempCaptionConfig.highlight_color}
                          onChange={(e) => setTempCaptionConfig({ ...tempCaptionConfig, highlight_color: e.target.value })}
                          className="w-8 h-8 rounded-lg border-0 cursor-pointer bg-transparent"
                        />
                        <input
                          type="text"
                          value={tempCaptionConfig.highlight_color}
                          onChange={(e) => setTempCaptionConfig({ ...tempCaptionConfig, highlight_color: e.target.value })}
                          className="w-full bg-transparent text-xs font-mono text-white focus:outline-none uppercase"
                        />
                      </div>
                    </div>
                  </div>

                  {/* 2. CapCut Style Effects Selector */}
                  <div>
                    <label className="block text-xs font-bold text-neutral-300 mb-2">نمط الحركة والتأثير (CapCut Style):</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { id: "none", label: "⚡ بسيط (ثابت)" },
                        { id: "karaoke", label: "🎤 كاريوكي" },
                        { id: "pop", label: "💥 نبض (CapCut Pop)" },
                        { id: "shadow", label: "🌑 ظل خلفي" },
                        { id: "box", label: "🔳 صندوق خلفية" },
                        { id: "outline", label: "🌓 حدود داكنة" },
                      ].map((ef) => (
                        <button
                          key={ef.id}
                          type="button"
                          onClick={() => setTempCaptionConfig({ ...tempCaptionConfig, effect: ef.id as any })}
                          className={`py-2 px-2 rounded-xl text-xs font-bold border transition-all ${
                            tempCaptionConfig.effect === ef.id
                              ? "bg-amber-500/20 border-amber-500 text-amber-400 shadow-md shadow-amber-500/10"
                              : "bg-[#1a1a1a] border-neutral-800 text-neutral-400 hover:border-neutral-700"
                          }`}
                        >
                          {ef.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 3. Font Selector */}
                  <div>
                    <label className="block text-xs font-bold text-neutral-300 mb-2">نوع الخط:</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { id: "Cairo", label: "Cairo", fontVar: "var(--font-cairo)" },
                        { id: "Geist", label: "Geist", fontVar: "var(--font-plus-jakarta)" },
                        { id: "Almarai", label: "Almarai", fontVar: "var(--font-almarai)" },
                        { id: "Montserrat", label: "Montserrat", fontVar: "var(--font-montserrat)" },
                        { id: "Poppins", label: "Poppins", fontVar: "var(--font-poppins)" },
                        ...customFonts.map((cf) => ({
                          id: `custom:${cf.id}`,
                          label: cf.font_name,
                          fontVar: "sans-serif",
                        })),
                      ].map((ft) => (
                        <button
                          key={ft.id}
                          type="button"
                          onClick={() => setTempCaptionConfig({ ...tempCaptionConfig, font: ft.id as any })}
                          style={{ fontFamily: ft.fontVar }}
                          className={`py-2 px-2 rounded-xl text-xs font-bold border transition-all truncate ${
                            tempCaptionConfig.font === ft.id
                              ? "bg-amber-500/20 border-amber-500 text-amber-400"
                              : "bg-[#1a1a1a] border-neutral-800 text-neutral-400 hover:border-neutral-700"
                          }`}
                        >
                          {ft.label}
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={() => {
                          setUploadFontError(null);
                          setIsUploadFontOpen(true);
                        }}
                        className="py-2 px-2 rounded-xl text-xs font-bold border border-dashed border-amber-500/40 text-amber-400 hover:bg-amber-500/10 transition-all flex items-center justify-center gap-1"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>رفع خط مخصص</span>
                      </button>
                    </div>
                  </div>

                  {/* 4. Size Slider */}
                  <div>
                    <div className="flex items-center justify-between text-xs font-bold text-neutral-300 mb-2">
                      <span>حجم الخط:</span>
                      <span className="text-amber-400 font-mono">{tempCaptionConfig.size_percent}%</span>
                    </div>
                    <input
                      type="range"
                      min="50"
                      max="150"
                      step="5"
                      value={tempCaptionConfig.size_percent}
                      onChange={(e) =>
                        setTempCaptionConfig({ ...tempCaptionConfig, size_percent: Number(e.target.value) })
                      }
                      className="w-full accent-amber-500 cursor-pointer bg-neutral-800 rounded-lg h-2"
                    />
                    <div className="flex justify-between text-[10px] text-neutral-500 mt-1">
                      <span>صغير (50%)</span>
                      <span>عادي (100%)</span>
                      <span>كبير (150%)</span>
                    </div>
                  </div>

                  {/* 5. Position Selector */}
                  <div>
                    <label className="block text-xs font-bold text-neutral-300 mb-2">موضع النص على الفيديو:</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { id: "top", label: "أعلى ⬆️" },
                        { id: "middle", label: "وسط ⏹️" },
                        { id: "bottom", label: "أسفل ⬇️" },
                      ].map((pos) => (
                        <button
                          key={pos.id}
                          type="button"
                          onClick={() => setTempCaptionConfig({ ...tempCaptionConfig, position: pos.id as any })}
                          className={`py-2 rounded-xl text-xs font-bold border transition-all ${
                            tempCaptionConfig.position === pos.id
                              ? "bg-amber-500/20 border-amber-500 text-amber-400"
                              : "bg-[#1a1a1a] border-neutral-800 text-neutral-400 hover:border-neutral-700"
                          }`}
                        >
                          {pos.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Modal Footer / Confirm Button */}
              <div className="border-t border-neutral-800 pt-4 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsCaptionModalOpen(false)}
                  className="px-4 py-2.5 rounded-xl text-xs text-neutral-400 hover:text-white transition-colors"
                >
                  إلغاء
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCaptionConfig(tempCaptionConfig);
                    setIsCaptionModalOpen(false);
                  }}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-rose-500 text-black font-extrabold text-xs hover:opacity-90 transition-all shadow-lg shadow-amber-500/20 flex items-center gap-2"
                >
                  <Check className="w-4 h-4" />
                  <span>تأكيد الإعدادات ومتابعة</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── VOICE CLONING MODAL (FISH AUDIO) ────────────────────────────────── */}
        {isCloningOpen && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200">
            <div className="bg-[#121212] border border-neutral-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-5 relative">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-neutral-800 pb-4">
                <div className="flex items-center gap-2 text-cyan-400 font-extrabold text-lg">
                  <Mic className="w-5 h-5" />
                  <h3>استنسخ صوتك الشخصي (Fish Audio)</h3>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    handleStopRecording();
                    setIsCloningOpen(false);
                  }}
                  className="p-1 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Voice Name Input */}
              <div>
                <label className="block text-xs font-bold text-neutral-300 mb-2">
                  اسم الصوت المستنسخ:
                </label>
                <input
                  type="text"
                  required
                  placeholder="مثال: بصوتي الشخصي - حماسي"
                  value={cloneVoiceName}
                  onChange={(e) => setCloneVoiceName(e.target.value)}
                  className="w-full bg-[#1c1c1c] border border-neutral-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-cyan-500 transition-colors"
                />
              </div>

              {/* Audio Source Options (Record or Upload) */}
              <div className="space-y-4">
                {/* 1. Record via Microphone */}
                <div className="bg-[#1a1a1a] border border-neutral-800 rounded-xl p-4 text-center">
                  <span className="text-xs font-bold text-neutral-300 block mb-2">
                    الخيار 1: سجل بصوتك الآن عبر الميكروفون
                  </span>
                  
                  {isRecording ? (
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-12 h-12 rounded-full bg-rose-500/20 text-rose-500 border border-rose-500/40 flex items-center justify-center animate-ping">
                        <Mic className="w-6 h-6" />
                      </div>
                      <span className="text-xs font-mono text-rose-400 font-bold">
                        جاري التسجيل: 00:{recordingTime < 10 ? `0${recordingTime}` : recordingTime}
                      </span>
                      <button
                        type="button"
                        onClick={handleStopRecording}
                        className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs rounded-xl flex items-center gap-2 shadow-lg shadow-rose-600/20"
                      >
                        <Square className="w-4 h-4 fill-current" />
                        <span>إيقاف التسجيل</span>
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={handleStartRecording}
                      className="px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs rounded-xl inline-flex items-center gap-2 shadow-lg shadow-cyan-600/20 transition-all"
                    >
                      <Mic className="w-4 h-4" />
                      <span>بدء تسجيل نموذج صوتك (10-30 ثانية)</span>
                    </button>
                  )}
                </div>

                {/* 2. File Upload */}
                <div className="bg-[#1a1a1a] border border-neutral-800 rounded-xl p-4 text-center">
                  <span className="text-xs font-bold text-neutral-300 block mb-2">
                    الخيار 2: أو قم برفع ملف صوتي جاهز (.mp3, .wav, .m4a)
                  </span>
                  <input
                    type="file"
                    accept="audio/*"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        const file = e.target.files[0];
                        setCloneFile(file);
                        setRecordedAudioUrl(URL.createObjectURL(file));
                      }
                    }}
                    className="block w-full text-xs text-neutral-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-neutral-800 file:text-cyan-400 hover:file:bg-neutral-700 cursor-pointer"
                  />
                </div>
              </div>

              {/* Recorded Audio Preview */}
              {recordedAudioUrl && (
                <div className="bg-cyan-950/20 border border-cyan-800/40 rounded-xl p-3 flex items-center justify-between">
                  <span className="text-xs text-cyan-300 font-bold flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                    تم التقاط الصوت بنجاح!
                  </span>
                  <audio controls src={recordedAudioUrl} className="h-8 max-w-[200px]" />
                </div>
              )}

              {/* Error Message */}
              {cloningError && (
                <div className="bg-rose-950/30 border border-rose-800 text-rose-300 p-3 rounded-xl text-xs text-right flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{cloningError}</span>
                </div>
              )}

              {/* Footer */}
              <div className="border-t border-neutral-800 pt-4 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    handleStopRecording();
                    setIsCloningOpen(false);
                  }}
                  className="px-4 py-2.5 rounded-xl text-xs text-neutral-400 hover:text-white transition-colors"
                >
                  إلغاء
                </button>
                <button
                  type="button"
                  onClick={handleCloneSubmit}
                  disabled={cloningLoading || !cloneFile || !cloneVoiceName.trim()}
                  className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-extrabold text-xs hover:opacity-90 disabled:opacity-50 transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
                >
                  {cloningLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>جاري الاستنساخ وحفظ الصوت...</span>
                    </>
                  ) : (
                    <>
                      <Wand2 className="w-4 h-4" />
                      <span>استنسخ الصوت الآن 🚀</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── CUSTOM FONT UPLOAD MODAL ─────────────────────────────────────── */}
        {isUploadFontOpen && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200">
            <div className="bg-[#121212] border border-neutral-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-5 relative text-right">
              <div className="flex items-center justify-between border-b border-neutral-800 pb-4">
                <div className="flex items-center gap-2 text-amber-400 font-extrabold text-base">
                  <Type className="w-5 h-5" />
                  <h3>رفع خط مخصص (.ttf / .otf)</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsUploadFontOpen(false)}
                  className="p-1 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div>
                <label className="block text-xs font-bold text-neutral-300 mb-2">اسم الخط كما تريده أن يظهر:</label>
                <input
                  type="text"
                  required
                  placeholder="مثال: خطي الخاص الحماسي"
                  value={uploadFontName}
                  onChange={(e) => setUploadFontName(e.target.value)}
                  className="w-full bg-[#1c1c1c] border border-neutral-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-amber-500 transition-colors"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-neutral-300 mb-2">ملف الخط (.ttf أو .otf):</label>
                <input
                  type="file"
                  accept=".ttf,.otf"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setUploadFontFile(e.target.files[0]);
                    }
                  }}
                  className="block w-full text-xs text-neutral-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-neutral-800 file:text-amber-400 hover:file:bg-neutral-700 cursor-pointer"
                />
              </div>

              {uploadFontError && (
                <div className="bg-rose-950/30 border border-rose-800 text-rose-300 p-3 rounded-xl text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{uploadFontError}</span>
                </div>
              )}

              <div className="border-t border-neutral-800 pt-4 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsUploadFontOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs text-neutral-400 hover:text-white transition-colors"
                >
                  إلغاء
                </button>
                <button
                  type="button"
                  onClick={handleUploadFontSubmit}
                  disabled={uploadFontLoading || !uploadFontFile || !uploadFontName.trim()}
                  className="px-5 py-2 rounded-xl bg-amber-500 text-black font-extrabold text-xs hover:bg-amber-400 disabled:opacity-50 transition-all shadow-lg shadow-amber-500/20 flex items-center gap-2"
                >
                  {uploadFontLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>جاري الرفع...</span>
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4" />
                      <span>رفع الخط وتطبيقه</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Dynamic Section Approval Modal */}
        {sectionApprovalData && (
          <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
            <div className="bg-[#141414] border border-amber-500/30 rounded-2xl max-w-lg w-full p-6 space-y-5 shadow-2xl shadow-amber-500/10 animate-in fade-in zoom-in-95">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-amber-400" />
                </div>
                <div>
                  <h3 className="text-base font-extrabold text-white">اقتراح أقسام للفيديو تلقائياً</h3>
                  <p className="text-xs text-neutral-400">حلل الذكاء الاصطناعي السكريبت واقترح إضافة عناوين للأقسام</p>
                </div>
              </div>

              {sectionApprovalData.reasoning && (
                <p className="text-xs bg-neutral-900 border border-neutral-800 p-3 rounded-xl text-neutral-300">
                  {sectionApprovalData.reasoning}
                </p>
              )}

              {sectionApprovalData.sections && sectionApprovalData.sections.length > 0 && (
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  <span className="text-xs font-bold text-neutral-400">الأقسام المقترحة:</span>
                  {sectionApprovalData.sections.map((sec: any, idx: number) => (
                    <div key={idx} className="bg-neutral-900/80 border border-neutral-800 p-2.5 rounded-xl flex items-center justify-between text-xs">
                      <span className="text-amber-400 font-bold">المشهد #{sec.scene_index + 1}</span>
                      <span className="text-white font-medium">{sec.section_title || (sec.section_number ? `القسم ${sec.section_number}` : "")}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex items-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => handleSectionDecision(true)}
                  disabled={submittingSectionDecision}
                  className="flex-1 py-2.5 rounded-xl bg-amber-500 text-black font-extrabold text-xs hover:bg-amber-400 disabled:opacity-50 transition-all shadow-lg shadow-amber-500/20 flex items-center justify-center gap-2"
                >
                  {submittingSectionDecision ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      <span>تطبيق الأقسام واستمرار التوليد</span>
                    </>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => handleSectionDecision(false)}
                  disabled={submittingSectionDecision}
                  className="py-2.5 px-4 rounded-xl bg-neutral-800 text-neutral-300 font-bold text-xs hover:bg-neutral-700 hover:text-white disabled:opacity-50 transition-all"
                >
                  تجاهل والتوليد بدون أقسام
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </main>
  );
}
