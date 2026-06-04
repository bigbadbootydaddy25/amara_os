'use client';

import { useEffect, useRef, useState } from 'react';

const FLUSH_INTERVAL_MS = 4000;
const CHUNK_TIMESLICE_MS = 200;

async function detectBlackholeDevice(): Promise<string | null> {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    const match = devices.find(
      (d) => d.kind === 'audioinput' && /blackhole/i.test(d.label),
    );
    return match?.deviceId ?? null;
  } catch {
    return null;
  }
}

async function transcribeBlob(blob: Blob, signal: AbortSignal): Promise<string> {
  const formData = new FormData();
  formData.append('audio', blob, 'audio.webm');

  const response = await fetch('/api/transcribe', {
    method: 'POST',
    body: formData,
    signal,
  });

  if (!response.ok) {
    throw new Error('Transcription failed');
  }

  const payload = (await response.json()) as { transcript?: string };
  return payload.transcript?.trim() ?? '';
}

export interface UseCallCaptureOptions {
  enabled: boolean;
  onTranscript: (text: string) => void;
  onError: (message: string) => void;
}

export function useCallCapture({ enabled, onTranscript, onError }: UseCallCaptureOptions) {
  const [isCapturing, setIsCapturing] = useState(false);
  const [deviceLabel, setDeviceLabel] = useState('');
  const onTranscriptRef = useRef(onTranscript);
  const onErrorRef = useRef(onError);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let active = true;
    let stream: MediaStream | null = null;
    let recorder: MediaRecorder | null = null;
    let flushTimer: number | null = null;
    const abortController = new AbortController();
    const pending: Blob[] = [];

    const flush = async () => {
      const chunks = pending.splice(0);
      if (chunks.length === 0 || !active) return;

      const blob = new Blob(chunks, { type: 'audio/webm' });
      try {
        const text = await transcribeBlob(blob, abortController.signal);
        if (text && active) {
          onTranscriptRef.current(text);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return;
        console.error('[CallCapture] transcription error:', error);
      }
    };

    (async () => {
      try {
        const deviceId = await detectBlackholeDevice();
        if (!active) return;

        const audioConstraints: MediaTrackConstraints = {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        };
        if (deviceId) {
          audioConstraints.deviceId = { exact: deviceId };
        }

        stream = await navigator.mediaDevices.getUserMedia({ audio: audioConstraints });
        if (!active) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        const track = stream.getAudioTracks()[0];
        setDeviceLabel(track?.label ?? 'System audio');

        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm';

        recorder = new MediaRecorder(stream, { mimeType });
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) pending.push(e.data);
        };
        recorder.start(CHUNK_TIMESLICE_MS);

        setIsCapturing(true);

        flushTimer = window.setInterval(() => {
          void flush();
        }, FLUSH_INTERVAL_MS);
      } catch (error) {
        if (!active) return;
        const message = error instanceof Error ? error.message : 'Call capture failed';
        onErrorRef.current(
          /permission|denied|notallowed/i.test(message)
            ? 'Microphone permission needed for call capture.'
            : 'Unable to capture call audio. Ensure BlackHole 2ch is set up.',
        );
      }
    })();

    return () => {
      active = false;
      abortController.abort();
      if (flushTimer !== null) clearInterval(flushTimer);
      try { recorder?.stop(); } catch {}
      stream?.getTracks().forEach((t) => t.stop());
      setIsCapturing(false);
      setDeviceLabel('');
    };
  }, [enabled]);

  return { isCapturing, deviceLabel };
}
