#!/usr/bin/env node
// answer-dump --dump <path> --model <model> --out <path>
// Answers a retrieval dump with any opencode model (TUI or headless), stores answers for evaluate-dump
import { readFile, writeFile, mkdir } from "node:fs/promises"
import { join, dirname } from "node:path"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
const execFileAsync = promisify(execFile)

function parseArgs() {
  const a = process.argv
  const dump = a[a.indexOf("--dump") + 1]
  const model = a[a.indexOf("--model") + 1] || "nvidia/nemotron-3.5-lightning-30b-a3b"
  const out = a[a.indexOf("--out") + 1] || `bench/answers/${dump?.split("/").pop()?.replace(".json","")}-${model.replace(/[\/:]/g,"_")}.json`
  if (!dump) { console.error("Usage: bun run answer-dump --dump <dump.json> --model <model> --out <out.json>"); process.exit(1) }
  return { dump, model, out }
}

const { dump, model, out } = parseArgs()
const questions = JSON.parse(await readFile(dump, "utf-8"))
console.log(`Answering ${questions.length} questions with ${model} → ${out}`)

// Use opencode run as answering harness: we reuse MemoryBench answer phase prompt via direct LLM call
// Simple: for each question, call `opencode run` with context via stdin, or fallback to nvidia API via python
// Here we use python helper that calls the model's API through opencode's auth (nvidia key) or direct

for (let i = 0; i < questions.length; i++) {
  const q = questions[i]
  const context = q.searchResults.slice(0, 10).map(r => r.content).join("\n---\n").slice(0, 6000)
  const prompt = `Context:\n${context}\n\nQuestion: ${q.question}\nAnswer concisely, just the answer.`
  // Write per-question answer via python nvidia call (no extra ingest)
  const py = `
import json, os, sys
from pathlib import Path
import urllib.request, urllib.error
key = json.load(open('/home/rajat/.local/share/opencode/auth.json'))['nvidia']['key']
prompt = open(sys.argv[1]).read()
import json as j, urllib.request as req
data = j.dumps({"model": "nvidia/nemotron-3.5-lightning-30b-a3b", "messages": [{"role":"user","content": prompt}], "max_tokens": 256, "temperature": 0}).encode()
r = req.Request("https://integrate.api.nvidia.com/v1/chat/completions", data=data, headers={"Authorization": f"Bearer {key}", "Content-Type":"application/json"})
try:
    with req.urlopen(r, timeout=30) as resp:
        out = j.load(resp)
        ans = out['choices'][0]['message']['content']
        print(ans)
except Exception as e:
    print(f"ERROR:{e}")
`
  // For opencode-go model, use opencode CLI
  let answer = ""
  if (model.startsWith("opencode")) {
    // Use opencode headless: echo prompt | opencode run -m <model> (proven to hang for gateway models, but try)
    try {
      const { stdout } = await execFileAsync("bash", ["-c", `echo ${JSON.stringify(prompt)} | opencode run -m ${model} --format json 2>&1 | head -c 2000`], { timeout: 40000 })
      answer = stdout.slice(0, 500)
    } catch (e) { answer = `ERROR opencode: ${e.message?.slice(0,200)}` }
  } else {
    const tmp = `/tmp/prompt-${i}.txt`
    await writeFile(tmp, prompt)
    try {
      const { stdout } = await execFileAsync("python3", ["-c", py, tmp], { timeout: 35000 })
      answer = stdout.trim()
    } catch (e) { answer = `ERROR nvidia: ${e.message?.slice(0,200)}` }
  }
  q.hypothesis = answer
  q.answeringModel = model
  if (i % 10 === 0) console.log(`${i}/${questions.length} ${q.questionId} → ${answer.slice(0,80).replace(/\n/g," ")}`)
  // incremental write every 20
  if (i % 20 === 0) {
    await mkdir(dirname(out), { recursive: true })
    await writeFile(out, JSON.stringify(questions, null, 2))
  }
}
await mkdir(dirname(out), { recursive: true })
await writeFile(out, JSON.stringify(questions, null, 2))
console.log(`done → ${out}`)
