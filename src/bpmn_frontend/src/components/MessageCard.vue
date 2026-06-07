<template>
  <transition name="fade" appear>
    <div class="message-container" :class="`message-${role}`">
      <div class="message-bubble">
        <div class="message-role">
          <b>{{ roleDisplay }}</b>
        </div>
        <!-- Display images above the text content -->
        <div v-if="images && images.length > 0" class="message-images">
          <img
            v-for="(image, index) in images"
            :key="index"
            :src="image.preview"
            :alt="image.name"
            class="message-image"
          />
        </div>
        <div class="message-content" v-html="sanitizedContent"></div>
      </div>
    </div>
  </transition>
</template>

<script>
import DOMPurify from 'dompurify';

export default {
  props: {
    role: String,
    content: String,
    images: {
      type: Array,
      default: () => [],
    },
  },
  computed: {
    roleDisplay() {
      return this.role === 'user' ? 'You' : 'BPMN Assistant';
    },
    sanitizedContent() {
      const formattedContent = (this.content || '')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n- /g, '<br>• ')
        .replace(/\n/g, '<br>');
      return DOMPurify.sanitize(formattedContent, {
        ALLOWED_TAGS: ['br', 'strong'],
        ALLOWED_ATTR: [],
      });
    },
  },
};
</script>

<style scoped>
.fade-enter-active {
  transition: opacity 0.5s ease-out;
}

.fade-enter-from {
  opacity: 0;
}

.fade-enter-to {
  opacity: 1;
}

.fade-enter-active {
  transition: opacity 0.5s ease-out, transform 0.3s ease-out;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-enter-to {
  opacity: 1;
  transform: translateY(0);
}

.message-container {
  display: flex;
  margin-bottom: 12px;
  max-width: 85%;
}

.message-user {
  justify-content: flex-end;
  margin-left: auto;
  margin-right: 8px;
}

.message-assistant {
  justify-content: flex-start;
  margin-left: 8px;
  margin-right: auto;
}

.message-bubble {
  padding: 10px 15px;
  border-radius: 18px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  word-wrap: break-word;
  position: relative;
}

.message-user .message-bubble {
  background-color: #e1f5fe;
  color: #333;
  border-bottom-right-radius: 4px;
}

.message-assistant .message-bubble {
  background-color: #f1f1f1;
  color: #333;
  border-bottom-left-radius: 4px;
}

.message-role {
  font-size: 0.8em;
  color: #555;
  margin-bottom: 4px;
}

.message-content {
  font-size: 1em;
  line-height: 1.4;
}

.message-content ::v-deep(strong) {
  font-weight: bold;
}

.message-content ::v-deep(br) {
  content: '';
  display: block;
  margin-bottom: 0.2em;
}

.message-images {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.message-image {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  object-fit: cover;
}
</style>
