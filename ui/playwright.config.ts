import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev:frontend',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    { name: 'chromium', testMatch: /(?<!touch)(?<!mobile)\.spec\.ts$/, use: { ...devices['Desktop Chrome'] } },
    // A real touch device profile. The map has to be usable under a finger, and
    // that cannot be verified with a mouse-only profile: pointer events carry a
    // different `pointerType`, there is no hover, and only `hasTouch` exposes
    // `page.touchscreen`. Defaults to off so the desktop projects stay fast.
    { name: 'mobile', testMatch: /(touch|mobile)\.spec\.ts/, use: { ...devices['Pixel 7'] } },
  ],
});
