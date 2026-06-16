"use client";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface UploadSignature {
  signature: string;
  timestamp: number;
  cloud_name: string;
  api_key: string;
  upload_preset: string;
  folder: string;
}

export interface UploadedResume {
  resume_public_id: string;
  resume_url: string;
}

async function getUploadSignature(): Promise<UploadSignature> {
  const res = await fetch(`${API_URL}/api/v1/storage/sign`, { credentials: "include" });
  if (!res.ok) throw new Error("Could not get upload signature");
  return res.json();
}

/**
 * Reuse the existing Cloudinary signed-upload flow: the backend signs the
 * params, the file bytes go directly from the browser to Cloudinary, and we
 * return the public_id + secure_url to attach to a candidate.
 */
export async function uploadResumeToCloudinary(file: File): Promise<UploadedResume> {
  const sig = await getUploadSignature();
  const form = new FormData();
  form.append("file", file);
  form.append("api_key", sig.api_key);
  form.append("timestamp", String(sig.timestamp));
  form.append("upload_preset", sig.upload_preset);
  form.append("folder", sig.folder);
  form.append("signature", sig.signature);

  const res = await fetch(`https://api.cloudinary.com/v1_1/${sig.cloud_name}/raw/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error("Cloudinary upload failed");
  const data = await res.json();
  return { resume_public_id: data.public_id, resume_url: data.secure_url };
}
