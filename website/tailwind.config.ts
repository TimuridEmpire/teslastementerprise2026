import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
        body:    ['IBM Plex Sans', 'system-ui', 'sans-serif'],
        mono:    ['IBM Plex Mono', 'ui-monospace', 'monospace'],
      },
      colors: {
        bg:      '#080808',
        surface: '#0E0E0E',
        card:    '#1A1A1A',
        primary: '#FFFFFF',
        green:   '#5CB88A',
        amber:   '#C8953A',
        red:     '#C85C5C',
        sky:     '#5A8CB8',
        teal:    '#3A9C9C',
        agent: {
          ceo:         '#C8953A',
          product:     '#5A8CB8',
          engineering: '#5CB88A',
          hr:          '#C87A7A',
          sales:       '#7A9CB8',
          marketing:   '#B8905A',
          finance:     '#8CB878',
        },
      },
      borderRadius: {
        card: '12px',
        inner: '8px',
      },
      boxShadow: {
        card: '0 4px 24px rgba(0,0,0,0.5)',
      },
      animation: {
        'fade-up': 'fadeUp 0.35s ease-out',
        'fade-in': 'fadeIn 0.25s ease-out',
      },
      keyframes: {
        fadeUp: {
          '0%':   { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}

export default config
