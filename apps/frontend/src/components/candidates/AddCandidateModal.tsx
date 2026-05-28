import React, { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { IconX, IconUserPlus } from "@tabler/icons-react";
import { usePositionsStore } from "@/stores/usePositionsStore";

interface AddCandidateModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function AddCandidateModal({ isOpen, onClose }: AddCandidateModalProps) {
  const { addCandidate } = usePositionsStore();

  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone: "",
    previousCompany: "",
    experienceYears: "",
    skills: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Parse skills from comma-separated string
    const parsedSkills = formData.skills
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    addCandidate({
      name: formData.name,
      email: formData.email,
      phone: formData.phone,
      previousCompany: formData.previousCompany,
      experienceYears: Number(formData.experienceYears) || 0,
      skills: parsedSkills.length > 0 ? parsedSkills : ["General"],
    });

    setFormData({
      name: "",
      email: "",
      phone: "",
      previousCompany: "",
      experienceYears: "",
      skills: "",
    });

    onClose();
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 transition-opacity flex items-center justify-center p-4"
          >
            {/* Modal */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-[var(--color-surface)] border border-border shadow-2xl rounded-2xl w-full max-w-md overflow-hidden flex flex-col max-h-[90vh]"
            >
              {/* Header */}
              <div className="p-5 border-b border-border flex items-center justify-between bg-[var(--color-surface)]">
                <h2 className="text-lg font-bold font-heading text-white flex items-center gap-2">
                  <IconUserPlus className="size-5 text-yellow" />
                  Add New Candidate
                </h2>
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg bg-[var(--color-canvas)] border border-border text-gray-400 hover:text-white transition-colors"
                >
                  <IconX className="size-4" />
                </button>
              </div>

              {/* Form Content */}
              <div className="p-5 overflow-y-auto dashboard-scrollbar bg-[var(--color-canvas)]">
                <form id="add-candidate-form" onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">
                      Full Name
                    </label>
                    <input
                      required
                      type="text"
                      placeholder="e.g. Ayesha Khan"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-surface)] border border-border text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">
                        Email
                      </label>
                      <input
                        required
                        type="email"
                        placeholder="ayesha@example.com"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-surface)] border border-border text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">
                        Phone
                      </label>
                      <input
                        required
                        type="text"
                        placeholder="+91 98765 43210"
                        value={formData.phone}
                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                        className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-surface)] border border-border text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">
                        Previous Company
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. Taj Hotels"
                        value={formData.previousCompany}
                        onChange={(e) =>
                          setFormData({ ...formData, previousCompany: e.target.value })
                        }
                        className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-surface)] border border-border text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">
                        Years Exp
                      </label>
                      <input
                        required
                        type="number"
                        min="0"
                        step="0.5"
                        placeholder="e.g. 3"
                        value={formData.experienceYears}
                        onChange={(e) =>
                          setFormData({ ...formData, experienceYears: e.target.value })
                        }
                        className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-surface)] border border-border text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wider">
                      Skills (Comma separated)
                    </label>
                    <input
                      required
                      type="text"
                      placeholder="e.g. POS Systems, Guest Relations, Billing"
                      value={formData.skills}
                      onChange={(e) => setFormData({ ...formData, skills: e.target.value })}
                      className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-surface)] border border-border text-white placeholder-gray-500 focus:outline-none focus:border-yellow transition-all"
                    />
                  </div>
                </form>
              </div>

              {/* Footer Actions */}
              <div className="p-5 border-t border-border bg-[var(--color-surface)] flex justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  form="add-candidate-form"
                  className="px-4 py-2 rounded-lg bg-yellow text-navy hover:bg-yellow-dark text-sm font-bold transition-all shadow-lg shadow-yellow/10"
                >
                  Add Candidate
                </button>
              </div>
            </motion.div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
