const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function setMappingInterviewDate(
  mappingId: string,
  interviewDate: string,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/interview-date`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ interview_date: interviewDate }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function uploadMappingOffer(mappingId: string, file: File): Promise<void> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/offer-letter`, {
    method: "PUT",
    credentials: "include",
    body: formData,
  });
  // The endpoint rejects a non-PDF (400) and an oversize file (413) with a
  // readable `detail`; res.text() would put the raw JSON in front of the user.
  if (!res.ok) {
    let detail = "Could not upload the offer letter.";
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON error body — keep the generic message.
    }
    throw new Error(detail);
  }
}

export async function setMappingJoiningDate(
  mappingId: string,
  joiningDate: string,
  salaryOffered: number,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/joining-date`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ joining_date: joiningDate, salary_offered: salaryOffered }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function setMappingDropped(mappingId: string, droppedNotes: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/pipeline/mappings/${mappingId}/dropped`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ dropped_notes: droppedNotes }),
  });
  if (!res.ok) throw new Error(await res.text());
}
