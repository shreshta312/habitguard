/**
 * HabitGuard Chrome Extension — shared configuration.
 *
 * This file is loaded before popup.js (via a <script> tag in popup.html)
 * and before background.js (via importScripts in the service worker).
 *
 * Change the base URL here to point to a different backend environment.
 */
const API_BASE_URL = 'http://127.0.0.1:8000';
