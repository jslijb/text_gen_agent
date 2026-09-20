/**
 * API 代理路由：将 /api/* 请求转发到后端 http://localhost:8000/api/*
 *
 * 替代 next.config.ts 的 rewrites，原因：
 * - rewrites 底层 http-proxy 默认 30 秒超时
 * - LLM 生成梗概/标题需 60+ 秒，导致 ECONNRESET
 * - 自定义代理设置 5 分钟超时，避免长耗时 API 失败
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const PROXY_TIMEOUT_MS = 300_000; // 5 分钟

async function proxyRequest(req: NextRequest, method: string) {
  const path = req.nextUrl.pathname.replace(/^\/api/, "");
  const search = req.nextUrl.search;
  const targetUrl = `${BACKEND_URL}/api${path}${search}`;

  // 转发请求头（排除 host，避免后端拒绝）
  const headers = new Headers(req.headers);
  headers.delete("host");

  // 获取请求体（GET/DELETE 无 body）
  let body: BodyInit | null = null;
  if (method !== "GET" && method !== "HEAD") {
    body = await req.text();
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);

  try {
    const resp = await fetch(targetUrl, {
      method,
      headers,
      body,
      signal: controller.signal,
    });

    // 转发响应
    const respHeaders = new Headers(resp.headers);
    // 移除 transfer-encoding，让 NextResponse 自动处理
    respHeaders.delete("transfer-encoding");
    const respBody = await resp.arrayBuffer();
    return new NextResponse(respBody, {
      status: resp.status,
      statusText: resp.statusText,
      headers: respHeaders,
    });
  } catch (err: any) {
    if (err.name === "AbortError") {
      return NextResponse.json(
        { detail: `后端响应超时（${PROXY_TIMEOUT_MS / 1000}秒）` },
        { status: 504 }
      );
    }
    return NextResponse.json(
      { detail: `代理请求失败: ${err.message}` },
      { status: 502 }
    );
  } finally {
    clearTimeout(timer);
  }
}

export async function GET(req: NextRequest) {
  return proxyRequest(req, "GET");
}

export async function POST(req: NextRequest) {
  return proxyRequest(req, "POST");
}

export async function PUT(req: NextRequest) {
  return proxyRequest(req, "PUT");
}

export async function DELETE(req: NextRequest) {
  return proxyRequest(req, "DELETE");
}

export async function PATCH(req: NextRequest) {
  return proxyRequest(req, "PATCH");
}
