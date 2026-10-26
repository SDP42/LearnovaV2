import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-[background-color,color,border-color,box-shadow,transform] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground shadow-sm hover:-translate-y-px hover:bg-[#A84423] hover:shadow-[0_10px_20px_-10px_rgb(194_80_42/0.7)] active:translate-y-0",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:-translate-y-px hover:bg-[#A53125] active:translate-y-0",
        outline:
          "border border-input bg-white text-foreground shadow-sm hover:-translate-y-px hover:border-[#E3A98B] hover:bg-[#FDEEE3] hover:text-[#8F3A18] active:translate-y-0",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:-translate-y-px hover:bg-[#EBDACB] active:translate-y-0",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-lg px-3 text-[13px] max-sm:h-10",
        lg: "h-11 rounded-xl px-6",
        icon: "size-10 sm:size-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

const Button = React.forwardRef(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
