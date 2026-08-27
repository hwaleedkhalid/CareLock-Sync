/**
 * Playwright E2E Test Configuration — CareLock Sync Frontend
 *
 * Runs against the live Vite dev server (port 5173) talking to the
 * real FastAPI backend (port 8003). Tests validate that the full
 * stack works end-to-end including lazy-loaded routes and API calls.
 */
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,          // Sequential — tests share auth state
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,                    // Single worker to avoid port conflicts
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 30000,
  expect: { timeout: 10000 },

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
