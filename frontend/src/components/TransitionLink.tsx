import { ReactNode, MouseEvent } from 'react'
import { Link, LinkProps } from 'react-router-dom'
import { useTransition } from '../context/TransitionContext'

interface TransitionLinkProps extends Omit<LinkProps, 'onClick'> {
  children: ReactNode
  onClick?: (e: MouseEvent<HTMLAnchorElement>) => void
}

export default function TransitionLink({
  children,
  to,
  onClick,
  ...props
}: TransitionLinkProps) {
  const { navigateWithTransition } = useTransition()

  const handleClick = (e: MouseEvent<HTMLAnchorElement>) => {
    e.preventDefault()
    onClick?.(e)
    navigateWithTransition(typeof to === 'string' ? to : to.pathname || '/')
  }

  return (
    <Link to={to} onClick={handleClick} {...props}>
      {children}
    </Link>
  )
}

// Hook for programmatic navigation with transitions
export { useTransition } from '../context/TransitionContext'
