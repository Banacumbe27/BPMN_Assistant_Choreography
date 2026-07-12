export const bpmnAssistantUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Detect if running on hosted version vs local Docker
export const isHostedVersion = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';