/**
 * 静态文件代理路由：将 /static/* 请求转发到后端 http://localhost:8000/static/*
 *
 * 解决封面图片等静态资源在前端 404 的问题：
 * 后端 cover_url 存储为 /static/covers/xxx.png，前端 <img src="/static/covers/xxx.png">
 * 原先 /static/* 不在 /api/* 代理范围内，导致 404。
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
  const path = req.nextUrl.pathname;
  const search = req.nextUrl.search;
  const targetUrl = `${BACKEND_URL}${path}${search}`;

  try {
    const resp = await fetch(targetUrl, {
      headers: { "accept": req.headers.get("accept") || "*" },
    });

    if (!resp.ok) {
      return new NextResponse(null, { status: resp.status });
    }

    const contentType = resp.headers.get("content-type") || "application/octet-stream";
    const cacheControl = resp.headers.get("cache-control") || "public, max-age=86400";
    const body = await resp.arrayBuffer();
    return new NextResponse(body, {
      status: 200,
      headers: {
        "content-type": contentType,
        "cache-control": cacheControl,
        "access-control-allow-origin": "*",
      },
    });
  } catch (err: any) {
    return NextResponse.json(
      { detail: `静态文件代理失败: ${err.message}` },
      { status: 502 }
    );
  }
}
