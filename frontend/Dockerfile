# frontend/Dockerfile
# 开发模式：挂载源码，next dev 实时编译，支持新增路由文件热加载
FROM node:20-alpine

WORKDIR /app

# 安装依赖
COPY package.json package-lock.json* ./
RUN npm config set registry https://registry.npmmirror.com && npm ci

# 源码通过 volume 挂载（docker-compose.yml），这里只确保 node_modules 存在
ENV NODE_ENV=development
ENV NEXT_TELEMETRY_DISABLED=1

# 后端地址（容器间通信用服务名）
ENV BACKEND_URL=http://backend:8000

EXPOSE 3000

CMD ["npm", "run", "dev"]
