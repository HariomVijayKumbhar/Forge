/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        // Dev: proxied by the Next.js server to local FastAPI.
        // Prod (Vercel): NEXT_PUBLIC_API_BASE_URL points at the Render backend.
        destination: `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
