interface HeaderProps {
  title: string
  children?: React.ReactNode
}

export function Header({ title, children }: HeaderProps) {
  return (
    <header className="h-14 bg-zinc-950 border-b border-zinc-800 flex items-center justify-between px-6">
      <h2 className="text-lg font-semibold text-zinc-100">{title}</h2>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </header>
  )
}
