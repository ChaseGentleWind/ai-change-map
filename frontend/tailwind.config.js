/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // designkit 风格设计 token
        canvas: '#F6F7FA',          // 主背景
        sidebar: '#EDEFF5',          // 侧栏 / 卡片底
        ink: {
          DEFAULT: '#1C1D1F',        // 主标题
          soft: '#17181A',           // 次级
          muted: '#616366',          // 描述
          faint: '#9095A0',          // 极弱
        },
        brand: {
          DEFAULT: '#1890FF',
          50: '#E6F4FF',
          100: '#BAE0FF',
        },
        line: '#E5E7EB',
        selected: 'rgba(0, 31, 92, 0.06)',
      },
      borderRadius: {
        card: '16px',
      },
      boxShadow: {
        hover: '0 8px 24px rgba(15, 23, 42, 0.08)',
      },
      transitionTimingFunction: {
        soft: 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
    },
  },
  plugins: [],
}
