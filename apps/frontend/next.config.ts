import type { NextConfig } from "next";
import { loadEnvConfig } from "@next/env";
import path from "path";

// Point Next.js to the monorepo root to load the shared .env file.
// This means .env, .env.local, .env.production etc. all live at the root.
loadEnvConfig(path.resolve(__dirname, "../../"));

const nextConfig: NextConfig = {
  env: {},
};

export default nextConfig;
