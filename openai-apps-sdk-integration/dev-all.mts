#!/usr/bin/env -S node --enable-source-maps
import { createServer as createHttpServer, request as httpRequest } from "node:http";
import { URL } from "node:url";
import { spawn } from "node:child_process";
import fg from "fast-glob";
import path from "node:path";

const REACT_PORT = 4450;
const PROXY_PORT = 4444;

function escapeHtml(str: string): string {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function detectEntryNames(): string[] {
  const entries = fg.sync("src/**/index.{tsx,jsx}", { dot: false });
  return entries.map((entry) => path.basename(path.dirname(entry)));
}

function startVite(configFile: string, port: number) {
  const child = spawn(
    process.platform === "win32" ? "pnpm.cmd" : "pnpm",
    ["vite", "--config", configFile, "--port", String(port), "--strictPort"],
    {
      stdio: ["ignore", "pipe", "pipe"],
      env: {
        ...process.env,
        VITE_DEV_CLIENT_ORIGIN: `http://localhost:${port}`,
      },
    }
  );

  const prefix = (s: string) => `[react] ${s}`;
  child.stdout.on("data", (d) => process.stdout.write(prefix(d.toString())));
  child.stderr.on("data", (d) => process.stderr.write(prefix(d.toString())));
  child.on("exit", (code) => {
    console.log(`react exited with code ${code}`);
  });
  return child;
}

async function main() {
  const entryNames = detectEntryNames();
  console.log("Detected widget entries:");
  for (const name of entryNames) {
    console.log(`  /${name}.js, /${name}.css`);
  }

  const reactChild = startVite("vite.config.mts", REACT_PORT);

  // Simple proxy to keep legacy 4444 port and allow missing base prefix
  const server = createHttpServer((req, res) => {
    const urlObj = new URL(req.url || "/", `http://localhost:${PROXY_PORT}`);

    if (urlObj.pathname === "/") {
      res.setHeader("content-type", "text/html; charset=utf-8");
      res.end(
        `<!doctype html><meta charset=utf-8><title>ecosystem_ui dev</title>` +
          `<style>body{font:13px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Inter,Helvetica,Arial,sans-serif;padding:16px}</style>` +
          `<h1>ecosystem_ui dev proxy (4444)</h1>` +
          `<p>Entries:</p>` +
          `<ul>` +
          entryNames
            .map((n) => { const s = escapeHtml(n); return `<li><a href="/${s}.js">/${s}.js</a></li>`; })
            .join("") +
          `</ul>`
      );
      return;
    }

    const targetUrl = new URL(urlObj.pathname + urlObj.search, `http://localhost:${REACT_PORT}`);
    const opts = {
      method: req.method,
      headers: {
        ...req.headers,
        host: targetUrl.host,
        origin: `${targetUrl.protocol}//${targetUrl.host}`,
        "access-control-allow-origin": "*",
      },
    };

    const proxyReq = httpRequest(targetUrl, opts, (proxyRes) => {
      for (const [k, v] of Object.entries(proxyRes.headers)) {
        if (v !== undefined) res.setHeader(k, v as any);
      }
      res.setHeader("access-control-allow-origin", "*");
      res.writeHead(proxyRes.statusCode || 200, proxyRes.statusMessage);
      proxyRes.pipe(res);
    });

    proxyReq.on("error", (err) => {
      res.statusCode = 502;
      res.setHeader("content-type", "text/plain");
      res.end(`Proxy error: ${escapeHtml(err.message)}`);
    });

    if (req.readable) req.pipe(proxyReq);
    else proxyReq.end();
  });

  server.listen(PROXY_PORT, () => {
    console.log(`Proxy listening on http://localhost:${PROXY_PORT}`);
  });

  const shutdown = () => {
    try {
      reactChild.kill();
    } catch {}
    try {
      server.close();
    } catch {}
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

