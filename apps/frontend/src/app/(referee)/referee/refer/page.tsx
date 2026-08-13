import { IconUserPlus } from "@tabler/icons-react";

export default function ReferCandidatePlaceholder() {
  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 flex flex-col items-center justify-center">
      <div className="max-w-md w-full text-center space-y-6">
        <div className="mx-auto w-16 h-16 rounded-full bg-surface-2 border border-border flex items-center justify-center text-text-secondary">
          <IconUserPlus className="w-8 h-8" />
        </div>

        <div>
          <h1 className="text-2xl font-heading font-bold text-text-primary">Refer a Candidate</h1>
          <p className="text-sm text-text-secondary mt-2">
            The candidate referral flow is currently under development. Soon, you will be able to
            generate unique referral links or directly submit candidate information here.
          </p>
        </div>
      </div>
    </div>
  );
}
