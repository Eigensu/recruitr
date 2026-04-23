import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  activeBrandId: string | null;
  activeBrandName: string | null;
  setActiveBrand: (id: string, name: string) => void;
  clearBrand: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      activeBrandId: null,
      activeBrandName: null,
      setActiveBrand: (id, name) => set({ activeBrandId: id, activeBrandName: name }),
      clearBrand: () => set({ activeBrandId: null, activeBrandName: null }),
    }),
    { name: "eigensu-auth" }, // persisted to localStorage
  ),
);
