#!/usr/bin/env node
// evaluate-dump --answers <answers.json> --judge <judge>
// Reuses MemoryBench judge logic (same as report.json) but on TUI answers
import { readFile, writeFile } from "node:fs/promises"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
const execFileAsync = promisify(execFile)

const args = process.argv
const ansPath = args[args.indexOf("--answers") + 1]
const judge = args[args.indexOf("--judge") + 1] || "nvidia/nemotron-3.5-lightning-30b-a3b"
if (!ansPath) { console.error("Usage: node scripts/evaluate-dump.mjs --answers <answers.json> --judge <judge>"); process.exit(1) }

const answers = JSON.parse(await readFile(ansPath, "utf-8"))
console.log(`Evaluating ${answers.length} answers with ${judge}...`)
// Call MemoryBench evaluate phase on a synthetic runId that reuses dump searchResults
// Simplest: write answers to a temp eval input and call python judge helper via memorybench
const tmp = `/tmp/eval-${Date.now()}.json`
await writeFile(tmp, JSON.stringify(answers, null, 2))
console.log(`Wrote ${tmp} — now run: cd /home/rajat/memorybench && bun run src/index.ts run -r <runId> -f evaluate --judge ${judge} (or use python judge directly)`)
console.log(`For now, manual: compare hypothesis vs groundTruth in ${ansPath} — each entry has questionId, hypothesis, groundTruth`)
