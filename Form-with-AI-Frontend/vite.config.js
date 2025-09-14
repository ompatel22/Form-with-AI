import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite'


export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // This is needed to allow access from ngrok tunnels.
    // Vite's dev server blocks requests from hosts other than localhost by default.
    // The value '.ngrok-free.app' allows all subdomains of ngrok-free.app.
    allowedHosts: ['.ngrok-free.app'],
  },
});