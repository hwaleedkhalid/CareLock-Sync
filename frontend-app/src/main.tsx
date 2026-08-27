import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Global error handler for debugging
window.addEventListener('error', (e) => {
  console.error('[GLOBAL_ERROR]', e.error);
});

window.addEventListener('unhandledrejection', (e) => {
  console.error('[UNHANDLED_PROMISE]', e.reason);
});

console.log('[INIT] React app starting...');

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

console.log('[INIT] React app rendered');
