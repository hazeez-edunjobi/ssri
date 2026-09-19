import type { NextConfig } from "next";

/**
 * Next.js configuration.
 * Note: Next.js 14 loads `next.config.mjs` at runtime.
 * Keep both files in sync when making changes.
 */
const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
        pathname: "/**",
      },
    ],
  },
};

export default nextConfig;
