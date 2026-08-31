/**
 * memory.ts — client-side session persistence (cookies + localStorage) and
 * downloadable PDF report assembly for the enterprise dashboard.
 *
 * ── Storage ─────────────────────────────────────────────────────────────
 *  - localStorage: non-sensitive UI/report state (e.g. "when was the report
 *    last generated"). Plain JSON, no encryption — nothing here is a secret.
 *  - cookies: small session-scoped values. Anything sensitive (the admin
 *    secret / manager API key a user pastes into Settings) is AES-GCM
 *    encrypted before being written to the cookie, using a per-browser key
 *    kept in localStorage.
 *
 *    Caveat: this raises the bar above "read it in the cookie devtools
 *    panel" or "another same-origin script grep'ing document.cookie", but
 *    it is NOT a server-side security boundary — the decryption key lives
 *    in localStorage on the same origin, so any script with page access can
 *    still recover it. Real secrets belong in httpOnly server-set cookies;
 *    this is the best available option for a purely static, backend-less
 *    client page that still wants "not plaintext at rest".
 *
 * ── PDF report ──────────────────────────────────────────────────────────
 *  Pulls every artifact from the enterprise_router `/artifacts` API,
 *  aggregates them into one Markdown document (with a deterministic
 *  executive summary), then renders that Markdown to PDF using jsPDF's text
 *  primitives directly — never via html2canvas/DOM screenshotting.
 *
 *  That's what fixes "HTML to PDF rendering is inconsistent": a
 *  screenshot-based export bakes in whatever fonts/zoom/layout the browser
 *  happened to use at that moment, so the same report can come out
 *  differently between runs or machines. Going through one deterministic
 *  markdown -> block -> PDF-text pipeline makes the output reproducible
 *  regardless of how any individual artifact happens to be formatted.
 */

import jsPDF from 'jspdf'
import { api } from './api'
import type { ApiArtifact } from './api-types'

// ───────────────────────────── localStorage ────────────────────────────────

const LS_PREFIX = 'brain:'

export function setLocalItem<T>(key: string, value: T): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(LS_PREFIX + key, JSON.stringify(value))
  } catch {
    // private browsing / storage quota — non-fatal
  }
}

export function getLocalItem<T>(key: string): T | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(LS_PREFIX + key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

export function removeLocalItem(key: string): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(LS_PREFIX + key)
  } catch {
    // ignore
  }
}

// ─────────────────────────────── Cookies ───────────────────────────────────

