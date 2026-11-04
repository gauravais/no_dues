import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const distDir = path.resolve(__dirname, '..', 'dist')

if (!fs.existsSync(distDir)) {
  console.error(`[check:leaks] FAILED: dist directory not found at ${distDir}. Run build first.`)
  process.exit(1)
}

const FORBIDDEN_PATTERNS = ['example.edu', 'DEMO2026', 'dev_otp']

function scanDirectory(dir, fileList = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      scanDirectory(fullPath, fileList)
    } else if (entry.isFile()) {
      fileList.push(fullPath)
    }
  }
  return fileList
}

const allFiles = scanDirectory(distDir)
let leakFound = false
let scannedCount = 0

for (const filePath of allFiles) {
  const ext = path.extname(filePath).toLowerCase()
  if (!['.js', '.mjs', '.css', '.html', '.json', '.map', '.txt', '.svg'].includes(ext)) {
    continue
  }

  scannedCount++
  const content = fs.readFileSync(filePath, 'utf-8')
  for (const pattern of FORBIDDEN_PATTERNS) {
    if (content.includes(pattern)) {
      console.error(`[check:leaks] LEAK DETECTED: Found forbidden string "${pattern}" in: ${filePath}`)
      leakFound = true
    }
  }
}

if (leakFound) {
  console.error(`\n[check:leaks] FAILED: Production build in dist/ contains forbidden leak patterns.`)
  process.exit(1)
} else {
  console.log(`[check:leaks] PASSED: No forbidden patterns (${FORBIDDEN_PATTERNS.join(', ')}) found across ${scannedCount} build artifacts in dist/.`)
  process.exit(0)
}
