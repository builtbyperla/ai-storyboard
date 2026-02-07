/*
 * AudioWorklet Processor for 16kHz PCM Audio
 * Converts Float32 audio samples to Int16 PCM and chunks into 0.1 second segments
 */

class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = [];
    this.chunkSize = 1600; // 0.1 seconds at 16kHz (16000 samples/sec * 0.1 sec)
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];

    // If no input, return true to keep processor alive
    if (!input || !input[0]) {
      return true;
    }

    const inputChannel = input[0]; // Get first channel (mono)

    // Convert Float32 samples to Int16 PCM
    for (let i = 0; i < inputChannel.length; i++) {
      // Clamp to [-1, 1] range and convert to Int16 [-32768, 32767]
      const sample = Math.max(-1, Math.min(1, inputChannel[i]));
      const pcmSample = Math.round(sample * 32767);
      this.buffer.push(pcmSample);

      // When we have a full chunk, send it
      if (this.buffer.length >= this.chunkSize) {
        const chunk = new Int16Array(this.buffer.splice(0, this.chunkSize));
        this.port.postMessage(chunk.buffer, [chunk.buffer]);
      }
    }

    return true; // Keep processor alive
  }
}

registerProcessor('pcm-processor', PCMProcessor);
