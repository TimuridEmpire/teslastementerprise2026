'use client'

import { useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'

export default function OnboardingGuard() {
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (pathname === '/onboarding') return
    const done = localStorage.getItem('kanosei_onboarded')
    if (!done) router.replace('/onboarding')
  }, [pathname, router])

  return null
}
