import { Camera, CircleStop, Mic, RefreshCw, Upload, Video } from "lucide-react";
import { useEffect, useState } from "react";
import { uploadAnswer } from "../lib/api";
import { loadRecording, removeRecording, saveRecording } from "../lib/recordingCache";
import { useInterviewStore } from "../store/interviewStore";
import type { Question } from "../types";
import { useAnswerRecorder } from "../hooks/useAnswerRecorder";

interface AnswerRecorderProps {
  question: Question;
}

function formatTime(ms: number) {
  const total = Math.floor(ms / 1000);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

export function AnswerRecorder({ question }: AnswerRecorderProps) {
  const recorder = useAnswerRecorder();
  const getIdempotencyKey = useInterviewStore((state) => state.getIdempotencyKey);
  const beginAnalysis = useInterviewStore((state) => state.beginAnalysis);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const minDurationReached = recorder.elapsedMs >= 30_000;
  const restoreRecording = recorder.restoreRecording;

  useEffect(() => {
    loadRecording(question.id)
      .then((cached) => {
        if (cached) restoreRecording(cached.blob, cached.durationMs);
      })
      .catch(() => undefined);
  }, [question.id, restoreRecording]);

  useEffect(() => {
    if (!recorder.recording || recorder.status !== "recorded") return;
    saveRecording({
      questionId: question.id,
      blob: recorder.recording,
      durationMs: recorder.elapsedMs,
      savedAt: new Date().toISOString(),
    }).catch(() => undefined);
  }, [question.id, recorder.elapsedMs, recorder.recording, recorder.status]);

  const handleRetake = () => {
    removeRecording(question.id).catch(() => undefined);
    recorder.retake();
  };

  const handleUpload = async () => {
    if (!recorder.recording || !minDurationReached) return;
    setUploading(true);
    setUploadError(null);
    try {
      const result = await uploadAnswer(
        question.id,
        recorder.recording,
        recorder.elapsedMs,
        getIdempotencyKey(question.id),
        setUploadProgress,
      );
      await removeRecording(question.id).catch(() => undefined);
      beginAnalysis(result.job, result.answer.id);
    } catch (cause) {
      setUploadError(cause instanceof Error ? cause.message : "上传失败，本地录制仍保留，请重试。");
      setUploading(false);
    }
  };

  return (
    <section className="recorder-shell" aria-label="回答录制">
      <div className="camera-stage">
        {recorder.recordingUrl ? (
          <video className="camera-feed" src={recorder.recordingUrl} controls playsInline />
        ) : (
          <video className="camera-feed mirrored" ref={recorder.attachPreview} autoPlay muted playsInline />
        )}

        {(recorder.status === "idle" || recorder.status === "error") && (
          <div className="camera-empty">
            <div className="camera-icon"><Camera size={26} /></div>
            <strong>准备摄像头与麦克风</strong>
            <span>画面只会在你确认上传后发送</span>
            <button className="button button-light" onClick={recorder.requestPermission}>
              <Video size={16} /> 开启预览
            </button>
          </div>
        )}

        {recorder.status === "requesting" && <div className="camera-empty"><span className="spinner" />正在请求系统权限…</div>}

        <div className="recording-overlay">
          <span className={`record-status ${recorder.status === "recording" ? "live" : ""}`}>
            <i /> {recorder.status === "recording" ? "录制中" : recorder.status === "recorded" ? "本地回放" : "预览"}
          </span>
          <span className="timer">{formatTime(recorder.elapsedMs)} / 10:00</span>
        </div>
      </div>

      <div className="recorder-toolbar">
        <div className="device-status">
          <span><Camera size={15} /> 摄像头</span>
          <span><Mic size={15} /> 麦克风</span>
        </div>

        <div className="record-actions">
          {(recorder.status === "ready" || recorder.status === "idle" || recorder.status === "error") && (
            <button className="record-button" onClick={recorder.startRecording} title="开始录制">
              <span />
            </button>
          )}
          {recorder.status === "recording" && (
            <button className="record-button stop" onClick={recorder.stopRecording} title="停止录制">
              <CircleStop size={24} />
            </button>
          )}
          {recorder.status === "recorded" && !uploading && (
            <>
              <button className="button button-secondary" onClick={handleRetake}><RefreshCw size={16} />重录</button>
              <button className="button button-primary" disabled={!minDurationReached} onClick={handleUpload}>
                <Upload size={16} />确认上传
              </button>
            </>
          )}
        </div>

        <div className="duration-hint">
          {recorder.status === "recorded" && !minDurationReached ? "至少录制 30 秒" : "建议 1–3 分钟"}
        </div>
      </div>

      {uploading && (
        <div className="upload-progress" aria-live="polite">
          <div className="progress-label"><span>正在安全上传</span><strong>{Math.round(uploadProgress * 100)}%</strong></div>
          <div className="progress-track"><span style={{ width: `${uploadProgress * 100}%` }} /></div>
        </div>
      )}
      {(recorder.error || uploadError) && <div className="inline-error">{recorder.error || uploadError}</div>}
    </section>
  );
}
