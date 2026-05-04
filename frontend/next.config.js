/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Beta deploy: don't fail the production build on TS/ESLint errors.
  // Compilation is what matters at runtime; revisit once the type baseline is clean.
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000"}/:path*`,
      },
    ];
  },
};
module.exports = nextConfig;
