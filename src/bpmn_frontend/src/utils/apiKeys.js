/**
 * Utility functions for managing API keys in sessionStorage
 */

import { isHostedVersion } from '../config';

const STORAGE_KEY = 'bpmn_api_keys';

/**
 * Get API keys from sessionStorage
 * @returns {Object|null} Object containing API keys (openai_api_key, anthropic_api_key, etc.), or null if on local version
 */
export function getApiKeys() {
  // On local Docker version, API keys come from .env file on backend
  if (!isHostedVersion) {
    return null;
  }

  const stored = sessionStorage.getItem(STORAGE_KEY);
  if (!stored) {
    return {};
  }

  try {
    return JSON.parse(stored);
  } catch (e) {
    console.error('Failed to parse stored API keys', e);
    return {};
  }
}

/**
 * Check if any API keys are stored
 * @returns {boolean}
 */
export function hasApiKeys() {
  const keys = getApiKeys();
  return Object.keys(keys).length > 0;
}

/**
 * Save API keys to sessionStorage
 * @param {Object} keys - Object containing API keys
 */
export function saveApiKeys(keys) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(keys));
}

/**
 * Clear all API keys from sessionStorage
 */
export function clearApiKeys() {
  sessionStorage.removeItem(STORAGE_KEY);
}
