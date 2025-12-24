'use client'

import { ReactNode, ReactElement, isValidElement, Children, cloneElement } from 'react'
import { motion, Variants } from 'framer-motion'
import { cn } from '@/lib/utils'

/**
 * AnimatedGroup wraps children in motion.div elements for staggered animations.
 * 
 * @param wrapChildren - If true (default), wraps each child in motion.div.
 *   If false, merges motion props onto valid React elements via cloneElement.
 *   Non-elements (strings, numbers, fragments) are left untouched when wrapChildren=false.
 * 
 * Note: Children should have stable keys for proper reconciliation.
 */
type AnimatedGroupProps = {
  children: ReactNode
  className?: string
  variants?: {
    container?: Variants
    item?: Variants
  }
  wrapChildren?: boolean
}

const defaultContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    },
  },
}

const defaultItemVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
}

export function AnimatedGroup({
  children,
  className,
  variants,
  wrapChildren = true,
}: AnimatedGroupProps) {
  const containerVariants = variants?.container || defaultContainerVariants
  const itemVariants = variants?.item || defaultItemVariants

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      className={cn(className)}
    >
      {Children.map(children, (child) => {
        if (!isValidElement(child)) {
          // Non-elements (strings, numbers, null) - return as-is when not wrapping
          return wrapChildren ? <motion.div variants={itemVariants}>{child}</motion.div> : child
        }
        
        const childKey = child.key
        if (childKey == null && process.env.NODE_ENV === 'development') {
          console.warn('AnimatedGroup: Children should have stable keys for proper animation reconciliation')
        }
        
        if (wrapChildren) {
          return (
            <motion.div key={childKey ?? undefined} variants={itemVariants}>
              {child}
            </motion.div>
          )
        }
        
        // Merge motion props onto the child element via cloneElement
        return cloneElement(child as ReactElement<any>, {
          key: childKey ?? undefined,
          variants: itemVariants,
          initial: 'hidden',
          animate: 'visible',
        })
      })}
    </motion.div>
  )
}
