/**
 * Server-side proxy in front of the enterprise_router API.
 *
 * Why this exists: every client component used to call the router directly
 * with real credentials sourced from NEXT_PUBLIC_* env vars -- the admin
 * secret and every department's API key. Next.js inlines NEXT_PUBLIC_*
 * values into the client JS bundle at build time, so all of those
 * credentials shipped to the browser in plaintext, readable by anyone via
 * view-source. See the Enterprise Deployment Blueprint's critical-path
 * findings.
 *
 * This route runs server-side only. The browser sends an `X-Router-Auth`
 * header naming a ROLE ("admin", "manager", or "agent:<Name>") -- not a
 * secret, just a routing label the client already knew anyway (which
 * department page it's on). This handler resolves the real credential for
 * that role from server-only env vars (never NEXT_PUBLIC_*) and attaches
 * it to the upstream request. Any auth header the client itself sent is
 * never read or forwarded -- only server-resolved credentials reach the
 * router.
 */
import { NextRequest, NextResponse } from 'next/server'

const ROUTER_URL = (process.env.ROUTER_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const ADMIN_SECRET = process.env.ENTERPRISE_ROUTER_ADMIN_SECRET ?? ''

// Same env var names scripts/bootstrap_router_agents.py prints and
// docker-compose.yml's worker services already consume -- one .env entry
// per agent serves both the worker container and this proxy.
const AGENT_KEYS: Record<string, string> = {
  MANAGER: process.env.MANAGER_AGENT_API_KEY ?? '',
  CEO: process.env.CEO_AGENT_API_KEY ?? '',
  PM: process.env.PM_AGENT_API_KEY ?? '',
  Engineering: process.env.ENGINEERING_AGENT_API_KEY ?? '',
  HR: process.env.HR_AGENT_API_KEY ?? '',
  Sales: process.env.SALES_AGENT_API_KEY ?? '',
  Marketing: process.env.MARKETING_AGENT_API_KEY ?? '',
  Finance: process.env.FINANCE_AGENT_API_KEY ?? '',
}

function resolveAuthHeaders(role: string): Record<string, string> {
  if (role === 'admin') return { 'X-Admin-Secret': ADMIN_SECRET }
  if (role === 'manager') return { Authorization: `Bearer ${AGENT_KEYS.MANAGER}`, 'X-Agent-Id': 'MANAGER' }
  if (role.startsWith('agent:')) {
    const name = role.slice('agent:'.length)
    return { Authorization: `Bearer ${AGENT_KEYS[name] ?? ''}`, 'X-Agent-Id': name }
  }
  return {}
}

async function proxy(req: NextRequest, { params }: { params: { path: string[] } }): Promise<NextResponse> {
  const path = '/' + (params.path ?? []).join('/')
  const authHeaders = resolveAuthHeaders(req.headers.get('x-router-auth') ?? '')

  const init: RequestInit = {
    method: req.method,
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    cache: 'no-store',
  }
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    const body = await req.text()
    if (body) init.body = body
  }

  let upstream: Response
  try {
    upstream = await fetch(`${ROUTER_URL}${path}${req.nextUrl.search}`, init)
  } catch {
    return NextResponse.json({ detail: 'Router unreachable' }, { status: 502 })
  }

  const text = await upstream.text()
  return new NextResponse(text, {
    status: upstream.status,
    headers: { 'Content-Type': upstream.headers.get('content-type') ?? 'application/json' },
  })
}

export { proxy as GET, proxy as POST }
