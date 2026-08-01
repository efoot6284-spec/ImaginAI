/**
 * imaginAI Client API Utilities
 */

export interface JobRequest {
  idea: string;
  duration: "5_min" | "8_min" | "10_min" | "short" | "medium";
  style?: "mystery" | "listicle" | "documentary" | "motivational";
  voice_provider?: "gemini" | "edge-tts" | "gtts";
  voice?: string;
}

export interface VoiceItem {
  id: string;
  name: string;
  gender: "male" | "female";
  lang: string;
  desc: string;
}

export interface VoiceProviderCatalog {
  provider: "edge-tts" | "gemini" | "gtts";
  provider_name: string;
  desc: string;
  voices: VoiceItem[];
}

export interface JobStatusResponse {
  job_id: string;
  status: "pending" | "processing" | "done" | "failed";
  current_stage?: string;
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
    headers: {
      "Content-Type": "application/json",
      "x-visitor-id": visitorId,
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
  const resp = await fetch(`${API_BASE}/api/voices`, { cache: "no-store" });
  if (!resp.ok) {
    throw new Error("Failed to fetch voices catalog");
  }
  return resp.json();
}

export function getVoicePreviewUrl(provider: string, voiceId: string): string {
  return `${API_BASE}/api/voices/preview?provider=${encodeURIComponent(provider)}&voice=${encodeURIComponent(voiceId)}`;
}
