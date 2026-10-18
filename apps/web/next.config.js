/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // 浏览器只需访问前端端口；由 Next.js 服务器（与后端同网络环境）
    // 转发到真实 API，避免跨域和 WSL/宿主机端口转发问题。
    const target = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8001";
    return [
      {
        source: "/api/:path*",
        destination: `${target}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