export function setCookie(name: string, value: string, days = 7): void {
  if (typeof document === 'undefined') return
  const expires = new Date(Date.now() + days * 86_400_000).toUTCString()
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`
}

export function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

export function deleteCookie(name: string): void {
  if (typeof document === 'undefined') return
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
}

// ───────────────────────── Encryption (AES-GCM) ────────────────────────────

const DEVICE_KEY_ITEM = 'device-key'

function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  bytes.forEach((b) => (binary += String.fromCharCode(b)))
  return btoa(binary)
}

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}

// TypeScript's DOM lib types typed-array buffers as `ArrayBufferLike`
// (which includes `SharedArrayBuffer`) while `BufferSource`-consuming Web
// Crypto APIs require a concrete `ArrayBuffer`. Every array here is a plain
// browser-created Uint8Array (never backed by a SharedArrayBuffer), so this
// narrows the type without changing anything at runtime.
function asBufferSource(bytes: Uint8Array): BufferSource {
  return bytes as unknown as BufferSource
}

async function getOrCreateDeviceKey(): Promise<CryptoKey> {
  const existing = getLocalItem<string>(DEVICE_KEY_ITEM)
  if (existing) {
    return crypto.subtle.importKey('raw', asBufferSource(base64ToBytes(existing)), 'AES-GCM', true, [
      'encrypt',
      'decrypt',
    ])
  }
  const key = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, [
    'encrypt',
    'decrypt',
  ])
  const exported = await crypto.subtle.exportKey('raw', key)
  setLocalItem(DEVICE_KEY_ITEM, bytesToBase64(new Uint8Array(exported)))
  return key
}

async function encrypt(plaintext: string): Promise<string> {
  const key = await getOrCreateDeviceKey()
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: asBufferSource(iv) },
    key,
    asBufferSource(new TextEncoder().encode(plaintext)),
  )
  const combined = new Uint8Array(iv.length + ciphertext.byteLength)
  combined.set(iv, 0)
  combined.set(new Uint8Array(ciphertext), iv.length)
  return bytesToBase64(combined)
}

async function decrypt(encoded: string): Promise<string | null> {
  try {
    const key = await getOrCreateDeviceKey()
    const combined = base64ToBytes(encoded)
    const iv = combined.slice(0, 12)
    const ciphertext = combined.slice(12)
    const plaintext = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: asBufferSource(iv) },
      key,
      asBufferSource(ciphertext),
    )
    return new TextDecoder().decode(plaintext)
  } catch {
    return null
  }
}

/** Encrypt `value` and store it in a cookie — use for sensitive values. */
export async function setSecureCookie(name: string, value: string, days = 7): Promise<void> {
  setCookie(name, await encrypt(value), days)
}

/** Read + decrypt a cookie written by {@link setSecureCookie}. */
export async function getSecureCookie(name: string): Promise<string | null> {
  const raw = getCookie(name)
  return raw ? decrypt(raw) : null
}

// ───────────────── Concrete use: persisted admin credentials ──────────────
//
// The Settings page lets a user paste the router admin secret / manager API
// key. Previously "Save" only flashed a confirmation and never actually
// persisted anything — a refresh silently reverted to the build-time env
// var. These helpers make Save real: the values survive reloads (encrypted
// at rest in a cookie) and `api.ts` consults an in-memory cache seeded from
// them at startup, falling back to the env var when nothing is saved.

export const ADMIN_SECRET_COOKIE = 'brain_admin_secret'
export const MANAGER_KEY_COOKIE = 'brain_manager_key'

let cachedAdminSecret: string | null = null
let cachedManagerKey: string | null = null

export function getCachedAdminSecret(): string | null {
  return cachedAdminSecret
}

export function getCachedManagerKey(): string | null {
  return cachedManagerKey
}

/** Load any previously-saved credentials into the in-memory cache. Call once on app start. */
export async function initCredentialsFromCookies(): Promise<void> {
  const [admin, manager] = await Promise.all([
    getSecureCookie(ADMIN_SECRET_COOKIE),
    getSecureCookie(MANAGER_KEY_COOKIE),
  ])
  cachedAdminSecret = admin
  cachedManagerKey = manager
}

export async function saveAdminSecret(secret: string): Promise<void> {
  await setSecureCookie(ADMIN_SECRET_COOKIE, secret)
  cachedAdminSecret = secret
}

export async function saveManagerKey(key: string): Promise<void> {
  await setSecureCookie(MANAGER_KEY_COOKIE, key)
  cachedManagerKey = key
}

export function clearSavedCredentials(): void {
  deleteCookie(ADMIN_SECRET_COOKIE)
  deleteCookie(MANAGER_KEY_COOKIE)
  cachedAdminSecret = null
  cachedManagerKey = null
}

// ───────────────────────── PDF report assembly ─────────────────────────────

async function fetchAllArtifactsWithContent(limit: number): Promise<ApiArtifact[]> {
  const list = await api.artifacts.list(undefined, limit)
  return Promise.all(
    list.map(async (a) => {
      try {
        return await api.artifacts.get(a.artifact_id)
      } catch {
        return a
      }
    }),
  )
}

function stripLeadingTitle(markdown: string, title: string): string {
  const lines = markdown.split(/\r?\n/)
  if (lines[0]?.trim() === `# ${title}`) {
    return lines.slice(1).join('\n').replace(/^\s+/, '')
  }
  return markdown
}

function summarizeArtifacts(artifacts: ApiArtifact[]): string {
  if (artifacts.length === 0) return '_No artifacts have been produced yet._'

  const byAgent = new Map<string, ApiArtifact[]>()
  const byType = new Map<string, number>()
  for (const a of artifacts) {
    byAgent.set(a.agent_name, [...(byAgent.get(a.agent_name) ?? []), a])
    byType.set(a.artifact_type, (byType.get(a.artifact_type) ?? 0) + 1)
  }

  const lines: string[] = []
  lines.push(`Total artifacts: ${artifacts.length} across ${byAgent.size} agent(s).`)
  lines.push('')
  lines.push('### By agent')
  for (const [agent, list] of Array.from(byAgent.entries()).sort((a, b) => b[1].length - a[1].length)) {
    const latest = list[0]
    lines.push(
      `- ${agent} — ${list.length} artifact(s); most recent: "${latest.title}" (${latest.artifact_type}, ${latest.created_at})`,
    )
  }
  lines.push('')
  lines.push('### By type')
  for (const [type, count] of Array.from(byType.entries()).sort((a, b) => b[1] - a[1])) {
    lines.push(`- ${type}: ${count}`)
  }
  return lines.join('\n')
}

function buildAggregateMarkdown(artifacts: ApiArtifact[]): string {
  const sorted = [...artifacts].sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
  const parts: string[] = [
    '# Enterprise Artifact Report',
    '',
    `_Generated ${new Date().toISOString()}_`,
    '',
    '## Executive Summary',
    '',
    summarizeArtifacts(sorted),
    '',
    '---',
    '',
    '## Artifacts',
    '',
  ]
  for (const artifact of sorted) {
    parts.push(`### ${artifact.title}`)
    parts.push('')
    parts.push(`Agent: ${artifact.agent_name}`)
    parts.push(`Type: ${artifact.artifact_type}`)
    parts.push(`Created: ${artifact.created_at}`)
    parts.push('')
    parts.push(stripLeadingTitle(artifact.content ?? '_(content unavailable)_', artifact.title))
    parts.push('')
    parts.push('---')
    parts.push('')
  }
  return parts.join('\n')
}

