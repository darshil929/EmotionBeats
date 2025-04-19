/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required for working behind a reverse proxy
  assetPrefix: '',
  // Required for full URLs
  basePath: '',
  // Other Next.js configuration
  reactStrictMode: true,
  output: 'standalone',
}

module.exports = nextConfig
