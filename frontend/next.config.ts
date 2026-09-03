import type { NextConfig } from "next";

const nextConfig: NextConfig = {


  experimental: {
    proxyTimeout: 120000,
  },

  async rewrites() {
    // IMPORTANT: This value is evaluated at `next build` time, NOT at request time.
    // BACKEND_API_URL must be set as a Build Environment Variable in Vercel.
    // It is baked into .next/routes-manifest.json at build time.
    // Do NOT rely on NODE_ENV here — Vercel may evaluate this before NODE_ENV='production'
    // is set, causing the destination to be baked as http://127.0.0.1 and triggering
    // a 502 ROUTER_EXTERNAL_TARGET on Vercel's Edge Network.
    const defaultBackendUrl = 'https://research-intelligence-workspace-production.up.railway.app/api';
    const backendUrl = (process.env.BACKEND_API_URL || defaultBackendUrl).replace(/\/$/, '');
    return [
      {
        source: '/api/backend/:path*',
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
