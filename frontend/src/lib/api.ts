/**
 * imaginAI Client API Utilities
 */

export interface CaptionConfig {
  color?: string;
  effect?: string;
  font?: string;
  size_percent?: number;
  position?: string;
}

export interface JobRequest {
  idea: string;
  duration: "5_min" | "8_min" | "10_min" | "15_min" | "short" | "medium";
  style?: "mystery" | "listicle" | "documentary" | "motivational";
  voice_provider?: "gemini" | "fish-audio" | "edge-tts" | "gtts";
  voice?: string;
  niche_id?: string;
  custom_niche?: string;
  music_track?: string;
  input_mode?: "ai_generated" | "script_provided" | "idea" | "script";
  provided_script?: string;
  additional_context?: string;
  caption_config?: CaptionConfig;
}

export interface SubNiche {
  id: string;
  title: string;
  desc: string;
  prompt_instructions?: string;
  visual_style?: string;
  music_style?: string;
}

export interface DomainCategory {
  id: string;
  title: string;
  icon: string;
  color: string;
  sub_niches: SubNiche[];
}

export async function getNiches(): Promise<{ domains: DomainCategory[] }> {
  const resp = await fetch(`${API_BASE}/api/niches`, { cache: "no-store" });
  if (!resp.ok) {
    throw new Error("Failed to fetch niches catalog");
  }
  return resp.json();
}

export interface VoiceItem {
  id: string;
  name: string;
  gender: "male" | "female" | "neutral";
  lang: string;
  desc: string;
}

export interface VoiceProviderCatalog {
  provider: "gemini" | "fish-audio" | "edge-tts" | "gtts";
  provider_name: string;
  desc: string;
  voices: VoiceItem[];
}


export interface JobStatusResponse {
  job_id: string;
  status: "pending" | "processing" | "pending_section_approval" | "pending_review" | "done" | "failed";
  current_stage?: string;
  section_proposal?: any;
  stages: {
    script: "pending" | "processing" | "done" | "failed";
    tts: "pending" | "processing" | "done" | "failed";
    footage: "pending" | "processing" | "done" | "failed";
    captions: "pending" | "processing" | "done" | "failed";
    render: "pending" | "processing" | "done" | "failed";
  };
  error?: string;
  output_url?: string;
}

const API_BASE = "http://localhost:8000";

function getOrCreateVisitorId(): string {
  if (typeof window === "undefined") return "server_ssr";
  let vid = localStorage.getItem("imaginai_visitor_id");
  if (!vid) {
    vid = "v_" + Math.random().toString(36).substring(2, 11) + Date.now().toString(36);
    localStorage.setItem("imaginai_visitor_id", vid);
  }
  return vid;
}

export async function createJob(data: JobRequest): Promise<{ job_id: string }> {
  const visitorId = getOrCreateVisitorId();
  const resp = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    let errDetail = "فشل إنشاء طلب الفيديو";
    try {
      const errJson = await resp.json();
      if (errJson.detail) errDetail = errJson.detail;
    } catch {
      errDetail = resp.statusText || errDetail;
    }
    throw new Error(errDetail);
  }
  return resp.json();
}

export async function sendFeedback(message: string, contact?: string): Promise<{ message: string }> {
  const resp = await fetch(`${API_BASE}/api/feedback`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, contact }),
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.detail || "فشل إرسال الملاحظات");
  }
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}/status`, {
    cache: "no-store",
    credentials: "include",
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch job status: ${resp.statusText}`);
  }
  return resp.json();
}

