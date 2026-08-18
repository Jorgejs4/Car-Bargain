"use client";

import { useEffect, useState } from "react";

export function ImageCarousel({ images, alt }: { images: string[]; alt: string }) {
  const [index, setIndex] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const move = (delta: number) => setIndex((index + delta + images.length) % images.length);

  useEffect(() => {
    if (!expanded) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setExpanded(false);
      if (event.key === "ArrowLeft") setIndex((current) => (current - 1 + images.length) % images.length);
      if (event.key === "ArrowRight") setIndex((current) => (current + 1) % images.length);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [expanded, images.length]);

  if (!images.length) return null;
  const current = images[index];

  return (
    <>
      <div className="relative overflow-hidden rounded-xl bg-black">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="block w-full cursor-zoom-in"
          title="Ampliar imagen"
          aria-label={`Ampliar imagen ${index + 1}`}
        >
          <img src={current} alt={`${alt} · imagen ${index + 1}`} className="h-[28rem] w-full object-contain" />
        </button>
        <button type="button" aria-label="Imagen anterior" onClick={() => move(-1)} className="absolute left-3 top-1/2 rounded-full bg-black/70 px-3 py-2 text-xl text-white">‹</button>
        <button type="button" aria-label="Imagen siguiente" onClick={() => move(1)} className="absolute right-3 top-1/2 rounded-full bg-black/70 px-3 py-2 text-xl text-white">›</button>
        <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-black/70 px-3 py-1 text-xs text-white">{index + 1} / {images.length} · clicar para ampliar</div>
      </div>

      {expanded && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Imagen ampliada ${index + 1} de ${images.length}`}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
          onClick={(event) => { if (event.target === event.currentTarget) setExpanded(false); }}
        >
          <button type="button" aria-label="Cerrar imagen" onClick={() => setExpanded(false)} className="absolute right-4 top-4 z-10 rounded-full bg-white/15 px-4 py-2 text-2xl text-white hover:bg-white/25">×</button>
          <button type="button" aria-label="Imagen anterior" onClick={() => move(-1)} className="absolute left-3 top-1/2 z-10 rounded-full bg-white/15 px-4 py-3 text-3xl text-white hover:bg-white/25 md:left-8">‹</button>
          <img src={current} alt={`${alt} · imagen ampliada ${index + 1}`} className="max-h-[92vh] max-w-[92vw] object-contain" />
          <button type="button" aria-label="Imagen siguiente" onClick={() => move(1)} className="absolute right-3 top-1/2 z-10 rounded-full bg-white/15 px-4 py-3 text-3xl text-white hover:bg-white/25 md:right-8">›</button>
          <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/70 px-3 py-1 text-sm text-white">{index + 1} / {images.length}</div>
        </div>
      )}
    </>
  );
}
