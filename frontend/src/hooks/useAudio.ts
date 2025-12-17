import { useCallback, useRef, useState } from "react";

export function useAudio() {
  const ref = useRef<HTMLAudioElement | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "playing" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [rate, setRate] = useState(1);

  const ensure = () => {
    if (!ref.current) {
      ref.current = new Audio();
      ref.current.addEventListener("ended", () => setStatus("idle"));
    }
    return ref.current;
  };

  const play = useCallback(async (url: string, speed = 1) => {
    try {
      const el = ensure();
      setStatus("loading");
      setError(null);
      el.src = url;
      el.playbackRate = speed;
      await el.play();
      setRate(speed);
      setStatus("playing");
    } catch (e: any) {
      setStatus("error");
      setError(e?.message || "Playback failed");
    }
  }, []);

  const stop = useCallback(() => {
    const el = ensure();
    el.pause();
    el.currentTime = 0;
    setStatus("idle");
  }, []);

  const changeRate = useCallback((r: number) => {
    setRate(r);
    ensure().playbackRate = r;
  }, []);

  return { play, stop, status, error, rate, changeRate };
}
