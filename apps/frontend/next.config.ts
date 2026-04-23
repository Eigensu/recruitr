import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Point Next.js to the monorepo root to load the shared .env file.
  // This means .env, .env.local, .env.production etc. all live at the root.
  env: {},
  // Next.js reads .env files from the project root by default when using
  // the `experimental.envDir` option (Next.js 15+).
  experimental: {
    envDir: path.resolve(__dirname, "../../"),
  },
};

export default nextConfig;
