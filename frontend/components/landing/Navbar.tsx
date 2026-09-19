"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { BrandLockup } from "@/components/landing/BrandMark";
import { DASHBOARD_HREF, NAV_LINKS } from "@/lib/navigation";
import { cn } from "@/lib/utils";

const HOME_LINKS = [
  { label: "Home", href: "/" },
  ...NAV_LINKS.map(({ label, href }) => ({ label, href })),
];

export function Navbar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-50 border-b border-meadow/80 bg-chalk/95 backdrop-blur-md">
      <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 md:px-8">
        <BrandLockup />

        <div className="hidden items-center gap-1 md:flex">
          {HOME_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive(link.href)
                  ? "text-moss"
                  : "text-stone hover:text-canopy"
              )}
            >
              {link.label}
            </Link>
          ))}
        </div>

        <div className="hidden md:block">
          <Link
            href={DASHBOARD_HREF}
            className="inline-flex items-center gap-1.5 rounded-md bg-leaf px-4 py-2.5 text-sm font-semibold text-chalk shadow-soft transition hover:bg-moss"
          >
            Try a free risk check
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>

        <button
          aria-expanded={open}
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
          className="relative flex h-10 w-10 items-center justify-center rounded-md border border-meadow md:hidden"
        >
          <span className="sr-only">Menu</span>
          <motion.span
            animate={{ rotate: open ? 45 : 0, y: open ? 0 : -4 }}
            className="absolute h-[1.5px] w-4 rounded-full bg-bark"
          />
          <motion.span
            animate={{ opacity: open ? 0 : 1 }}
            className="absolute h-[1.5px] w-4 rounded-full bg-bark"
          />
          <motion.span
            animate={{ rotate: open ? -45 : 0, y: open ? 0 : 4 }}
            className="absolute h-[1.5px] w-4 rounded-full bg-bark"
          />
        </button>
      </nav>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-meadow bg-chalk md:hidden"
          >
            <div className="flex flex-col px-4 py-3">
              {HOME_LINKS.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className={cn(
                    "border-b border-meadow/70 py-3 text-sm font-medium last:border-0",
                    isActive(link.href) ? "text-moss" : "text-bark"
                  )}
                >
                  {link.label}
                </Link>
              ))}
              <Link
                href={DASHBOARD_HREF}
                onClick={() => setOpen(false)}
                className="mt-3 inline-flex items-center justify-center gap-2 rounded-md bg-leaf py-3 text-sm font-semibold text-chalk"
              >
                Try a free risk check
                <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
