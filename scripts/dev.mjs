import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "./build.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function loadEnv(file) {
  const full = path.join(root, file);
  if (!existsSync(full)) return;
  for (const line of readFileSync(full, "utf8").split(/\r?\n/)) {
    const match = line.match(/^\s*([^#=\s]+)\s*=\s*(.*)\s*$/);
    if (!match || process.env[match[1]]) continue;
    process.env[match[1]] = match[2].replace(/^["']|["']$/g, "");
  }
}

loadEnv(".env");
loadEnv(".env.local");
build();

const dist = path.join(root, "dist");
const port = Number(process.env.PORT || 3000);

const server = createServer(async (req, res) => {
  const url = new URL(req.url || "/", "http://localhost");
  if (url.pathname === "/api/config") {
    const supabaseUrl = String(process.env.SUPABASE_URL || "").replace(/\/$/, "");
    const key = String(process.env.SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_ANON_KEY || "");
    const publicKey = key.startsWith("sb_secret_") ? "" : key;
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store"
    });
    res.end(JSON.stringify({
      url: supabaseUrl,
      key: publicKey,
      configured: supabaseUrl.startsWith("https://") && publicKey.length > 20
    }));
    return;
  }

  if (url.pathname !== "/" && url.pathname !== "/index.html") {
    res.writeHead(404);
    res.end("Not found");
    return;
  }

  const body = await readFile(path.join(dist, "index.html"));
  res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
  res.end(body);
});

server.listen(port, () => {
  console.log(`KaubanTa running at http://localhost:${port}`);
});
