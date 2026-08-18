import React, { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconX, IconUserPlus } from "@tabler/icons-react";
import { useApiFetch } from "@/lib/api";
import { createCandidate, type CandidateCreatePayload } from "@/lib/api/candidates";
import type { ApiCandidate } from "@/types";

interface AddCandidateModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Called with the newly created candidate so the parent can prepend it to the list. */
  onCreated: (candidate: ApiCandidate) => void;
}

const EMPTY_FORM = {
  name: "",
  email: "",
  phone: "",
  previousCompany: "",
  experienceYears: "",
  skills: "",
  department: "",
  city: "",
  expectedSalary: "",
  sourceType: "internal", // internal or external
  sourceChannel: "", // Sourcing Team or external ref
};

// Tailwind v4 input class reused across every field
const INPUT_CLS =
  "w-full px-3 py-2 text-sm rounded-lg bg-(--color-surface) border border-border text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all";

const LABEL_CLS = "block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider";

export default function AddCandidateModal({
  isOpen,
  onClose,
  onCreated,
}: Readonly<AddCandidateModalProps>) {
  const apiFetch = useApiFetch();
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // React 19: use SyntheticEvent<HTMLFormElement> — FormEvent is deprecated
  async function handleSubmit(e: React.SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    const payload: CandidateCreatePayload = {
      full_name: formData.name.trim(),
      email: formData.email.trim(),
      phone: formData.phone.trim() || undefined,
      previous_company: formData.previousCompany.trim() || undefined,
      experience_years: Number(formData.experienceYears) || 0,
      department: formData.department.trim() || undefined,
      city: formData.city.trim() || undefined,
      expected_salary: Number(formData.expectedSalary) || undefined,
      source: formData.sourceType === "internal" ? formData.sourceChannel : "external",
      skills: formData.skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    };
    if (payload.skills.length === 0) payload.skills = ["General"];

    try {
      const created = await createCandidate(apiFetch, payload);
      onCreated(created);
      setFormData(EMPTY_FORM);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add candidate. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleClose() {
    if (isSubmitting) return;
    setFormData(EMPTY_FORM);
    setError(null);
    onClose();
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleClose}
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="add-candidate-title"
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-(--color-surface) border border-border shadow-2xl rounded-2xl w-full max-w-md overflow-hidden flex flex-col max-h-[90vh]"
          >
            {/* Header */}
            <div className="p-5 border-b border-border flex items-center justify-between bg-(--color-surface)">
              <h2
                id="add-candidate-title"
                className="text-lg font-bold font-heading text-white flex items-center gap-2"
              >
                <IconUserPlus className="size-5 text-yellow" />
                Add New Candidate
              </h2>
              <button
                type="button"
                onClick={handleClose}
                disabled={isSubmitting}
                aria-label="Close"
                className="p-1.5 rounded-lg bg-(--color-canvas) border border-border text-gray-400 hover:text-white transition-colors disabled:opacity-50"
              >
                <IconX className="size-4" />
              </button>
            </div>

            {/* Form */}
            <div className="p-5 overflow-y-auto dashboard-scrollbar bg-(--color-canvas)">
              {error && (
                <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                  {error}
                </div>
              )}

              <form id="add-candidate-form" onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="cand-name" className={LABEL_CLS}>
                    Full Name
                  </label>
                  <input
                    id="cand-name"
                    required
                    type="text"
                    placeholder="e.g. Ayesha Khan"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className={INPUT_CLS}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="cand-email" className={LABEL_CLS}>
                      Email
                    </label>
                    <input
                      id="cand-email"
                      required
                      type="email"
                      placeholder="ayesha@example.com"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className={INPUT_CLS}
                    />
                  </div>
                  <div>
                    <label htmlFor="cand-phone" className={LABEL_CLS}>
                      Phone
                    </label>
                    <input
                      id="cand-phone"
                      type="text"
                      placeholder="+91 98765 43210"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className={INPUT_CLS}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="cand-company" className={LABEL_CLS}>
                      Previous Company
                    </label>
                    <input
                      id="cand-company"
                      type="text"
                      placeholder="e.g. Taj Hotels"
                      value={formData.previousCompany}
                      onChange={(e) =>
                        setFormData({ ...formData, previousCompany: e.target.value })
                      }
                      className={INPUT_CLS}
                    />
                  </div>
                  <div>
                    <label htmlFor="cand-exp" className={LABEL_CLS}>
                      Years Exp
                    </label>
                    <input
                      id="cand-exp"
                      required
                      type="number"
                      min="0"
                      step="0.5"
                      placeholder="e.g. 3"
                      value={formData.experienceYears}
                      onChange={(e) =>
                        setFormData({ ...formData, experienceYears: e.target.value })
                      }
                      className={INPUT_CLS}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="cand-dept" className={LABEL_CLS}>
                      Department
                    </label>
                    <select
                      id="cand-dept"
                      value={formData.department}
                      onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                      className={INPUT_CLS}
                    >
                      <option value="">Select...</option>
                      <option value="BOH">BOH</option>
                      <option value="Service">Service</option>
                      <option value="Corporate">Corporate</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor="cand-city" className={LABEL_CLS}>
                      City
                    </label>
                    <input
                      id="cand-city"
                      type="text"
                      placeholder="e.g. Mumbai"
                      value={formData.city}
                      onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                      className={INPUT_CLS}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="cand-salary" className={LABEL_CLS}>
                      Expected Salary
                    </label>
                    <input
                      id="cand-salary"
                      type="number"
                      placeholder="e.g. 50000"
                      value={formData.expectedSalary}
                      onChange={(e) => setFormData({ ...formData, expectedSalary: e.target.value })}
                      className={INPUT_CLS}
                    />
                  </div>
                  <div>
                    <label htmlFor="cand-source-type" className={LABEL_CLS}>
                      Source Type
                    </label>
                    <select
                      id="cand-source-type"
                      value={formData.sourceType}
                      onChange={(e) => setFormData({ ...formData, sourceType: e.target.value })}
                      className={INPUT_CLS}
                    >
                      <option value="internal">Internal (Sourcing Team)</option>
                      <option value="external">External (Referral/Other)</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label htmlFor="cand-source-channel" className={LABEL_CLS}>
                    {formData.sourceType === "internal"
                      ? "Sourcing Team Name"
                      : "External Source Details"}
                  </label>
                  <input
                    id="cand-source-channel"
                    type="text"
                    placeholder={
                      formData.sourceType === "internal"
                        ? "e.g. Team Alpha"
                        : "e.g. LinkedIn, Connect Code"
                    }
                    value={formData.sourceChannel}
                    onChange={(e) => setFormData({ ...formData, sourceChannel: e.target.value })}
                    className={INPUT_CLS}
                  />
                </div>

                <div>
                  <label htmlFor="cand-skills" className={LABEL_CLS}>
                    Skills (comma-separated)
                  </label>
                  <input
                    id="cand-skills"
                    required
                    type="text"
                    placeholder="e.g. POS Systems, Guest Relations, Billing"
                    value={formData.skills}
                    onChange={(e) => setFormData({ ...formData, skills: e.target.value })}
                    className={INPUT_CLS}
                  />
                </div>
              </form>
            </div>

            {/* Footer */}
            <div className="p-5 border-t border-border bg-(--color-surface) flex justify-end gap-3">
              <button
                type="button"
                onClick={handleClose}
                disabled={isSubmitting}
                className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-400 hover:text-white transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                form="add-candidate-form"
                disabled={isSubmitting}
                className="px-4 py-2 rounded-lg bg-yellow text-navy hover:bg-yellow-dark text-sm font-bold transition-all shadow-lg shadow-yellow/10 disabled:opacity-60"
              >
                {isSubmitting ? "Adding…" : "Add Candidate"}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
