import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const frontendRoot = path.resolve(__dirname, '..')
const srcDir = path.resolve(frontendRoot, 'src')
const indexHtmlPath = path.resolve(frontendRoot, 'index.html')

const FORBIDDEN_RULES = [
  { name: 'demo', regex: /\bdemo\b/i },
  { name: 'FastAPI', regex: /FastAPI/i },
  { name: 'Tailwind', regex: /Tailwind/i },
  { name: 'shadcn', regex: /shadcn/i },
  { name: 'React 19', regex: /React\s*19/i },
  { name: 'synthetic', regex: /synthetic/i },
]

function collectFiles(dir, fileList = []) {
  if (!fs.existsSync(dir)) return fileList
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      collectFiles(fullPath, fileList)
    } else if (entry.isFile()) {
      fileList.push(fullPath)
    }
  }
  return fileList
}

const filesToScan = collectFiles(srcDir)
if (fs.existsSync(indexHtmlPath)) {
  filesToScan.push(indexHtmlPath)
}

let violationsCount = 0
let scannedFilesCount = 0

for (const filePath of filesToScan) {
  const ext = path.extname(filePath).toLowerCase()
  // Scan text-based source and markup files
  if (!['.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.svg', '.json'].includes(ext)) {
    continue
  }

  scannedFilesCount++
  const content = fs.readFileSync(filePath, 'utf-8')

  // Whole-file exemption
  if (content.includes('wording-ok-file')) {
    continue
  }

  const lines = content.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // Line-level exemption
    if (line.includes('wording-ok')) {
      continue
    }

    for (const rule of FORBIDDEN_RULES) {
      if (rule.regex.test(line)) {
        const relPath = path.relative(frontendRoot, filePath).replace(/\\/g, '/')
        console.error(
          `[check:wording] VIOLATION: Forbidden term "${rule.name}" found at ${relPath}:${i + 1}:\n    ${line.trim()}`
        )
        violationsCount++
      }
    }
  }
}

if (violationsCount > 0) {
  console.error(`\n[check:wording] FAILED: Found ${violationsCount} wording violation(s) in src/ and index.html.`)
  process.exit(1)
} else {
  console.log(
    `[check:wording] PASSED: No forbidden wording (demo, FastAPI, Tailwind, shadcn, React 19, synthetic) across ${scannedFilesCount} files in src/ and index.html.`
  )
  process.exit(0)
}
