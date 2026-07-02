"use client";

import { useEffect, useRef, useState, type RefObject } from "react";

/** ponytail: one-shot observer; upgrade path is react-intersection-observer if needs grow. */
export function useInView<T extends HTMLElement = HTMLDivElement>(
  rootMargin = "120px",
): [RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node || inView) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [inView, rootMargin]);

  return [ref, inView];
}
