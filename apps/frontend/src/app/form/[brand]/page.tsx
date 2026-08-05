import { notFound } from "next/navigation";
import ApplicationForm from "@/components/public/ApplicationForm";
import { fetchPublicBrand } from "@/lib/api/public";

interface PageProps {
  readonly params: Promise<{ brand: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { brand: domain } = await params;
  const brand = await fetchPublicBrand(domain).catch(() => null);
  return {
    title: brand ? `Apply to ${brand.name}` : "Submit your application",
  };
}

export default async function BrandedApplicationForm({ params }: PageProps) {
  const { brand: domain } = await params;
  const brand = await fetchPublicBrand(domain);
  if (!brand) notFound();
  return <ApplicationForm brand={brand} />;
}
