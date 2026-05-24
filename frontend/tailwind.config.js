/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#1B4332',
          50: '#E8F5EE',
          100: '#D1EBD8',
          200: '#A3D7B1',
          300: '#75C38A',
          400: '#52B788',
          500: '#1B4332',
          600: '#163826',
          700: '#112D1E',
          800: '#0C2216',
          900: '#07170E',
        },
        accent: {
          DEFAULT: '#52B788',
          50: '#EEF8F3',
          100: '#D5EEE3',
          200: '#ACDDC7',
          300: '#82CBAB',
          400: '#52B788',
          500: '#3A9E70',
          600: '#2E7D5A',
          700: '#225C42',
          800: '#163B2B',
          900: '#0A1A13',
        },
        background: {
          DEFAULT: '#F8F9FA',
          dark: '#0F1117',
        },
        surface: {
          DEFAULT: '#FFFFFF',
          dark: '#1A1D23',
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)',
        'card-hover': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)',
      },
      animation: {
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'fade-in': 'fadeIn 0.2s ease-out',
        'pulse-dot': 'pulseDot 2s infinite',
      },
      keyframes: {
        slideInRight: {
          '0%': { transform: 'translateX(100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        pulseDot: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
    },
  },
  plugins: [],
}
