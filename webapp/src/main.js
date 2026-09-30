import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';

mount(App, { target: document.getElementById('app') });

// Installable (PWA) : le code de l'interface et les polices restent en cache, jamais les données (/api).
if ('serviceWorker' in navigator && import.meta.env.PROD && !import.meta.env.VITE_MOCK) {
  addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
