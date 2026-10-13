import type { NextConfig } from 'next';
const config: NextConfig = {
  // Windows without Developer Mode cannot create pnpm's traced links. Render builds on Linux.
  output: process.platform === 'win32' ? undefined : 'standalone', poweredByHeader: false,
  devIndicators: false,
  async headers() { return [{ source: '/(.*)', headers: [
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'Referrer-Policy', value: 'same-origin' },
    { key: 'X-Frame-Options', value: 'DENY' },
    { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  ] }]; },
};
export default config;
