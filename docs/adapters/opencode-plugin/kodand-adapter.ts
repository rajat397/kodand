import { execFile } from "node:child_process"
import { join } from "node:path"

// kodand adapter for opencode. Per-session memory via stable per-repo store dirs.
// See ../README.md for the contract.
const PIPE = process.env.KODAND_RECALL_URL // e.g. 127.0.0.1:8766
const LAYA = process.env.KODAND_LAYA_URL
const KILL = process.env.KODAND_BASELINE === "1"

const repoDir = (why = "opencode") => join(process.cwd(), ".kodand", `repo-${why}`)

function run(args: string[], stdin?: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const p = KILL || !stdin ? execFile("kodand", args, { timeout: 120_000, maxBuffer: 1e6 },
      (e, o, er) => (e && !o ? reject(e) : resolve(o))) : null
    if (!p) return
    if (stdin) p.stdin!.end(stdin)
  })
}

async function recallViaDaemon(query: string, limit = 10): Promise<any[]> {
  const net = await import("node:net")
  const [host, port] = PIPE!.replace(/^\w+:\/\//, "").split(":")
  return new Promise((resolve, reject) => {
    const s = net.createConnection({ host, port: +port, timeout: 10_000 }, () => {
      s.setTimeout(0); s.setKeepAlive(true, 30_000)
      s.write(JSON.stringify({ repo: repoDir(), query, k: limit }) + "\n")
    })
    let buf = ""
    s.on("data", d => {
      buf += String(d)
      const i = buf.indexOf("\n")
      if (i === -1) return
      s.end()
      try {
        const r = JSON.parse(buf.slice(0, i))
        r.error ? reject(new Error(r.error)) : resolve(r.rows)
      } catch (e) { reject(e as Error) }
    })
    s.on("error", e => reject(e)); s.on("timeout", () => { s.destroy(); reject(new Error("recalld timeout")) })
  })
}

export async function recall(query: string, limit = 10): Promise<any[]> {
  if (PIPE) return recallViaDaemon(query, limit)
  const out = await run(
    ["recall", "--repo", repoDir(), "--query", query, "--limit", String(limit), "--json"]
  )
  return JSON.parse(out.trim() || "[]")
}

// Laya session-rerank is opt-in per call: session-mode keeps whole sessions' context.
export async function recallRanked(query: string, limit = 10) {
  const chunks = await recall(query, Math.max(limit, 16))
  if (KILL || !LAYA) return chunks
  const net = await import("node:net")
  const [host, port] = LAYA!.replace(/^\w+:\/\//, "").split(":")
  return new Promise((resolve, reject) => {
    const s = net.createConnection({ host, port: +port, timeout: 10_000 }, () => {
      s.setTimeout(0)
      s.write(JSON.stringify({ query, chunks, keep_chunks: limit, mode: "sessions" }) + "\n")
    })
    let buf = ""
    s.on("data", d => {
      buf += String(d)
      const i = buf.indexOf("\n")
      if (i === -1) return
      s.end()
      const r = JSON.parse(buf.slice(0, i))
      r.error ? reject(new Error(r.error)) : resolve(r.kept)
    })
    s.on("error", reject); s.on("timeout", () => { s.destroy(); reject(new Error("rerank-serve timeout")) })
  })
}

// write a memory; never auto: the caller decides what is worth storing
export async function remember(content: string, locator?: string) {
  await run(["remember", "--repo", repoDir(), "--content", content,
             ...(locator ? ["--locator", locator] : [])])
}

export default {
  scholar: { recall, recallRanked, remember, repoDir },
}