// ── Markdown -> block model (deliberately simple, not full CommonMark) ──
// Every artifact is produced by the same Python-side template, so a small,
// deterministic parser covering headings/lists/code/rules/paragraphs is
// enough to render all of them identically every time.

type Block =
  | { type: 'h1' | 'h2' | 'h3'; text: string }
  | { type: 'p'; text: string }
  | { type: 'li'; text: string }
  | { type: 'code'; text: string }
  | { type: 'hr' }
  | { type: 'blank' }

function parseMarkdownToBlocks(markdown: string): Block[] {
  const blocks: Block[] = []
  let inCode = false
  let codeBuf: string[] = []

  for (const rawLine of markdown.split(/\r?\n/)) {
    const line = rawLine.replace(/\s+$/, '')

    if (line.trim().startsWith('```')) {
      if (inCode) {
        blocks.push({ type: 'code', text: codeBuf.join('\n') })
        codeBuf = []
      }
      inCode = !inCode
      continue
    }
    if (inCode) {
      codeBuf.push(rawLine)
      continue
    }
    if (/^-{3,}$/.test(line.trim())) {
      blocks.push({ type: 'hr' })
    } else if (line.startsWith('### ')) {
      blocks.push({ type: 'h3', text: line.slice(4) })
    } else if (line.startsWith('## ')) {
      blocks.push({ type: 'h2', text: line.slice(3) })
    } else if (line.startsWith('# ')) {
      blocks.push({ type: 'h1', text: line.slice(2) })
    } else if (/^[-*]\s+/.test(line.trim())) {
      blocks.push({ type: 'li', text: line.trim().replace(/^[-*]\s+/, '') })
    } else if (line.trim() === '') {
      blocks.push({ type: 'blank' })
    } else {
      blocks.push({ type: 'p', text: line })
    }
  }
  return blocks
}

const PAGE_WIDTH = 595.28 // A4, points
const PAGE_HEIGHT = 841.89
const MARGIN = 48
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2

function renderBlocksToPdf(doc: jsPDF, blocks: Block[]): void {
  let y = MARGIN

  const ensureSpace = (needed: number) => {
    if (y + needed > PAGE_HEIGHT - MARGIN) {
      doc.addPage()
      y = MARGIN
    }
  }

  const writeLines = (lines: string[], size: number, style: 'normal' | 'bold', gapAfter: number, lineHeight: number) => {
    doc.setFont('helvetica', style)
    doc.setFontSize(size)
    for (const line of lines) {
      ensureSpace(lineHeight)
      doc.text(line, MARGIN, y)
      y += lineHeight
    }
    y += gapAfter
  }

  for (const block of blocks) {
    switch (block.type) {
      case 'h1':
        writeLines(doc.splitTextToSize(block.text, CONTENT_WIDTH), 18, 'bold', 10, 22)
        break
      case 'h2':
        writeLines(doc.splitTextToSize(block.text, CONTENT_WIDTH), 14, 'bold', 8, 17)
        break
      case 'h3':
        writeLines(doc.splitTextToSize(block.text, CONTENT_WIDTH), 12, 'bold', 6, 15)
        break
      case 'li':
        writeLines(doc.splitTextToSize(`•  ${block.text}`, CONTENT_WIDTH - 12), 10.5, 'normal', 2, 13)
        break
      case 'code': {
        doc.setFont('courier', 'normal')
        doc.setFontSize(9)
        for (const line of block.text.split('\n')) {
          for (const wrapped of doc.splitTextToSize(line || ' ', CONTENT_WIDTH)) {
            ensureSpace(12)
            doc.text(wrapped, MARGIN, y)
            y += 12
          }
        }
        y += 6
        break
      }
      case 'hr':
        ensureSpace(10)
        doc.setDrawColor(180)
        doc.line(MARGIN, y, PAGE_WIDTH - MARGIN, y)
        y += 10
        break
      case 'blank':
        y += 6
        break
      case 'p':
      default:
        writeLines(doc.splitTextToSize(block.text, CONTENT_WIDTH), 10.5, 'normal', 4, 13)
        break
    }
  }
}

/** Fetch every artifact and render the aggregated report to an in-memory jsPDF document. */
export async function generateArtifactsReportPdf(limit = 200): Promise<jsPDF> {
  const artifacts = await fetchAllArtifactsWithContent(limit)
  const blocks = parseMarkdownToBlocks(buildAggregateMarkdown(artifacts))
  const doc = new jsPDF({ unit: 'pt', format: 'a4' })
  renderBlocksToPdf(doc, blocks)
  return doc
}

/** Generate the report and trigger a browser download. */
export async function downloadArtifactsReportPdf(limit = 200): Promise<void> {
  const doc = await generateArtifactsReportPdf(limit)
  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  doc.save(`enterprise-artifact-report-${stamp}.pdf`)
  setLocalItem('lastReportGeneratedAt', new Date().toISOString())
}

export function getLastReportGeneratedAt(): string | null {
  return getLocalItem<string>('lastReportGeneratedAt')
}
