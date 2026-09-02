import type { NextConfig } from "next";

const nextConfig: NextConfig = {


  experimental: {
    proxyTimeout: 120000,
  },

  async rewrites() {
    // IMPORTANT: This value is evaluated at `next build` time, NOT at request time.
    // In production (Railway), set BACKEND_API_URL as a build-time environment variable
    // on the frontend service, e.g. https://your-backend.up.railway.app/api
    // The compiled destination is baked into .next/routes-manifest.json.
    const backendUrl = process.env.BACKEND_API_URL || 'http://127.0.0.1:8001/api';
    return [
      {
        source: '/api/backend/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
