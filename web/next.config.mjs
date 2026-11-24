/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // On Vercel the hosted build is always the public demo: synthetic examples only.
  env: { NEXT_PUBLIC_DEMO_MODE: process.env.NEXT_PUBLIC_DEMO_MODE ?? (process.env.VERCEL ? "1" : "") },
};
export default nextConfig;
