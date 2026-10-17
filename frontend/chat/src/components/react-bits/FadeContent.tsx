// React Bits FadeContent, c83b5e7e026f003af33ff9ebc3d93afb5c86ad22.
// Adapted for reduced motion, timer cleanup and the existing strict TS config.
// Source and license: frontend/chat/THIRD_PARTY.md.
import { useEffect, useRef, useState, type ReactNode } from "react"
import { useMediaQuery } from "@/lib/hooks"

export default function FadeContent({ children, duration = 180, delay = 0, threshold = 0, className = "" }: {
  children: ReactNode; duration?: number; delay?: number; threshold?: number; className?: string
}) {
  const [inView, setInView] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const reduce = useMediaQuery("(prefers-reduced-motion: reduce)")
  useEffect(() => {
    const element = ref.current
    if (!element || reduce) return
    if (typeof IntersectionObserver === "undefined") { setInView(true); return }
    let timer = 0
    const observer = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) {
        observer.unobserve(element)
        timer = window.setTimeout(() => setInView(true), delay)
      }
    }, { threshold })
    observer.observe(element)
    return () => { observer.disconnect(); window.clearTimeout(timer) }
  }, [threshold, delay, reduce])
  return <div ref={ref} className={className} style={{ opacity: reduce || inView ? 1 : 0, transition: reduce ? "none" : `opacity ${duration}ms ease-out` }}>{children}</div>
}
