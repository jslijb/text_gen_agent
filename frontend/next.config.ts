/** @type {import('next').NextConfig} */
const nextConfig = {
  // spec v1.4.0：启用 standalone 输出（Docker 生产模式用）
  output: 'standalone',
  // API 请求（/api/*）用 app/api/[...path]/route.ts 自定义代理（5分钟超时，支持 LLM 长耗时）
  // 静态文件（/static/*）用 app/static/[...path]/route.ts 代理到后端
};

export default nextConfig;