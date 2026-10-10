/** @type {import('next').NextConfig} */
const nextConfig = {
  // Two model stages (parallel debate, then judge) can exceed the 30s default.
  experimental: { proxyTimeout: 120000 },
  async rewrites() {
    return [{ source: '/api/:path*', destination: `${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}/api/:path*` }];
  },
};

module.exports = nextConfig;
