import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  transpilePackages: ["@aces/ui", "@aces/brand", "@aces/content"],
};

export default nextConfig;
