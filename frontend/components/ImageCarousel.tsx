"use client";

import { useState } from "react";

export function ImageCarousel({ images, alt }: { images: string[]; alt: string }) {
  const [index, setIndex] = useState(0);
  if (!images.length) return null;
  const current = images[index];
  const move = (delta: number) => setIndex((index + delta + images.length) % images.length);
  return (
    <div className="relative overflow-hidden rounded-xl bg-black">
      <a href={current} target="_blank" rel="noreferrer" title="Abrir imagen original en alta resolución">
        <img src={current} alt={`${alt} · imagen ${index + 1}`} className="h-[28rem] w-full object-contain" />
      </a>
      <button onClick={() => move(-1)} className="absolute left-3 top-1/2 rounded-full bg-black/70 px-3 py-2 text-xl text-white">‹</button>
      <button onClick={() => move(1)} className="absolute right-3 top-1/2 rounded-full bg-black/70 px-3 py-2 text-xl text-white">›</button>
      <div className="absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-black/70 px-3 py-1 text-xs text-white">{index + 1} / {images.length} · clic para resolución original</div>
    </div>
  );
}
