import * as React from "react"
import { cn } from "cn"

function Card({
  className,
  ...props
}) {
  return (
    <div
      data-slot="card"
      className={cn(
        "rounded-xl border border-border bg-card text-card-foreground shadow-xs transition-shadow",
        className
      )}
      {...props}
    />
  )
}

function CardHeader({
  className,
  ...props
}) {
  return (
    <div
      data-slot="card-header"
      className={cn("flex flex-col space-y-1.5 p-6", className)}
      {...props}
    />
  )
}

function CardTitle({
  className,
  ...props
}) {
  return (
    <h3
      data-slot="card-title"
      className={cn(
        "font-heading text-lg font-bold leading-snug tracking-tight text-foreground",
        className
      )}
      {...props}
    />
  )
}

function CardDescription({
  className,
  ...props
}) {
  return (
    <p
      data-slot="card-description"
      className={cn("text-xs text-muted-foreground leading-normal", className)}
      {...props}
    />
  )
}

function CardContent({
  className,
  ...props
}) {
  return (
    <div
      data-slot="card-content"
      className={cn("p-6 pt-0", className)}
      {...props}
    />
  )
}

function CardFooter({
  className,
  ...props
}) {
  return (
    <div
      data-slot="card-footer"
      className={cn("flex items-center p-6 pt-0", className)}
      {...props}
    />
  )
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
}
