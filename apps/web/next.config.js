/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@saleha/ui"],
  experimental: {
    serverActions: {
      bodySizeLimit: '10mb',
    },
  },
};

module.exports = nextConfig;

