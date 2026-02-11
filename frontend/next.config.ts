import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  async redirects() {
    return [
      {
        source: '/telemetry',
        destination: 'http://136.119.132.38:3333/',
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
