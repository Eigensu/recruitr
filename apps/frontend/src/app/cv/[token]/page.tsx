import CvUploadForm from "@/components/public/CvUploadForm";
import { fetchCvUploadLink } from "@/lib/api/public";

interface PageProps {
  readonly params: Promise<{ token: string }>;
}

export const metadata = {
  title: "Send your CV",
  // The address is the credential; it has no business in a search index.
  robots: { index: false, follow: false },
};

/** Where a CV upload link lands. Public: the candidate has no account. */
export default async function CvUploadPage({ params }: PageProps) {
  const { token } = await params;
  const info = await fetchCvUploadLink(token);
  return <CvUploadForm token={token} info={info} />;
}