export function getDownloadUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/download`;
}

export async function getVoicesCatalog(): Promise<{ providers: VoiceProviderCatalog[] }> {
  const visitorId = getOrCreateVisitorId();
  const resp = await fetch(`${API_BASE}/api/voices`, {
    cache: "no-store",
    credentials: "include",
    headers: {
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
  });
  if (!resp.ok) {
    throw new Error("Failed to fetch voices catalog");
  }
  return resp.json();
}

export interface Project {
  project_id: string;
  device_id: string;
  domain: string;
  niche: string;
  name: string;
  created_at: string;
  video_count?: number;
  last_video_at?: string;
}

export interface VideoItem {
  video_id: string;
  project_id: string;
  title: string;
  file_path?: string;
  duration: number;
  created_at: string;
  status: "processing" | "completed" | "failed";
}

export async function getProjects(): Promise<{ projects: Project[] }> {
  const visitorId = getOrCreateVisitorId();
  const resp = await fetch(`${API_BASE}/api/projects`, {
    cache: "no-store",
    credentials: "include",
    headers: { 
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
  });
  if (!resp.ok) {
    throw new Error("Failed to fetch projects list");
  }
  return resp.json();
}

export async function createProject(data: { domain: string; niche: string; name: string }): Promise<Project> {
  const visitorId = getOrCreateVisitorId();
  const resp = await fetch(`${API_BASE}/api/projects`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    throw new Error("Failed to create project");
  }
  return resp.json();
}

export async function getProjectVideos(projectId: string): Promise<{ project: Project; videos: VideoItem[] }> {
  const visitorId = getOrCreateVisitorId();
  const resp = await fetch(`${API_BASE}/api/projects/${projectId}`, {
    cache: "no-store",
    credentials: "include",
    headers: { 
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
  });
  if (!resp.ok) {
    throw new Error("Failed to fetch project videos");
  }
  return resp.json();
}

export function getVideoStreamUrl(videoId: string): string {
  return `${API_BASE}/api/videos/${videoId}/stream`;
}

export function getVoicePreviewUrl(provider: string, voiceId: string): string {
  return `${API_BASE}/api/voices/preview?provider=${encodeURIComponent(provider)}&voice=${encodeURIComponent(voiceId)}`;
}

export async function cloneVoice(file: File, voiceName: string): Promise<{ success: boolean; voice: any }> {
  const visitorId = getOrCreateVisitorId();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("voice_name", voiceName);

  const resp = await fetch(`${API_BASE}/api/voices/clone`, {
    method: "POST",
    credentials: "include",
    headers: {
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
    body: formData,
  });

  if (!resp.ok) {
    let errDetail = "فشل استنسخ الصوت";
    try {
      const errJson = await resp.json();
      if (errJson.detail) errDetail = errJson.detail;
    } catch {
      errDetail = resp.statusText || errDetail;
    }
    throw new Error(errDetail);
  }

  return resp.json();
}

export interface CustomFont {
  id: string;
  device_id: string;
  font_name: string;
  file_path: string;
  created_at: string;
}

export async function uploadCustomFont(file: File, fontName: string): Promise<{ success: boolean; font: CustomFont }> {
  const visitorId = getOrCreateVisitorId();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("font_name", fontName);

  const resp = await fetch(`${API_BASE}/api/fonts/upload`, {
    method: "POST",
    credentials: "include",
    headers: {
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
    body: formData,
  });

  if (!resp.ok) {
    let errDetail = "فشل رفع الخط";
    try {
      const errJson = await resp.json();
      if (errJson.detail) errDetail = errJson.detail;
    } catch {
      errDetail = resp.statusText || errDetail;
    }
    throw new Error(errDetail);
  }

  return resp.json();
}

export async function getCustomFonts(): Promise<{ fonts: CustomFont[] }> {
  const visitorId = getOrCreateVisitorId();
  const resp = await fetch(`${API_BASE}/api/fonts`, {
    cache: "no-store",
    credentials: "include",
    headers: {
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
  });

  if (!resp.ok) {
    throw new Error("Failed to fetch custom fonts");
  }

  return resp.json();
}

export interface ReviewShot {
  shot_index: number;
  clip_path: string;
  stream_url: string;
}

export interface ReviewScene {
  scene_index: number;
  narration: string;
  visual_keywords: string[];
  audio_path: string;
  audio_duration: number;
  shots: ReviewShot[];
}

export interface ReviewData {
  job_id: string;
  idea?: string;
  duration?: string;
  style?: string;
  voice?: string;
  voice_provider?: string;
  scenes: ReviewScene[];
}

export async function getJobReviewData(jobId: string): Promise<ReviewData> {
  const visitorId = getOrCreateVisitorId();
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}/review`, {
    cache: "no-store",
    credentials: "include",
    headers: {
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
  });

  if (!resp.ok) {
    throw new Error("فشل جلب بيانات المراجعة");
  }

  return resp.json();
}

export async function resumeJob(
  jobId: string,
  editedScenes: { scene_index: number; narration?: string; shots?: string[] }[]
): Promise<{ success: boolean; message: string }> {
  const visitorId = getOrCreateVisitorId();
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}/resume`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
    body: JSON.stringify({ edited_scenes: editedScenes }),
  });

  if (!resp.ok) {
    let errMsg = "فشل استئناف عملية الرندر";
    try {
      const errJson = await resp.json();
      if (errJson.detail) errMsg = errJson.detail;
    } catch {
      errMsg = resp.statusText || errMsg;
    }
    throw new Error(errMsg);
  }

  return resp.json();
}

export async function approveJobSections(
  jobId: string,
  applySections: boolean
): Promise<{ success: boolean; message: string }> {
  const visitorId = getOrCreateVisitorId();
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}/approve-sections`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "x-visitor-id": visitorId,
      "x-device-id": visitorId,
    },
    body: JSON.stringify({ apply_sections: applySections }),
  });

  if (!resp.ok) {
    let errMsg = "فشل إرسال قرار الأقسام";
    try {
      const errJson = await resp.json();
      if (errJson.detail) errMsg = errJson.detail;
    } catch {
      errMsg = resp.statusText || errMsg;
    }
    throw new Error(errMsg);
  }

  return resp.json();
}


