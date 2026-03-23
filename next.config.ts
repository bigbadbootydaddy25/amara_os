import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  images: {
    domains: ["photos.zillowstatic.com", "maps.googleapis.com"],
  },
};

export default nextConfig;
