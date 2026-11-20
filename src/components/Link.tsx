import type { AnchorHTMLAttributes } from 'react'

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { to: string }

export function Link({ to, ...props }: LinkProps) {
  return <a href={`#${to}`} {...props} />
}
