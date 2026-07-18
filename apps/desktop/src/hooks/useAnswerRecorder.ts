import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderStatus = "idle" | "requesting" | "ready" | "recording" | "recorded" | "error";

const MAX_DURATION_MS = 10 * 60 * 1000;

function chooseMimeType() {
  const candidates = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm", "video/mp4"];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}

export function useAnswerRecorder() {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [recording, setRecording] = useState<Blob | null>(null);
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const previewRef = useRef<HTMLVideoElement | null>(null);

  const stopTimer = useCallback(() => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
  }, []);

  const stopTracks = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  const attachPreview = useCallback((node: HTMLVideoElement | null) => {
    previewRef.current = node;
    if (node && streamRef.current) node.srcObject = streamRef.current;
  }, []);

  const requestPermission = useCallback(async () => {
    setStatus("requesting");
    setError(null);
    try {
      stopTracks();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;
      if (previewRef.current) {
        previewRef.current.srcObject = stream;
        await previewRef.current.play().catch(() => undefined);
      }
      setStatus("ready");
      return true;
    } catch (cause) {
      const denied = cause instanceof DOMException && (cause.name === "NotAllowedError" || cause.name === "PermissionDeniedError");
      setError(denied ? "摄像头或麦克风权限未开启。请在系统设置中允许访问后重试。" : "无法连接摄像头或麦克风，请检查设备是否被其他应用占用。");
      setStatus("error");
      return false;
    }
  }, [stopTracks]);

  const stopRecording = useCallback(() => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    stopTimer();
  }, [stopTimer]);

  const startRecording = useCallback(async () => {
    if (!streamRef.current) {
      const granted = await requestPermission();
      if (!granted || !streamRef.current) return;
    }
    if (recordingUrl) URL.revokeObjectURL(recordingUrl);
    setRecording(null);
    setRecordingUrl(null);
    setElapsedMs(0);
    chunksRef.current = [];

    const mimeType = chooseMimeType();
    const recorder = new MediaRecorder(streamRef.current, mimeType ? { mimeType } : undefined);
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "video/webm" });
      setRecording(blob);
      setRecordingUrl(URL.createObjectURL(blob));
      setElapsedMs(Date.now() - startedAtRef.current);
      setStatus("recorded");
    };
    recorder.start(1000);
    startedAtRef.current = Date.now();
    setStatus("recording");
    timerRef.current = window.setInterval(() => {
      const next = Date.now() - startedAtRef.current;
      setElapsedMs(next);
      if (next >= MAX_DURATION_MS) stopRecording();
    }, 250);
  }, [recordingUrl, requestPermission, stopRecording]);

  const restoreRecording = useCallback((blob: Blob, durationMs: number) => {
    if (recordingUrl) URL.revokeObjectURL(recordingUrl);
    setRecording(blob);
    setRecordingUrl(URL.createObjectURL(blob));
    setElapsedMs(durationMs);
    setError(null);
    setStatus("recorded");
  }, [recordingUrl]);

  const retake = useCallback(() => {
    if (recordingUrl) URL.revokeObjectURL(recordingUrl);
    setRecording(null);
    setRecordingUrl(null);
    setElapsedMs(0);
    setStatus(streamRef.current ? "ready" : "idle");
  }, [recordingUrl]);

  useEffect(() => () => {
    stopTimer();
    stopTracks();
    if (recordingUrl) URL.revokeObjectURL(recordingUrl);
  }, [recordingUrl, stopTimer, stopTracks]);

  return {
    status,
    elapsedMs,
    recording,
    recordingUrl,
    error,
    attachPreview,
    requestPermission,
    startRecording,
    stopRecording,
    restoreRecording,
    retake,
  };
}
