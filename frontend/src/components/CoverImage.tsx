interface CoverImageProps {
  src?: string | null
  alt: string
  className?: string
}

export function CoverImage({ src, alt, className = '' }: CoverImageProps) {
  if (!src) {
    return (
      <div className={`aspect-[3/4] bg-zinc-800 rounded flex items-center justify-center ${className}`}>
        <span className="text-zinc-500 text-sm text-center px-2">{alt}</span>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      className={`aspect-[3/4] object-cover rounded ${className}`}
    />
  )
}
