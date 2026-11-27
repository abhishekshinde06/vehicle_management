import { useCallback, useEffect, useRef, useState } from 'react';

function mapCameraError(err) {
  if (!err) return 'Unable to access the camera.';
  if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
    return 'Camera permission denied. Allow camera access in your browser settings and try again.';
  }
  if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
    return 'No camera device was detected on this device.';
  }
  if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
    return 'Camera is currently in use by another app. Close other camera apps and try again.';
  }
  return err.message || 'Failed to start live camera stream.';
}

export default function CameraCaptureCard({
  photoType,
  label,
  instruction,
  unlocked,
  capture,
  onCapture,
  onClear,
}) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);

  const [isStreaming, setIsStreaming] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [cameraError, setCameraError] = useState('');

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsStreaming(false);
    setIsStarting(false);
  }, []);

  useEffect(() => {
    return () => {
      stopStream();
    };
  }, [stopStream]);

  useEffect(() => {
    if (!unlocked && isStreaming) {
      stopStream();
    }
  }, [unlocked, isStreaming, stopStream]);

  useEffect(() => {
    if (isStreaming && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [isStreaming]);

  const startCamera = async () => {
    setCameraError('');
    if (!unlocked) return;

    if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setCameraError('Live camera capture is not supported in this browser.');
      return;
    }

    if (typeof window !== 'undefined' && !window.isSecureContext) {
      setCameraError(
        'Camera access requires a secure browser context (HTTPS or localhost).'
      );
      return;
    }

    stopStream();
    setIsStarting(true);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });

      streamRef.current = stream;
      setIsStreaming(true);
      setIsStarting(false);
    } catch (err) {
      stopStream();
      setCameraError(mapCameraError(err));
    }
  };

  const handleTakePhoto = () => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
      setCameraError('Camera stream is not ready yet. Wait a moment and tap Capture again.');
      return;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (!blob) {
          setCameraError('Failed to capture image frame. Please try again.');
          return;
        }
        const previewUrl = URL.createObjectURL(blob);
        stopStream();
        onCapture(photoType, {
          blob,
          previewUrl,
          capturedAt: new Date().toISOString(),
        });
      },
      'image/jpeg',
      0.85
    );
  };

  const handleRetake = () => {
    onClear(photoType);
    startCamera();
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-xs flex flex-col justify-between gap-4">
      <div>
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className="text-xs font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-2.5 py-1 rounded-md">
            {photoType}
          </span>
          {capture ? (
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-md">
              Captured
            </span>
          ) : (
            <span className="text-xs font-semibold text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
              Required
            </span>
          )}
        </div>
        <h3 className="text-base font-bold text-slate-900 mt-2">{label}</h3>
        <p className="text-sm text-slate-600 mt-0.5">{instruction}</p>
      </div>

      {cameraError && (
        <div role="alert" className="rounded-xl bg-red-50 border border-red-200 px-3 py-2.5 text-xs text-red-800">
          {cameraError}
        </div>
      )}

      {!unlocked && (
        <div className="rounded-xl bg-slate-100 border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          Locked until live GPS location is verified at the selected petrol pump.
        </div>
      )}

      {unlocked && isStreaming && (
        <div className="space-y-3">
          <div className="relative overflow-hidden rounded-xl bg-black aspect-video border border-slate-300">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover"
            />
            <div className="pointer-events-none absolute inset-3 border-2 border-white/60 rounded-lg" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={handleTakePhoto}
              className="w-full rounded-xl bg-emerald-600 px-4 py-3.5 text-base font-bold text-white hover:bg-emerald-700 active:scale-[0.99]"
            >
              Capture Photo
            </button>
            <button
              type="button"
              onClick={stopStream}
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3.5 text-base font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {unlocked && !isStreaming && capture && (
        <div className="space-y-3">
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-900 aspect-video">
            <img
              src={capture.previewUrl}
              alt={`${label} preview`}
              className="w-full h-full object-contain"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={handleRetake}
              className="w-full rounded-xl border border-blue-600 bg-blue-50 px-4 py-3 text-sm font-bold text-blue-700 hover:bg-blue-100"
            >
              Retake Photo
            </button>
            <button
              type="button"
              onClick={() => onClear(photoType)}
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Remove
            </button>
          </div>
        </div>
      )}

      {unlocked && !isStreaming && !capture && (
        <button
          type="button"
          onClick={startCamera}
          disabled={isStarting}
          className="w-full rounded-xl bg-blue-600 px-4 py-4 text-base font-bold text-white shadow-xs hover:bg-blue-700 disabled:opacity-60"
        >
          {isStarting ? 'Starting Camera...' : `Open Camera for ${photoType}`}
        </button>
      )}
    </div>
  );
}
