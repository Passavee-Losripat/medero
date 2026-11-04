/** @type {import('next').NextConfig} */
// NEXT_DIST_DIR lets a production build run next to the dev server without sharing .next
const nextConfig = { reactStrictMode: true, devIndicators: false, distDir: process.env.NEXT_DIST_DIR || ".next" };
export default nextConfig;
