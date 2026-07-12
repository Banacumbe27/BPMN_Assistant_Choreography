<script>
import ChatInterface from '../components/ChatInterface.vue';
import { markRaw } from 'vue';

const Modeler = window.ChorJSModeler || window.ChorJS;

export default {
  name: 'App',
  components: {
    ChatInterface,
  },
  data() {
    return {
      bpmnXml: '',
      process: null, // Process in JSON format
      bpmnViewer: null,
      snackbar: {
        show: false,
        text: '',
        color: 'success',
      },
    };
  },
  async mounted() {
    this.bpmnViewer = markRaw(
      new Modeler({
        container: this.$refs.canvas,
        keyboard: {
          bindTo: document,
        },
      }),
    );
  },
  beforeUnmount() {
    if (this.bpmnViewer) {
      this.bpmnViewer.destroy();
    }
  },
  methods: {
    showSnackbar(text, color = 'success') {
      this.snackbar.text = text;
      this.snackbar.color = color;
      this.snackbar.show = true;
    },
    clearDiagram() {
      this.bpmnXml = '';
      this.process = null;
      if (typeof this.bpmnViewer?.clear === 'function') {
        this.bpmnViewer.clear();
      }
    },
    async importDiagram(xmlContent) {
      if (!this.bpmnViewer) {
        return;
      }
      console.log('Importing BPMN diagram...', xmlContent);
      const result = await this.bpmnViewer.importXML(xmlContent.toString());
      const { warnings } = result;
      console.log('BPMN diagram imported successfully', warnings);
      this.bpmnViewer.get('canvas').zoom('fit-viewport');
    },
    async handleDrop(event) {
      event.preventDefault(); // Prevent the browser from default file handling
      if (event.dataTransfer.items) {
        for (let i = 0; i < event.dataTransfer.items.length; i++) {
          if (event.dataTransfer.items[i].kind === 'file') {
            const file = event.dataTransfer.items[i].getAsFile();

            if (file.name.endsWith('.bpmn')) {
              const reader = new FileReader();
              reader.onload = async (e) => {
                const xmlContent = e.target.result;
                try {
                  await this.importDiagram(xmlContent);
                  this.bpmnXml = xmlContent;
                  // Imported files are view-only: the assistant only edits
                  // choreographies it generated itself.
                  this.process = null;
                  this.showSnackbar('BPMN file loaded', 'success');
                } catch (err) {
                  console.error('Failed to import BPMN diagram:', err);
                  this.showSnackbar(
                    'There was a problem while loading the BPMN file',
                    'error',
                  );
                }
              };
              reader.readAsText(file);
            }
          }
        }
      }
    },
    async handleBpmnXml(bpmnXmlValue) {
      if (bpmnXmlValue === '') {
        this.clearDiagram();
        return;
      }

      try {
        // Choreographies always arrive already laid out: the backend embeds
        // deterministic DI, since the JS auto-layout service cannot handle
        // choreography diagrams.
        this.bpmnXml = bpmnXmlValue;
        await this.importDiagram(bpmnXmlValue);
      } catch (error) {
        console.error('Error handling BPMN XML:', error);
      }
    },
    async downloadBpmnFile() {
      const { xml } = await this.bpmnViewer.saveXML();
      const blob = new Blob([xml], { type: 'text/xml' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'diagram.bpmn';
      a.click();
    },
    setBpmnJson(value) {
      this.process = value;
    },
  },
};
</script>

<template>
  <div style="display: flex; flex-direction: row; height: 100vh">
    <div class="chat-container">
      <ChatInterface
        @bpmn-xml-received="handleBpmnXml"
        @bpmn-json-received="setBpmnJson"
        @download="downloadBpmnFile"
        :isDownloadReady="!!bpmnXml"
        :process="process"
      />
    </div>
    <div
      ref="canvas"
      class="canvas-container"
      @dragover.prevent
      @drop="handleDrop"
    ></div>
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" :timeout="3000">
      {{ snackbar.text }}
    </v-snackbar>
  </div>
</template>

<style>
#canvas {
  margin: 10px;
}

.chat-container {
  flex: 3;
}

.canvas-container {
  flex: 4;
  border: 2px solid gray;
}

@media (min-width: 1800px) {
  .chat-container {
    flex: 2;
  }
  .canvas-container {
    flex: 5;
  }
}
</style>
