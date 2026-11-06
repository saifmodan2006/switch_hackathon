import type { NextConfig } from 'next';
const config: NextConfig = {
  distDir: process.env.E2E === '1' ? '.next-e2e' : '.next',
  output: 'standalone',
  devIndicators: false,
  async rewrites() { return [{source:'/api/:path*', destination:`${process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000'}/api/:path*`}]; },
  async headers() { return [{source:'/:path*',headers:[{key:'X-Content-Type-Options',value:'nosniff'},{key:'X-Frame-Options',value:'DENY'},{key:'Referrer-Policy',value:'strict-origin-when-cross-origin'}]}]; }
};
export default config;
