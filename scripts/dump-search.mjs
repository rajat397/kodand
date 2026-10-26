#!/usr/bin/env node
// dump-search --runId <runId> → bench/retrieval-dump/<runId>.json
// Reads checkpoint.json after search phase, exports question + searchResults
import { readFile, writeFile, mkdir } from "node:fs/promises"
import { existsSync } from "node:fs"
import { join } from "node:path"

const runId = process.argv[process.argv.indexOf("--runId") + 1] || process.env.RUN_ID
if (!runId) { console.error("Usage: bun run dump-search --runId <runId>"); process.exit(1) }

const ckPath = join(process.cwd(), "../memorybench/data/runs", runId, "checkpoint.json")
const altCk = join("/home/rajat/memorybench/data/runs", runId, "checkpoint.json")
const reportPath = join("/home/rajat/memorybench/data/runs", runId, "report.json")
let out = []
if (existsSync(reportPath)) {
  // Report has evaluations with searchResults — best for re-answering same retrieval
  const rep = JSON.parse(await readFile(reportPath, "utf-8"))
  for (const e of rep.evaluations) {
    out.push({
      questionId: e.questionId,
      question: e.question,
      groundTruth: e.groundTruth,
      questionType: e.questionType,
      searchResults: e.searchResults,
      searchDurationMs: e.searchDurationMs,
    })
  }
} else {
  const ckFile = existsSync(ckPath) ? ckPath : altCk
  const ck = JSON.parse(await readFile(ckFile, "utf-8"))
  for (const [qid, q] of Object.entries(ck.questions)) {
    const ph = q.phases.search
    // searchResults may be in resultFile
    if (ph && ph.resultFile && existsSync(ph.resultFile)) {
      try {
        const res = JSON.parse(await readFile(ph.resultFile, "utf-8"))
        out.push({
          questionId: qid,
          question: q.question,
          groundTruth: q.groundTruth,
          questionType: q.questionType,
          searchResults: res.searchResults || res.results || [],
          searchDurationMs: ph.durationMs,
        })
        continue
      } catch {}
    }
    if (!ph || !ph.searchResults) continue
    out.push({
      questionId: qid,
      question: q.question,
      groundTruth: q.groundTruth,
      questionType: q.questionType,
      searchResults: ph.searchResults,
      searchDurationMs: ph.searchResultsDurationMs || q.phases.search.searchDurationMs,
    })
  }
  if (!out.length) console.warn("No searchResults in checkpoint, trying results dir...")
}

const outPath = join(process.cwd(), "bench/retrieval-dump", `${runId}.json`)
await mkdir(join(process.cwd(), "bench/retrieval-dump"), { recursive: true })
await writeFile(outPath, JSON.stringify(out, null, 2))
console.log(`dumped ${out.length} questions with searchResults → ${outPath} (${(JSON.stringify(out).length/1e6).toFixed(1)} MB)`)
